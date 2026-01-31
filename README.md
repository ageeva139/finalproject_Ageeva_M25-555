# ValutaTrade Hub

Консольная платформа для симуляции торговли валютами: регистрация пользователей, виртуальный портфель, покупка/продажа валют за USD, просмотр баланса и получение курсов

Курсы берутся из локального кэша (data/rates.json) с TTL и могут обновляться вручную через Parser Service (CoinGecko + ExchangeRate-API) 

## Идея проекта

Проект состоит из двух частей:

- **Core Service (CLI)** - основное приложение
  - хранит пользователей и портфели в JSON
  - выполняет команды: register/login/show-portfolio/buy/sell/get-rate/show-rates/update-rates
  - читает курсы из локального кэша data/rates.json

- **Parser Service** - обновляет курсы валют
  - CoinGecko для криптовалют (BTC/ETH/SOL и т.д.)
  - ExchangeRate-API для фиатных валют (USD/EUR/GBP/RUB и т.д.)
  - пишет:
    - data/rates.json - текущий снимок курсов (использует Core)
    - data/exchange_rates.json - история измерений (журнал)

## Структура проекта
```finalproject_Ageeva_M25-555/
├── data/
│ ├── users.json
│ ├── portfolios.json
│ ├── rates.json
│ └── exchange_rates.json
├── valutatrade_hub/
│ ├── cli/
│ │ └── interface.py
│ ├── core/
│ │ ├── currencies.py
│ │ ├── exceptions.py
│ │ ├── models.py
│ │ ├── usecases.py
│ │ └── utils.py
│ ├── infra/
│ │ ├── settings.py
│ │ └── database.py
│ ├── parser_service/
│ │ ├── api_clients.py
│ │ ├── config.py
│ │ ├── storage.py
│ │ └── updater.py
│ ├── decorators.py
│ └── logging_config.py
├── main.py
├── Makefile
├── pyproject.toml
└── README.md
```

# Установка и запуск

## Требования
Python 3.12 или выше

Poetry (менеджер зависимостей)

## Установка

### Клонируйте репозиторий

```bash
git clone https://github.com/ageeva139/finalproject_Ageeva_M25-555.git
cd finalproject_Ageeva_M25-555
```

### Установите зависимости

```bash
make install
# или
poetry install
```

## Запуск

```bash
make project
# или
poetry run project
```

# Доступные команды

`register --username <str> --password <str>` - зарегестрировать нового пользователя

`login --username <str> --password <str>` - войти в аккаунт

`show-portfolio [--base <code>]` - показать кошелек

`get-rate --from <code> --to <code>` - узнать курс

`update-rates [--source <coingecko|exchangerate>]` - обновить курсы

`show-rates [--currency <code>] [--top <n>] [--base <code>]` - показать курсы из кеша

`buy --currency <code> --amount <float>` - покупка валюты за USD

`sell --currency <code> --amount <float>` - продажа валюты в USD

`help` - список доступных команд

`exit` - выйти из программы

## Пример использования команд

1. Регистрация нового пользователя

`register --username alice --password 1234`

Возможные ошибки:
- имя занято
- пароль короче 4 символов

2. Войти в аккаунт пользователя

`login --username alice --password 1234`

Возможные ошибки:
- пользователь не найден
- неверный пароль

3. Показать кошелек и итоговую стоимоть в базовой валюте 

`show-portfolio`

`show-portfolio --base USD`

`show-portfolio --base EUR`

4. Купить валюту (списать USD и начислить выбранную)

`buy --currency BTC --amount 0.01`

`buy --currency EUR --amount 10`

Возможные ошибки:
- недостаточно средств для покупки

5. Продать валюту (списать выбранную и начислить USD)

`sell --currency BTC --amount 0.005`

Возможные ошибки:
- в кошельке нет выбранной валюты

6. Показать курс и время его обновления

`get-rate --from BTC --to USD`

`get-rate --from EUR --to USD`

7. Обновить курс вручную (с возможностью выбора)

`update-rates --source coingecko` (обновит только криптовалюту)

`update-rates --source exchangerate` (обновит фиатную валюту)

`update-rates` (обновит обе валюты)

8. Показать курсы из кэша

`show-rates`

`show-rates` --currency BTC

`show-rates` --top 2

`show-rates` --base EUR

# Кэш курсов и TTL

Кэш лежит в data/rates.json и имеет формат:
```json
{
  "pairs": {
    "BTC_USD": { "rate": 123.45, "updated_at": "...", "source": "..." }
  },
  "last_refresh": "..."
}
```

pairs - последние значения по каждой паре

last_refresh - время последнего обновления парсером

В Core Service используется TTL из настроек (RATES_TTL_SECONDS), чтобы понимать, не устарели ли данные

# Parser Service и ключ API

Для ExchangeRate-API нужен ключ. Он хранится в переменной окружения:

```bash
export EXCHANGERATE_API_KEY="ключ"
```

Parser Service вызывается через CLI команду:

```bash
update-rates
```

История измерений пишется в data/exchange_rates.json

# Логи

Операции buy/sell и обновления курсов логируются (уровень INFO).
Расположение и формат логов задаётся в настройках проект

# Демонстрация asciinema

https://asciinema.org/a/NxldkLSxUHFCBjwG