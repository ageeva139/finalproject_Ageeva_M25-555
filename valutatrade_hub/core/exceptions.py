class InsufficientFundsError(Exception):
    """ошибка когда денег не хватает"""

    def __init__(self, available: float, required: float, code: str):
        def fmt(v):
            return f"{float(v):.8f}".rstrip("0").rstrip(".")
        
        msg = (
            f"Недостаточно средств: доступно {fmt(available)} {code}, "
            f"требуется {fmt(required)} {code}"
        )
        super().__init__(msg)


class CurrencyNotFoundError(Exception):
    """ошибка когда валюта не найдена в реестре"""

    def __init__(self, code: str):
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """ошибка когда внешний источник курсов недоступен"""

    def __init__(self, reason: str):
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
