from datetime import datetime, timezone
import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import (
    append_exchange_records,
    load_rates_cache,
    save_rates_cache,
)


def now_iso() -> str:
    """возвращает текущее время в iso"""
    return datetime.now().replace(microsecond=0).isoformat()


def to_utc(ts: str) -> str:
    """приводит iso timestamp к виду utc"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc).replace(microsecond=0)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        #если дата сломана, берём текущее utc время
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


class RatesUpdater:
    """координирует обновление курсов"""

    def __init__(self, clients: list, logger: logging.Logger | None = None):
        """создаёт updater с клиентами"""
        self._clients = clients
        self._logger = logger or logging.getLogger("parser_service")

    def run_update(self) -> dict:
        """обновляет rates.json и пишет историю в exchange_rates.json"""
        self._logger.info("update start")

        #получаем данные из всех источников
        merged = {}

        for client in self._clients:
            name = client.__class__.__name__
            try:
                self._logger.info("fetch start client=%s", name)
                data = client.fetch_rates()
                if isinstance(data, dict):
                    merged.update(data)
                self._logger.info("fetch ok client=%s pairs=%d", name, len(data))
            except ApiRequestError as e:
                self._logger.info("fetch error client=%s err=%s", name, str(e))
            except Exception as e:
                self._logger.info("fetch error client=%s err=%s", name, str(e))

        #читаем текущий кеш
        rates = load_rates_cache()
        pairs = rates.get("pairs")
        if not isinstance(pairs, dict):
            pairs = {}

        #обновляем только если новая запись свежее
        for pair, item in merged.items():
            if not isinstance(item, dict):
                continue

            #приводим updated_at к utc чтобы формат был одинаковым
            ts_new = to_utc(str(item.get("updated_at", "")))
            rate_new = item.get("rate")
            source_new = str(item.get("source", ""))
            if not isinstance(rate_new, (int, float)):
                continue

            current = pairs.get(pair)
            if isinstance(current, dict) and "updated_at" in current:
                ts_old = to_utc(str(current.get("updated_at", "")))
                if ts_new <= ts_old:
                    continue

            pairs[pair] = {
                "rate": float(rate_new),
                "updated_at": ts_new,
                "source": source_new,
            }

        #last_refresh ставим всегда на момент запуска обновления
        last_refresh = to_utc(datetime.now(timezone.utc).isoformat())

        #сохраняем кеш
        save_rates_cache({"pairs": pairs, "last_refresh": last_refresh})

        #готовим записи истории по одной на каждую пару
        records = []
        for pair, item in merged.items():
            if not isinstance(item, dict):
                continue

            parts = str(pair).split("_")
            if len(parts) != 2:
                continue

            from_code = parts[0].strip().upper()
            to_code = parts[1].strip().upper()

            #простая проверка формата кодов
            if not (2 <= len(from_code) <= 5) or " " in from_code:
                continue
            if not (2 <= len(to_code) <= 5) or " " in to_code:
                continue

            rate = item.get("rate")
            if not isinstance(rate, (int, float)):
                continue

            ts = to_utc(str(item.get("updated_at", "")))
            rec_id = f"{from_code}_{to_code}_{ts}"

            records.append(
                {
                    "id": rec_id,
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": float(rate),
                    "timestamp": ts,
                    "source": str(item.get("source", "")),
                    "meta": item.get("meta", {}),
                }
            )

        #пишем историю только по успешным валидным записям
        append_exchange_records(records)

        self._logger.info("update finish merged=%d", len(merged))

        return {"pairs": pairs, "last_refresh": last_refresh}


def refresh_rates_cache() -> dict:
    """обновляет rates.json и пишет историю в exchange_rates.json"""
    #получаем данные из двух источников
    updater = RatesUpdater([CoinGeckoClient(), ExchangeRateApiClient()])
    return updater.run_update()
