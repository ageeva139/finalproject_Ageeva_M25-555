from datetime import datetime

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import User
from valutatrade_hub.core.utils import load_json, normalize_currency_code, save_json
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader


def get_rate(
    base_currency: str,
    quote_currency: str = "USD",
    max_age_seconds: int = 300,
) -> dict:
    """возвращает курс и время обновления используя кэш или заглушку"""
    settings = SettingsLoader()
    max_age_seconds = int(settings.get("RATES_TTL_SECONDS", max_age_seconds))

    base = normalize_currency_code(base_currency)
    quote = normalize_currency_code(quote_currency)
    
    #ключ для поиска в кэше
    key = f"{base}_{quote}"

    # читаем кэш курсов из файла
    rates = load_json("rates.json", {})
    #если файл случайно был не словарём, то начинаем с пустого
    if not isinstance(rates, dict):
        rates = {}

    #если курс уже есть в кэше, то просто возвращаем его
    cached = rates.get(key)
    if isinstance(cached, dict) and "rate" in cached and "updated_at" in cached:
        try:
            #превращаем iso формат обратно в datetime
            updated_at = datetime.fromisoformat(str(cached["updated_at"]))
            #считаем сколько секунд прошло с момента обновления
            age = (datetime.now() - updated_at).total_seconds()
            #если запись моложе max_age_seconds то используем её
            if age <= max_age_seconds:
                return {
                    "rate": float(cached["rate"]),
                    "updated_at": updated_at.replace(microsecond=0).isoformat(),
                }
        except Exception:
            #если дата в кэше сломана, то обновляем её
            pass

    #заглушка: сколько стоит 1 единица валюты в usd
    exchange_rates = {
        "USD": 1.0,
        "EUR": 1.0786,
        "BTC": 59337.21,
        "RUB": 0.01016,
        "ETH": 3720.00,
    }

    #если валюты нет в заглушке, то считаем что курс недоступен
    if base not in exchange_rates:
        raise CurrencyNotFoundError(base)
    if quote not in exchange_rates:
        raise CurrencyNotFoundError(quote)

    rate = exchange_rates[base] / exchange_rates[quote]

    #сохраняем курс в кэш с временем обновления
    now = datetime.now().replace(microsecond=0).isoformat()
    rates[key] = {"rate": rate, "updated_at": now}
    rates["source"] = "StubRates"
    rates["last_refresh"] = now
    try:
        save_json("rates.json", rates)
    except Exception as e:
        raise ApiRequestError(str(e))

    return {"rate": rate, "updated_at": now}


def now_iso() -> str:
    """возвращает текущее время в iso формате"""
    return datetime.now().replace(microsecond=0).isoformat()


def next_user_id(users: list) -> int:
    """возвращает следующий user_id"""
    max_id = 0
    for u in users:
        uid = u.get("user_id")
        if isinstance(uid, int) and uid > max_id:
            max_id = uid
    return max_id + 1


def username_exists(users: list, username: str) -> bool:
    """проверяет что username уже есть в списке"""
    for u in users:
        if u.get("username") == username:
            return True
    return False


def register_user(username: str, password: str) -> int:
    """регистрирует пользователя и возвращает его id"""
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username не может быть пустым")
    if not isinstance(password, str) or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    username = username.strip()

    users = load_json("users.json", [])
    #если файл случайно был не списком, то начинаем с пустого
    if not isinstance(users, list):
        users = []

    #проверка уникальности имени пользователя
    if username_exists(users, username):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = next_user_id(users)

    user = User(user_id, username, "", "", now_iso())
    user.change_password(password)

    #сохраняем пользователя
    users.append(
        {
            "user_id": user_id,
            "username": username,
            "hashed_password": user.get_hashed_password(),
            "salt": user.get_salt(),
            "registration_date": user.get_registration_date().isoformat(),
        }
    )
    save_json("users.json", users)

    #создаем пустой портфель
    portfolios = load_json("portfolios.json", [])
    if not isinstance(portfolios, list):
        portfolios = []

    portfolios.append({"user_id": user_id, "wallets": {}})
    save_json("portfolios.json", portfolios)

    return user_id

def find_user_by_username(users: list, username: str):
    """ищет пользователя по имени"""
    for u in users:
        if u.get("username") == username:
            return u
    return None

def login_user(username: str, password: str) -> User:
    """проверяет логин и пароль и возвращает объект user"""
    #проверяем правильность строк
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username не может быть пустым")
    if not isinstance(password, str):
        raise ValueError("password должен быть строкой")

    username = username.strip()

    users = load_json("users.json", [])
    if not isinstance(users, list):
        users = []

    #ищем пользователя по имени
    data = find_user_by_username(users, username)
    if data is None:
        raise ValueError(f"Пользователь '{username}' не найден")

    #собираем объект user, чтобы проверить пароль
    user = User(
        data["user_id"],
        data["username"],
        data.get("hashed_password", ""),
        data.get("salt", ""),
        data.get("registration_date", datetime.now().isoformat()),
    )

    #сравниваем хеши пароля
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")

    return user


def load_portfolio_wallets(user_id: int) -> dict:
    """загружает кошельки пользователя"""
    portfolios = load_json("portfolios.json", [])
    if not isinstance(portfolios, list):
        portfolios = []

    #ищем кошелек по user_id
    for p in portfolios:
        if p.get("user_id") == user_id:
            wallets = p.get("wallets", {})
            #сохраняем, если кошелек - словарь
            return wallets if isinstance(wallets, dict) else {}

    portfolios.append({"user_id": user_id, "wallets": {}})
    save_json("portfolios.json", portfolios)
    return {}


def show_portfolio(user: User, base_currency: str = "USD") -> dict:
    """готовит данные портфеля для вывода на экран"""
    base = normalize_currency_code(base_currency)

    #проверяем что базовая валюта поддерживается
    if base != "USD":
        try:
            get_rate(base, "USD")
        except Exception:
            raise ValueError(f"Неизвестная базовая валюта '{base}'")

    wallets = load_portfolio_wallets(user.get_user_id())
    items = []
    total = 0.0

    #считаем стоимость каждого кошелька
    for code, data in wallets.items():
        code = normalize_currency_code(code)
        balance = float(data.get("balance", 0.0))
        rate = 1.0 if code == base else float(get_rate(code, base)["rate"])
        value_in_base = balance * rate
        items.append((code, balance, value_in_base))
        total += value_in_base

    #сортируем для стабильного вывода
    items.sort(key=lambda x: x[0])

    return {
        "username": user.get_username(),
        "base": base,
        "items": items,
        "total": total,
    }


def save_portfolio(user_id: int, wallets: dict) -> None:
    """сохраняет кошелек пользователя"""
    portfolios = load_json("portfolios.json", [])
    if not isinstance(portfolios, list):
        portfolios = []

    #ищем кошелек по user_id
    for p in portfolios:
        if p.get("user_id") == user_id:
            p["wallets"] = wallets
            save_json("portfolios.json", portfolios)
            return

    #если кошелька нет, создаём пустой и сохраняем
    portfolios.append({"user_id": user_id, "wallets": wallets})
    save_json("portfolios.json", portfolios)


def get_wallet_balance(wallets: dict, code: str) -> float:
    """возвращает баланс кошелька или 0 если его нет"""
    data = wallets.get(code)
    if isinstance(data, dict):
        return float(data.get("balance", 0.0))
    return 0.0


def set_wallet_balance(wallets: dict, code: str, balance: float) -> None:
    """устанавливает баланс кошелька создавая его если нужно"""
    if code not in wallets or not isinstance(wallets.get(code), dict):
        wallets[code] = {"balance": 0.0}
    wallets[code]["balance"] = float(balance)


@log_action("BUY", verbose=True) #декоратор
def buy(user: User, currency_code: str, amount) -> dict:
    """покупает валюту за usd и возвращает данные для вывода"""
    code = normalize_currency_code(currency_code)

    #приводим amount к числовому типу
    if isinstance(amount, bool):
        raise ValueError("'amount' должен быть положительным числом")
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
    except Exception:
        raise ValueError("'amount' должен быть положительным числом")

    #получаем курс
    try:
        rate_info = get_rate(code, "USD")
        rate = float(rate_info["rate"])
    except Exception:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    wallets = load_portfolio_wallets(user.get_user_id())

    usd_balance_before = get_wallet_balance(wallets, "USD")
    code_balance_before = get_wallet_balance(wallets, code)

    cost_usd = amount * rate
    if usd_balance_before < cost_usd:
        raise InsufficientFundsError(usd_balance_before, cost_usd, "USD")

    usd_balance_after = usd_balance_before - cost_usd
    code_balance_after = code_balance_before + amount

    #обновляем баланс обеих валют и сохраняем
    set_wallet_balance(wallets, "USD", usd_balance_after)
    set_wallet_balance(wallets, code, code_balance_after)
    save_portfolio(user.get_user_id(), wallets)

    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "cost_usd": cost_usd,
        "before": code_balance_before,
        "after": code_balance_after,
    }

@log_action("SELL", verbose=True) #декоратор
def sell(user: User, currency_code: str, amount) -> dict:
    """продаёт валюту в usd и возвращает данные для вывода"""
    code = normalize_currency_code(currency_code)

    #приводим amount к числовому типу
    if isinstance(amount, bool):
        raise ValueError("'amount' должен быть положительным числом")
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
    except Exception:
        raise ValueError("'amount' должен быть положительным числом")

    #получаем курс
    try:
        rate_info = get_rate(code, "USD")
        rate = float(rate_info["rate"])
    except Exception:
        raise ValueError(f"Не удалось получить курс для {code}→USD")

    wallets = load_portfolio_wallets(user.get_user_id())

    if code not in wallets:
        raise ValueError(f"У вас нет кошелька '{code}'."
             "Добавьте валюту: она создаётся автоматически при первой покупке")

    #проверяем баланс
    code_balance_before = get_wallet_balance(wallets, code)
    if code_balance_before < amount:
        raise InsufficientFundsError(code_balance_before, amount, code)


    usd_balance_before = get_wallet_balance(wallets, "USD")

    revenue_usd = amount * rate
    code_balance_after = code_balance_before - amount
    usd_balance_after = usd_balance_before + revenue_usd

    #обновляем баланс обеих валют и сохраняем
    set_wallet_balance(wallets, code, code_balance_after)
    set_wallet_balance(wallets, "USD", usd_balance_after)
    save_portfolio(user.get_user_id(), wallets)

    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "revenue_usd": revenue_usd,
        "before": code_balance_before,
        "after": code_balance_after,
    }
