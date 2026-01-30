import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging() -> logging.Logger:
    """настраивает логгер доменных действий"""
    settings = SettingsLoader()
    log_dir = Path(str(settings.get("LOG_DIR", "logs")))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("actions")
    #если логгер уже настроен, не добавляем хендлеры второй раз
    if logger.handlers:
        return logger

    #уровень по умолчанию
    logger.setLevel(logging.INFO)

    #пишем в файл и включаем ротацию по размеру
    log_path = log_dir / "actions.log"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    #задаём формат
    fmt = logging.Formatter(
        "%(levelname)s %(asctime)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)

    logger.addHandler(handler)

    #не отправляем эти записи в root logger, чтобы избежать дублирования
    logger.propagate = False
    return logger
