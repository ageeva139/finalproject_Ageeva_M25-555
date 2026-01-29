import json
from pathlib import Path


def get_data_dir() -> Path:
    """возвращает путь к папке data"""
    return Path(__file__).resolve().parents[2] / "data"


def load_json(filename: str, default):
    """читает json из data и возвращает default если файла нет"""
    path = get_data_dir() / filename
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data) -> None:
    """записывает json в data"""
    path = get_data_dir() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_currency_code(currency_code: str) -> str:
    """проверяет код валюты и приводит к верхнему регистру"""
    if not isinstance(currency_code, str) or not currency_code.strip():
        raise ValueError("currency_code не может быть пустым")
    return currency_code.strip().upper()


def validate_amount(amount) -> float:
    """проверяет что сумма - это число и оно больше нуля"""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError("сумма должна быть числом")
    amount = float(amount)
    if amount <= 0:
        raise ValueError("сумма должна быть больше нуля")
    return amount
