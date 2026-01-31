import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.core.utils import get_data_dir


@dataclass(frozen=True)
class ParserConfig:
    """настройки parser service"""

    #ключ берём из переменной окружения
    exchangerate_api_key: str = os.getenv("EXCHANGERATE_API_KEY", "")

    #эндпоинты
    coingecko_url: str = "https://api.coingecko.com/api/v3/simple/price"
    exchangerate_api_url: str = "https://v6.exchangerate-api.com/v6"

    #валюты
    base_fiat_currency: str = "USD"
    fiat_currencies: tuple[str, ...] = ("EUR", "GBP", "RUB")
    crypto_currencies: tuple[str, ...] = ("BTC", "ETH", "SOL")

    #соответствие тикера и id в coingecko
    crypto_id_map: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )
    #сетевые параметры
    request_timeout: int = 10

    #пути к файлам в data/
    rates_filename: str = "rates.json"
    history_filename: str = "exchange_rates.json"

    @property
    def rates_path(self) -> Path:
        """путь до rates.json"""
        return get_data_dir() / self.rates_filename

    @property
    def history_path(self) -> Path:
        """путь до exchange_rates.json"""
        return get_data_dir() / self.history_filename
