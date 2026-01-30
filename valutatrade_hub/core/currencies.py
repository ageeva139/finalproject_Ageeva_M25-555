from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


def validate_code(code: str) -> str:
    """проверяет код валюты и возвращает нормализованный"""
    #приводим к верхнему регистру и убираем пробелы по краям
    if not isinstance(code, str):
        raise ValueError("code должен быть строкой")
    code = code.strip().upper()

    #без пробелов внутри, длина от 2 до 5
    if " " in code:
        raise ValueError("code не должен содержать пробелы")
    if not (2 <= len(code) <= 5):
        raise ValueError("code должен быть длиной 2-5 символов")

    #только буквы и цифры
    if not code.isalnum():
        raise ValueError("code должен быть буквенно-цифровым")

    return code


def validate_name(name: str) -> str:
    """проверяет что name не пустое"""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name не может быть пустым")
    return name.strip()


def fmt_mcap(value: float) -> str:
    """форматирует капитализацию как 1.12e12"""
    # используем научную нотацию как в примере тз
    s = f"{float(value):.2e}"
    return s.replace("e+", "e")


class Currency(ABC):
    """базовый класс валюты"""

    def __init__(self, name: str, code: str):
        self.name = validate_name(name)
        self.code = validate_code(code)

    @abstractmethod #обязательный для наследников
    def get_display_info(self) -> str:
        """возвращает строку для ui и логов"""
        raise NotImplementedError


class FiatCurrency(Currency):
    """фиатная валюта"""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code) #вызываем конструктор базового класса
        #страна
        self.issuing_country = validate_name(issuing_country)

    def get_display_info(self) -> str:
        """возвращает строку для ui и логов"""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """криптовалюта"""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        #алгоритм и капитализация для криптовалюты
        self.algorithm = validate_name(algorithm)

        if not isinstance(market_cap, (int, float)) or isinstance(market_cap, bool):
            raise ValueError("market_cap должен быть числом")
        if market_cap < 0:
            raise ValueError("market_cap не может быть отрицательным")
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        """возвращает строку для ui и логов"""
        mcap = fmt_mcap(self.market_cap)
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap})"


#реестр валют для get_currency
CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.50e11),
}


def get_currency(code: str) -> Currency:
    """возвращает валюту по коду"""
    normalized = validate_code(code)
    currency = CURRENCY_REGISTRY.get(normalized)
    if currency is None:
        raise CurrencyNotFoundError(f"неизвестная валюта '{normalized}'")
    return currency
