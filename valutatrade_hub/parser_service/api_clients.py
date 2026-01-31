import time
from abc import ABC, abstractmethod
from email.utils import parsedate_to_datetime

import requests
from requests.exceptions import RequestException

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


def now_iso() -> str:
    """возвращает текущее время в iso"""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class BaseApiClient(ABC):
    """базовый класс для клиентов api"""

    @abstractmethod
    def fetch_rates(self) -> dict:
        """возвращает курсы в едином формате"""
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    """клиент для получения крипто курсов"""

    def __init__(self, cfg: ParserConfig | None = None):
        """создаёт клиент с настройками"""
        # если настройки не передали, берём стандартные
        self._cfg = cfg or ParserConfig()

    def fetch_rates(self) -> dict:
        """получает курсы криптовалют к usd"""
        ids = []
        code_by_id = {}

        for code in self._cfg.crypto_currencies:
            #приводим к верхнему регистру
            c = str(code).strip().upper()

            #ищем соответствующий coin id
            coin_id = self._cfg.crypto_id_map.get(c)
            if not coin_id:
                continue

            ids.append(coin_id)
            code_by_id[coin_id] = c

        #если нечего запрашивать, возвращаем пустой словарь
        if not ids:
            return {}

        #параметры запроса coingecko
        params = {"ids": ",".join(ids), "vs_currencies": "usd"}

        #измеряем время запроса
        start = time.perf_counter()
        try:
            resp = requests.get(
                self._cfg.coingecko_url,
                params=params,
                timeout=self._cfg.request_timeout,
            )
        except RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}")

        request_ms = int((time.perf_counter() - start) * 1000)

        #проверяем http статус
        if resp.status_code != 200:
            raise ApiRequestError(
                f"Ошибка при обращении к внешнему API: http {resp.status_code}"
            )

        #пытаемся разобрать json
        try:
            data = resp.json()
        except Exception:
            raise ApiRequestError("Ошибка при обращении к внешнему API: плохой json")

        if not isinstance(data, dict):
            raise ApiRequestError(
                "Ошибка при обращении к внешнему API: ответ не объект"            )

        #общие метаданные ответа
        meta_base = {
            "request_ms": request_ms,
            "status_code": int(resp.status_code),
            "etag": resp.headers.get("ETag", ""),
        }

        #фиксируем время обновления 
        ts = now_iso()

        #приводим ответ к единому формату для updater
        out = {}
        for coin_id, payload in data.items():
            if not isinstance(payload, dict):
                continue

            usd = payload.get("usd")
            if not isinstance(usd, (int, float)):
                continue

            #по coin id возвращаем исходный тикер
            code = code_by_id.get(coin_id)
            if not code:
                continue

            #ключ пары делаем как BTC_USD
            out[f"{code}_USD"] = {
                "rate": float(usd),
                "updated_at": ts,
                "source": "CoinGecko",
                "meta": {**meta_base, "raw_id": coin_id},
            }

        return out


class ExchangeRateApiClient(BaseApiClient):
    """клиент для получения фиатных курсов"""

    def __init__(self, cfg: ParserConfig | None = None):
        """создаёт клиент с настройками"""
        #если настройки не передали, берём стандартные
        self._cfg = cfg or ParserConfig()

    def fetch_rates(self) -> dict:
        """получает курсы фиата к usd"""
        #ключ берём из переменной окружения через config
        api_key = str(self._cfg.exchangerate_api_key).strip()
        if not api_key:
            raise ApiRequestError("Ошибка при обращении к внешнему API: нет api ключа")

        #этот эндпоинт отдаёт курсы от usd ко всем валютам
        url = (
            f"{self._cfg.exchangerate_api_url}/{api_key}/latest/"
            f"{self._cfg.base_fiat_currency}"
        )

        #измеряем время запроса для meta
        start = time.perf_counter()
        try:
            resp = requests.get(url, timeout=self._cfg.request_timeout)
        except RequestException as e:
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {e}")

        request_ms = int((time.perf_counter() - start) * 1000)

        #проверяем http статус
        if resp.status_code != 200:
            raise ApiRequestError(
                f"Ошибка при обращении к внешнему API: http {resp.status_code}"
            )

        #пытаемся разобрать json
        try:
            data = resp.json()
        except Exception:
            raise ApiRequestError("Ошибка при обращении к внешнему API: плохой json")

        if not isinstance(data, dict):
            raise ApiRequestError(
                "Ошибка при обращении к внешнему API: ответ не объект"            )

        #базовая проверка успеха ответа
        if data.get("result") != "success":
            reason = data.get("error-type") or "ошибка сервиса"
            raise ApiRequestError(f"Ошибка при обращении к внешнему API: {reason}")

        rates = data.get("rates")
        if rates is None:
            rates = data.get("conversion_rates")
        if not isinstance(rates, dict):
            raise ApiRequestError("Ошибка при обращении к внешнему API: нет rates")

        meta_base = {
            "request_ms": request_ms,
            "status_code": int(resp.status_code),
            "etag": resp.headers.get("ETag", ""),
        }

        #берём время обновления из ответа, если получится
        ts_fetch = now_iso()

        provider_updated = data.get("time_last_update_utc")
        provider_ts = ""
        if isinstance(provider_updated, str) and provider_updated.strip():
            try:
                provider_ts = (
                    parsedate_to_datetime(provider_updated)
                    .replace(microsecond=0)
                    .isoformat()
                )
            except Exception:
                provider_ts = ""

        out = {}
        for code in self._cfg.fiat_currencies:
            c = str(code).strip().upper()

            #usd мы добавляем отдельно
            if c == "USD":
                continue

            v = rates.get(c)
            if not isinstance(v, (int, float)):
                continue
            if float(v) == 0.0:
                continue

            #api даёт usd-eur, а нам нужен eur-usd
            out[f"{c}_USD"] = {
                "rate": 1.0 / float(v),
                "updated_at": ts_fetch,
                "source": "ExchangeRate-API",
                "meta": {
                    **meta_base,
                    "raw_id": "latest/USD",
                    "provider_updated_at": provider_ts,
                },
            }

        # обавляем usd_usd на всякий случай
        out["USD_USD"] = {
            "rate": 1.0,
            "updated_at": ts_fetch,
            "source": "ExchangeRate-API",
            "meta": {
                **meta_base,
                "raw_id": "latest/USD",
                "provider_updated_at": provider_ts,
            },
        }

        return out
