#!/usr/bin/env python3

from datetime import datetime

from valutatrade_hub.core import usecases


def parse_args(parts: list) -> dict:
    """превращает список аргументов вида --key value в словарь"""
    args = {}
    i = 0
    while i < len(parts):
        if parts[i].startswith("--"):
            key = parts[i][2:]
            if i + 1 >= len(parts):
                raise ValueError(f"нет значения для --{key}")
            args[key] = parts[i + 1]
            i += 2
        else:
            i += 1
    return args

def print_help() -> None:
    """печатает список команд"""
    print("Доступные команды:")
    print("register --username <str> --password <str>", 
          "- зарегестрировать нового пользователя" )
    print("login --username <str> --password <str> - войти в аккаунт")
    print("show-portfolio [--base <code>] - показать кошелек")
    print("get-rate --from <code> --to <code> - узнать курс")
    print("buy --currency <code> --amount <float> - покупка валюты за USD")
    print("sell --currency <code> --amount <float> - продажа валюты в USD")
    print("help - список доступных команд")
    print("exit - выйти из программы")


def format_number(value: float, decimals: int = 2, code: str = "") -> str:
    """форматирует число для вывода"""
    if code in ("BTC", "ETH"):
        decimals = 4
    return f"{value:,.{decimals}f}"


def main() -> None:
    print("Добро пожаловать на платформу")
    print_help()
    current_user = None

    while True:
        command = input("Введите команду: ").strip()
        if not command:
            continue

        parts = command.split()
        cmd = parts[0]

        try:
            if cmd == "help": #список команд
                print_help()

            elif cmd == "exit": #выйти из программы
                break

            elif cmd == "register": #зарегестрировать нового пользователя
                args = parse_args(parts[1:])
                username = args.get("username")
                password = args.get("password")
                if username is None or password is None:
                    print("нужно придумать имя и пароль (минимум 4 символа), например:",
                          "register --username alice --password 1234")
                    continue

                #создаём пользователя и сохраняем его в users.json
                user_id = usecases.register_user(username, password)
                print(
                    f"Пользователь '{username}' зарегистрирован (id={user_id}). "
                    f"Войдите: login --username {username} --password ****"
                )

            elif cmd == "login": #войти в аккаунт пользователя
                args = parse_args(parts[1:])
                username = args.get("username")
                password = args.get("password")
                if username is None or password is None:
                    print("нужно ввести имя и пароль, например:",
                          "login --username alice --password 1234")
                    continue

                current_user = usecases.login_user(username, password)
                print(f"Вы вошли как '{current_user.get_username()}'")

            elif cmd == "get-rate": #узнать курс обмена
                args = parse_args(parts[1:])
                base = args.get("from")
                quote = args.get("to")
                if base is None:
                    print("нужно указать валюту, например:",
                          "get-rate --from EUR --to USD")
                    continue
                info = usecases.get_rate(base, quote)
                rate = float(info["rate"])
                updated_at = str(info["updated_at"])
                ts = datetime.fromisoformat(updated_at).strftime("%Y-%m-%d %H:%M:%S")

                base_u = base.strip().upper()
                quote_u = quote.strip().upper()

                print(f"Курс {base_u}→{quote_u}: {format_number(rate, 8)}",
                     f"(обновлено: {ts})")

                if rate != 0:
                    reverse = 1 / rate
                    print(
                        f"Обратный курс {quote_u}→{base_u}: {format_number(reverse, 2)}"
                        )

            elif cmd == "show-portfolio": #показать кошелек
                if current_user is None:
                    print("Сначала выполните login")
                    continue

                args = parse_args(parts[1:])
                base = args.get("base", "USD")

                data = usecases.show_portfolio(current_user, base)
                username = data["username"]
                base = data["base"]
                items = data["items"]
                total = data["total"]

                print(f"Портфель пользователя '{username}' (база: {base}):")
                
                #если кошельков нет, выводим сообщение об этом
                if not items:
                    print("кошельков нет")
                    continue

                #выводим каждый кошелёк и его стоимость в базовой валюте
                for code, bal, val in items:
                    bal_s = format_number(bal, code=code)
                    val_s = format_number(val, 2)
                    print(f"- {code}: {bal_s}  → {val_s} {base}")

                print("--"*10)
                print(f"ИТОГО: {format_number(total, 2)} {base}")

            elif cmd == "buy": #покупка валюты за USD
                if current_user is None:
                    print("Сначала выполните login")
                    continue

                args = parse_args(parts[1:])
                currency = args.get("currency")
                amount = args.get("amount")

                if currency is None or amount is None:
                    print("нужно указать валюту и количество, например:",
                          "buy --currency BTC --amount 0.05")
                    continue

                info = usecases.buy(current_user, currency, amount)

                code = info["currency"]
                amt = info["amount"]
                rate = info["rate"]
                before = info["before"]
                after = info["after"]
                cost = info["cost_usd"]

                print(f"Покупка выполнена: {format_number(amt, code=code)} {code} "
                    f"по курсу {format_number(rate, 2)} USD/{code}")
                print("Изменения в портфеле:")
                print(f"- {code}: было {format_number(before, code=code)} → "
                    f"стало {format_number(after, code=code)}")
                print(f"Оценочная стоимость покупки: {format_number(cost, 2)} USD")

            elif cmd == "sell": #проджа валюты в USD
                if current_user is None:
                    print("Сначала выполните login")
                    continue

                args = parse_args(parts[1:])
                currency = args.get("currency")
                amount = args.get("amount")

                if currency is None or amount is None:
                    print("нужно указать валюту и количество, например:",
                          "sell --currency BTC --amount 0.01")
                    continue

                info = usecases.sell(current_user, currency, amount)

                code = info["currency"]
                amt = info["amount"]
                rate = info["rate"]
                before = info["before"]
                after = info["after"]
                revenue = info["revenue_usd"]

                print(f"Продажа выполнена: {format_number(amt, code=code)} {code} "
                    f"по курсу {format_number(rate, 2)} USD/{code}")
                print("Изменения в портфеле:")
                print(f"- {code}: было {format_number(before, code=code)} → "
                    f"стало {format_number(after, code=code)}")
                print(f"Оценочная выручка: {format_number(revenue, 2)} USD")

            else: #неизвестная кмоанда
                print("Неизвестная команда")
                print_help()

        except Exception as e: #ловим ошибки
            print(str(e))
