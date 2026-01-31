import time

from valutatrade_hub.parser_service.updater import refresh_rates_cache


def run_scheduler(interval_seconds: int = 300) -> None:
    """периодически обновляет курсы в бесконечном цикле"""
    while True:
        # делаем обновление
        refresh_rates_cache()

        # ждём до следующего запуска
        time.sleep(interval_seconds)
