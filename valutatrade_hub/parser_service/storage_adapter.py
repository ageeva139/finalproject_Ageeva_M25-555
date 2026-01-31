from dataclasses import dataclass

from valutatrade_hub.parser_service.storage import (
    append_exchange_records,
    load_rates_cache,
    save_rates_cache,
)


@dataclass
class StorageAdapter:
    """обёртка над функциями storage"""

    def load_rates(self) -> dict:
        """читает rates.json"""
        return load_rates_cache()

    def save_rates(self, data: dict) -> None:
        """пишет rates.json"""
        save_rates_cache(data)

    def append_history(self, records: list[dict]) -> None:
        """добавляет записи в exchange_rates.json"""
        append_exchange_records(records)
