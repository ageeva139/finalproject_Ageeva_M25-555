from datetime import datetime

from valutatrade_hub.core.models import User
from valutatrade_hub.core.utils import load_json, normalize_currency_code, save_json


def get_rate(base_currency: str, quote_currency: str = "USD") -> float:
    """возвращает курс используя кеш или заглушку"""
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
    if key in rates and isinstance(rates[key], dict) and "rate" in rates[key]:
        return float(rates[key]["rate"])

    #заглушка: сколько стоит 1 единица валюты в usd
    exchange_rates = {
        "USD": 1.0,
        "EUR": 1.0786,
        "BTC": 59337.21,
        "RUB": 0.01016,
        "ETH": 3720.00,
    }

    if base not in exchange_rates:
        raise ValueError(f"Нет курса для базовой валюты: {base}")
    if quote not in exchange_rates:
        raise ValueError(f"Нет курса для котируемой валюты: {quote}")

    rate = exchange_rates[base] / exchange_rates[quote]

    #сохраняем курс в кеш с временем обновления
    now = datetime.now().replace(microsecond=0).isoformat()
    rates[key] = {"rate": rate, "updated_at": now}
    rates["source"] = "StubRates"
    rates["last_refresh"] = now
    save_json("rates.json", rates)

    return rate


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

    for p in portfolios:
        if p.get("user_id") == user_id:
            wallets = p.get("wallets", {})
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
        rate = 1.0 if code == base else get_rate(code, base)
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
