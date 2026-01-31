import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import get_data_dir, load_json, save_json
from valutatrade_hub.parser_service.config import ParserConfig


def now_utc() -> str:
    """возвращает текущее время в utc"""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_load_json(filename: str, default):
    """читает json и при проблемах кидает ApiRequestError"""
    try:
        return load_json(filename, default)
    except Exception as e:
        raise ApiRequestError(str(e))


def safe_save_json(filename: str, data) -> None:
    """пишет json и при проблемах кидает ApiRequestError"""
    try:
        save_json(filename, data)
    except Exception as e:
        raise ApiRequestError(str(e))
    

def data_path(filename: str) -> Path:
    """строит путь до файла в папке data"""
    cfg = ParserConfig()
    if filename == "rates.json":
        return cfg.rates_path
    if filename == "exchange_rates.json":
        return cfg.history_path
    return get_data_dir() / filename

def atomic_save_json(filename: str, data) -> None:
    """пишет json атомарно через временный файл"""
    path = data_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=path.name,
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception as e:
        try:
            os.remove(tmp_name)
        except Exception:
            pass
        raise ApiRequestError(str(e))


def load_rates_cache() -> dict:
    """читает rates.json"""
    data = safe_load_json("rates.json", {})
    if not isinstance(data, dict):
        return {"pairs": {}, "last_refresh": ""}

    #формат по тз
    pairs = data.get("pairs")
    if isinstance(pairs, dict):
        return {"pairs": pairs, "last_refresh": str(data.get("last_refresh", ""))}

    #формат из прошлых шагов превращаем в новый
    migrated_pairs = {}
    for k, v in data.items():
        if not isinstance(k, str) or "_" not in k:
            continue
        if not isinstance(v, dict):
            continue
        if "rate" not in v or "updated_at" not in v:
            continue
        migrated_pairs[k] = v

    return {"pairs": migrated_pairs, "last_refresh": str(data.get("last_refresh", ""))}



def save_rates_cache(rates: dict) -> None:
    """пишет rates.json"""
    #фиксируем момент общего обновления
    pairs = rates.get("pairs")
    if not isinstance(pairs, dict):
        pairs = {}

    #фиксируем момент общего обновления
    out = {"pairs": pairs, "last_refresh": now_utc()}

    #пишем атомарно, чтобы не получит пустой файл при сбое
    atomic_save_json("rates.json", out)


def append_exchange_records(records: list[dict]) -> None:
    """добавляет измерения в exchange_rates.json без дублей"""
    history = safe_load_json("exchange_rates.json", [])
    if not isinstance(history, list):
        history = []

    #собираем уже существующие id
    existing = set()
    for item in history:
        if isinstance(item, dict) and "id" in item:
            existing.add(str(item["id"]))

    #добавляем только новые записи
    added = False
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("id")
        if not isinstance(rec_id, str) or not rec_id:
            continue
        if rec_id in existing:
            continue
        history.append(rec)
        existing.add(rec_id)
        added = True

    #пишем файл только если что-то добавили
    if added:
        atomic_save_json("exchange_rates.json", history)

