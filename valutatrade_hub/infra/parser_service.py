import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.request import urlopen

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import load_json, save_json
from valutatrade_hub.infra.settings import SettingsLoader

#словарь соотвествтия криптовалюты
CRYPTO_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}


def now_iso() -> str:
    """возвращает текущее время в iso"""
    return datetime.now().replace(microsecond=0).isoformat()


def safe_load_json(filename: str, default):
    """читает json и при проблемах возвращает ApiRequestError"""
    try:
        return load_json(filename, default)
    except Exception as e:
        raise ApiRequestError(str(e))


def safe_save_json(filename: str, data) -> None:
    """пишет json и при проблемах возвращает ApiRequestError"""
    try:
        save_json(filename, data)
    except Exception as e:
        raise ApiRequestError(str(e))


def http_get_json(url: str) -> dict:
    """делает get запрос и возвращает json"""
    #используем urlopen чтобы не добавлять внешние зависимости
    try:
        with urlopen(url, timeout=15) as r:
            raw = r.read().decode("utf-8")

        #превращаем строку в python dict
        data = json.loads(raw)

        #если пришло не то, что ожидаем, считаем это ошибкой api
        if not isinstance(data, dict):
            raise ApiRequestError("ответ api не похож на json объект")
        return data

    except ApiRequestError:
        raise

    #любые другие ошибки превращаем в ApiRequestError
    except Exception as e:
        raise ApiRequestError(str(e))


def fetch_crypto_rates_usd(codes: list[str] | None = None) -> dict:
    """получает курсы криптовалют к usd через coingecko"""
    #если список валют не передали, берём из настроек
    if codes is None:
        settings = SettingsLoader()
        codes = list(settings.get("CRYPTO_CODES", ["BTC", "ETH", "SOL"]))

    #собираем coin ids для запроса и маппинг id -> тикер
    ids = []
    code_by_id = {}
    for code in codes:
        c = str(code).strip().upper()
        coin_id = CRYPTO_ID_MAP.get(c)
        if coin_id is None:
            continue
        ids.append(coin_id)
        code_by_id[coin_id] = c

    #если ничего не подошло, возвращаем пустой словарь
    if not ids:
        return {}

    #делаем запрос к coingecko
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={','.join(ids)}&vs_currencies=usd"
    )
    data = http_get_json(url)

    #у coingecko нет времени обновления, ставим текущее
    now = now_iso()

    #приводим ответ к единому формату
    out = {}
    for coin_id, payload in data.items():
        if not isinstance(payload, dict):
            continue
        usd = payload.get("usd")
        if not isinstance(usd, (int, float)):
            continue

        code = code_by_id.get(coin_id)
        if code is None:
            continue

        out[f"{code}_USD"] = {
            "rate": float(usd),
            "updated_at": now,
            "source": "CoinGecko",
        }

    return out


def fetch_fiat_rates_usd(codes: list[str] | None = None) -> dict:
    """получает курсы фиатных валют к usd через exchangerate-api"""
    settings = SettingsLoader()

    #ключ лежит в config.json
    api_key = str(settings.get("EXCHANGERATE_API_KEY", "")).strip()
    if not api_key:
        raise ApiRequestError("не задан EXCHANGERATE_API_KEY в config.json")

    #список фиатных валют можно задавать в config.json
    if codes is None:
        codes = list(settings.get("FIAT_CODES", ["EUR", "GBP", "RUB"]))

    #запрос возвращает курсы USD -> XXX
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    data = http_get_json(url)

    #проверяем что api ответил успехом
    if data.get("result") != "success":
        raise ApiRequestError("exchangeRate-api вернул ошибку")

    rates = data.get("rates")
    if rates is None:
        rates = data.get("conversion_rates")
    if not isinstance(rates, dict):
        raise ApiRequestError("в ответе нет поля rates или conversion_rates")


    #берём время обновления если оно есть, иначе ставим текущее
    ts = now_iso()
    updated = data.get("time_last_update_utc")
    if isinstance(updated, str) and updated.strip():
        try:
            ts = parsedate_to_datetime(updated).replace(microsecond=0).isoformat()
        except Exception:
            pass

    out = {}
    for code in codes:
        c = str(code).strip().upper()
        if c == "USD":
            continue

        v = rates.get(c)
        if not isinstance(v, (int, float)):
            continue
        if float(v) == 0.0:
            continue

        out[f"{c}_USD"] = {
            "rate": 1.0 / float(v),
            "updated_at": ts,
            "source": "ExchangeRate-API",
        }

    #на всякий случай кладём и usd_usd
    out["USD_USD"] = {"rate": 1.0, "updated_at": ts, "source": "ExchangeRate-API"}
    return out


def refresh_rates_cache() -> dict:
    """обновляет rates.json и возвращает обновлённый словарь"""
    #получаем данные из двух источников
    crypto = fetch_crypto_rates_usd()
    fiat = fetch_fiat_rates_usd()

    #объединяем словари курсов
    merged = {}
    merged.update(crypto)
    merged.update(fiat)

    #читаем текущий rates.json, чтобы не терять служебные поля
    rates = safe_load_json("rates.json", {})
    if not isinstance(rates, dict):
        rates = {}

    #обновляем курсы в файле
    for k, v in merged.items():
        rates[k] = v

    #фиксируем момент общего обновления
    rates["last_refresh"] = now_iso()

    #сохраняем в json
    safe_save_json("rates.json", rates)
    return rates
