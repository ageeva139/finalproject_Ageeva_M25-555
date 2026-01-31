from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
)
from valutatrade_hub.core.models import User, Wallet
from valutatrade_hub.core.utils import load_json, normalize_currency_code, save_json
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.parser_service import refresh_rates_cache
from valutatrade_hub.infra.settings import SettingsLoader


def safe_load_json(filename: str, default):
    """читает json и при проблемах возвращает понятную ошибку"""
    try:
        return load_json(filename, default)
    except Exception as e:
        raise ApiRequestError(str(e))


def safe_save_json(filename: str, data) -> None:
    """записывает json и при проблемах возвращает понятную ошибку"""
    try:
        save_json(filename, data)
    except Exception as e:
        raise ApiRequestError(str(e))


def get_rate(
    base_currency: str,
    quote_currency: str = "USD",
    max_age_seconds: int = 300,
) -> dict:
    """возвращает курс и время обновления используя кэш или заглушку"""
    settings = SettingsLoader()
    max_age_seconds = int(settings.get("RATES_TTL_SECONDS", max_age_seconds))

    base = get_currency(base_currency).code
    quote = get_currency(quote_currency).code
    
    #ключ для поиска в кэше
    key = f"{base}_{quote}"

    #читаем кэш курсов из файла
    rates = safe_load_json("rates.json", {})
    #если файл случайно был не словарём, то начинаем с пустого
    if not isinstance(rates, dict):
        rates = {}

    pairs = rates.get("pairs")
    if not isinstance(pairs, dict):
        pairs = rates

    cached = pairs.get(key)
    if isinstance(cached, dict) and "rate" in cached and "updated_at" in cached:
        try:
            ts = str(cached["updated_at"]).replace("Z", "+00:00")
            updated_at = datetime.fromisoformat(ts)

            now_dt = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
            age = (now_dt - updated_at).total_seconds()

            if age <= max_age_seconds:
                return {
                    "rate": float(cached["rate"]),
                    "updated_at": str(cached["updated_at"]),
                    "source": str(cached.get("source", "")),
                }
        except Exception:
            pass

    if isinstance(cached, dict) and "updated_at" in cached:
        raise ApiRequestError(
            f"Данные по курсу {base}→{quote} устарели, выполните update-rates"
        )

    raise ApiRequestError(f"Курс {base}→{quote} недоступен, выполните update-rates")


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
    portfolios = safe_load_json("portfolios.json", [])
    if not isinstance(portfolios, list):
        portfolios = []

    #ищем кошелек по user_id
    for p in portfolios:
        if p.get("user_id") == user_id:
            wallets = p.get("wallets", {})
            #сохраняем, если кошелек - словарь
            return wallets if isinstance(wallets, dict) else {}

    portfolios.append({"user_id": user_id, "wallets": {}})
    safe_save_json("portfolios.json", portfolios)
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
    portfolios = safe_load_json("portfolios.json", [])
    if not isinstance(portfolios, list):
        portfolios = []

    #ищем кошелек по user_id
    for p in portfolios:
        if p.get("user_id") == user_id:
            p["wallets"] = wallets
            safe_save_json("portfolios.json", portfolios)
            return

    #если кошелька нет, создаём пустой и сохраняем
    portfolios.append({"user_id": user_id, "wallets": wallets})
    safe_save_json("portfolios.json", portfolios)


def load_wallet(wallets: dict, code: str) -> Wallet:
    """создаёт объект Wallet из словаря""" #для упрощения buy и sell
    balance = get_wallet_balance(wallets, code)
    return Wallet(code, balance)


def save_wallet(wallets: dict, wallet: Wallet) -> None:
    """сохраняет объект Wallet в словарь""" #для упрощения buy и sell
    wallets[wallet.currency_code] = {"balance": float(wallet.balance)}


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
    code = get_currency(currency_code).code

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
        raise ApiRequestError(f"Не удалось получить курс для {code}→USD")

    wallets = load_portfolio_wallets(user.get_user_id())

    usd_wallet = load_wallet(wallets, "USD")
    code_wallet = load_wallet(wallets, code)

    code_balance_before = float(code_wallet.balance)

    cost_usd = amount * rate

    usd_wallet.withdraw(cost_usd)
    code_wallet.deposit(amount)
    
    #обновляем баланс обеих валют и сохраняем
    save_wallet(wallets, usd_wallet)
    save_wallet(wallets, code_wallet)
    save_portfolio(user.get_user_id(), wallets)

    code_balance_after = float(code_wallet.balance)


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
    code = get_currency(currency_code).code

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
        raise ApiRequestError(f"Не удалось получить курс для {code}→USD")

    wallets = load_portfolio_wallets(user.get_user_id())

    if code not in wallets:
        raise ValueError(f"У вас нет кошелька '{code}'. "
             "Добавьте валюту: она создаётся автоматически при первой покупке")

    #проверяем баланс
    code_wallet = load_wallet(wallets, code)
    usd_wallet = load_wallet(wallets, "USD")

    code_balance_before = float(code_wallet.balance)

    revenue_usd = amount * rate

    code_wallet.withdraw(amount)
    usd_wallet.deposit(revenue_usd)

    #обновляем баланс обеих валют и сохраняем
    save_wallet(wallets, code_wallet)
    save_wallet(wallets, usd_wallet)
    save_portfolio(user.get_user_id(), wallets)

    code_balance_after = float(code_wallet.balance)


    return {
        "currency": code,
        "amount": amount,
        "rate": rate,
        "revenue_usd": revenue_usd,
        "before": code_balance_before,
        "after": code_balance_after,
    }
