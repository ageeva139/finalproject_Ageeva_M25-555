import hashlib
import secrets
from datetime import datetime


class User:
    """пользователь системы
    хранит идентификатор, имя, хеш пароля, соль и дату регистрации
    пароль хранится только в виде хеша
    """

    def __init__(self, user_id, username, hashed_password, salt, registration_date):
        """создаёт пользователя
        registration_date может быть datetime или строкой ISO
        """
        self.set_user_id(user_id)
        self.set_username(username)
        self._hashed_password = hashed_password
        self._salt = salt
        self.set_registration_date(registration_date)

    def _hash(self, password, salt):
        """возвращает sha256-хеш для password + salt."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def get_user_id(self):
        """возвращает айди пользователя"""
        return self._user_id

    def set_user_id(self, value):
        """устанавливает айди пользователя"""
        if not isinstance(value, int) or value <= 0:
            raise ValueError("user_id должен быть положительным целым числом")
        self._user_id = value

    def get_username(self):
        """возвращает имя пользователя"""
        return self._username

    def set_username(self, value):
        """устанавливает имя пользователя"""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    def get_hashed_password(self):
        """возвращает хэш пароля"""
        return self._hashed_password

    def get_salt(self):
        """возвращает соль"""
        return self._salt

    def get_registration_date(self):
        """возвращает дату регистрации"""
        return self._registration_date

    def set_registration_date(self, value):
        """устанавливает дату регистрации"""
        if isinstance(value, datetime):
            self._registration_date = value
        elif isinstance(value, str):
            self._registration_date = datetime.fromisoformat(value)
        else:
            raise ValueError("registration_date должен быть datetime или ISO-строкой")

    def get_user_info(self):
        """возвращает информацию о пользователе без пароля"""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password):
        """меняет пароль"""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        if not self._salt:
            self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash(new_password, self._salt)

    def verify_password(self, password):
        """проверяет, совпадает ли введённый пароль с сохранённым хешем"""
        if not isinstance(password, str):
            return False
        return self._hash(password, self._salt) == self._hashed_password


class Wallet:
    """кошелёк для одной валюты с балансом и базовыми операциями"""

    def __init__(self, currency_code: str, balance: float = 0.0):
        """создаёт кошелёк с кодом валюты и начальным балансом"""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("currency_code не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self._balance = 0.0
        self.balance = balance

    def _check_amount(self, amount: float) -> None:
        """проверяет, что amount это число и оно больше нуля"""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("amount должен быть числом")
        if amount <= 0:
            raise ValueError("amount должен быть больше нуля")

    @property
    def balance(self) -> float:
        """возвращает текущий баланс"""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """устанавливает баланс, запрещает отрицательные значения и неверные типы"""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("balance должен быть числом")
        if value < 0:
            raise ValueError("balance не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """пополняет баланс на суммму"""
        self._check_amount(amount)
        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        """снимает сумму, если хватает средств"""
        self._check_amount(amount)
        if amount > self._balance:
            raise ValueError("недостаточно средств")
        self._balance -= float(amount)

    def get_balance_info(self) -> dict:
        """возвращает информацию о валюте и текущем балансе"""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """портфель пользователя с набором кошельков"""

    def __init__(self, user, wallets=None):
        """создаёт портфель для user и словаря кошельков"""
        self._user = user
        self._user_id = user.get_user_id()
        self._wallets = {}

        if wallets:
            for code, wallet in wallets.items():
                self._wallets[code.upper()] = wallet

    @property
    def user(self):
        """возвращает объект пользователя"""
        return self._user

    @property
    def wallets(self):
        """возвращает копию словаря кошельков"""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> None:
        """добавляет кошелёк для currency_code если его ещё нет"""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("currency_code не может быть пустым")
        code = currency_code.strip().upper()
        if code in self._wallets:
            raise ValueError("такая валюта уже есть в портфеле")
        self._wallets[code] = Wallet(code)

    def get_wallet(self, currency_code: str):
        """возвращает кошелёк по коду валюты"""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("currency_code не может быть пустым")
        code = currency_code.strip().upper()
        if code not in self._wallets:
            raise ValueError("кошелёк для этой валюты не найден")
        return self._wallets[code]

    def get_total_value(self, base_currency: str = "USD") -> float:
        """считает общую стоимость портфеля в base_currency по фиктивным курсам"""
        base = base_currency.strip().upper()

        #фиктивные курсы: сколько стоит 1 единица валюты в usd
        exchange_rates = {
            "USD": 1.0,
            "EUR": 1.1,
            "BTC": 40000.0,
        }

        if base not in exchange_rates:
            raise ValueError("нет курса для base_currency")

        total_usd = 0.0
        for code, wallet in self._wallets.items():
            if code not in exchange_rates:
                continue
            total_usd += wallet.balance * exchange_rates[code]

        return total_usd / exchange_rates[base]
