import json
from pathlib import Path
from typing import Any


class SettingsLoader:
    """singleton для конфигурации проекта"""

    _instance = None

    def __new__(cls):
        #используем __new__ потому что это самый простой singleton без метаклассов
        #и гарантирует что объект создаётся один раз на весь процесс
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._config = {}
        return cls._instance

    def _default_config(self) -> dict:
        #базовые значения если config.json отсутствует
        return {
            "DATA_DIR": "data",
            "RATES_TTL_SECONDS": 300,
            "DEFAULT_BASE_CURRENCY": "USD",
            "LOG_DIR": "logs",
            "LOG_FORMAT": "%(asctime)s %(levelname)s %(message)s",
        }

    def reload(self) -> None:
        """перезагружает конфигурацию из файла"""
        config = self._default_config()

        #читаем config.json если он есть
        root = Path(__file__).resolve().parents[2]
        cfg_path = root / "config.json"
        if cfg_path.exists():
            try:
                loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    config.update(loaded)
            except Exception:
                pass

        self._config = config
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """возвращает значение по ключу"""
        if not self._loaded:
            self.reload()
        return self._config.get(key, default)
