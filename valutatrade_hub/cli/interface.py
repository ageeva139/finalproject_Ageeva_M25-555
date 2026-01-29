#!/usr/bin/env python3

from valutatrade_hub.core import usecases


def _parse_args(parts: list) -> dict:
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
    print("get-rate --base <code> [--quote <code>] - узнать курс")
    print("help - список доступных команд")
    print("exit - выйти из программы")


def format_number(value: float, decimals: int = 2) -> str:
    """форматирует число для вывода"""
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
                args = _parse_args(parts[1:])
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
                args = _parse_args(parts[1:])
                username = args.get("username")
                password = args.get("password")
                if username is None or password is None:
                    print("нужно ввести имя и пароль, например:",
                          "login --username alice --password 1234")
                    continue

                current_user = usecases.login_user(username, password)
                print(f"Вы вошли как '{current_user.get_username()}'")

            elif cmd == "get-rate": #узнать курс обмена
                args = _parse_args(parts[1:])
                base = args.get("base")
                quote = args.get("quote", "USD")
                if base is None:
                    print("нужно указать валюту, например:",
                          "get-rate --base EUR --quote USD")
                    continue
                rate = usecases.get_rate(base, quote)
                print(rate)

            elif cmd == "show-portfolio": #показать кошелек
                if current_user is None:
                    print("Сначала выполните login")
                    continue

                args = _parse_args(parts[1:])
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
                    bal_s = format_number(bal, 4 if code in ("BTC", "ETH") else 2)
                    val_s = format_number(val, 2)
                    print(f"- {code}: {bal_s}  → {val_s} {base}")

                print("--"*10)
                print(f"ИТОГО: {format_number(total, 2)} {base}")


            else: #неизвестная кмоанда
                print("Неизвестная команда")
                print_help()

        except Exception as e: #ловим ошибки
            print(str(e))
            print_help()
