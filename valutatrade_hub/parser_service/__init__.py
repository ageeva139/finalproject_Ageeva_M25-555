"""parser service package"""

__all__ = ["refresh_rates_cache"]


def refresh_rates_cache() -> dict:
    """обновляет rates.json и пишет историю в exchange_rates.json"""
    #импорт внутри функции, чтобы не тянуть updater при импорте пакета
    from valutatrade_hub.parser_service.updater import refresh_rates_cache as _impl

    return _impl()
