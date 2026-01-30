from datetime import datetime
from functools import wraps
from typing import Any, Callable

from valutatrade_hub.logging_config import setup_logging


def fmt(v):
    """для красивых чисел в логе"""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:.8f}".rstrip("0").rstrip(".")
    return v


def log_action(action: str, verbose: bool = False) -> Callable:
    """логирует доменную операцию и пробрасывает исключения"""
    #настраиваем логгер
    logger = setup_logging()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            #timestamp в iso формате
            ts = datetime.now().replace(microsecond=0).isoformat()

            user = args[0] if args else None
            username = None
            user_id = None
            if user is not None:
                if hasattr(user, "get_username"):
                    username = user.get_username()
                if hasattr(user, "get_user_id"):
                    user_id = user.get_user_id()

            currency_code = args[1] if len(args) > 1 else kwargs.get("currency_code")
            amount = args[2] if len(args) > 2 else kwargs.get("amount")

            try:
                #вызываем исходную функцию
                result = func(*args, **kwargs)

                #если функция вернула dict, берем данные для лога
                code = None
                amt = None
                rate = None
                base = "USD"

                if isinstance(result, dict):
                    code = result.get("currency")
                    amt = result.get("amount")
                    rate = result.get("rate")
                    if "base" in result:
                        base = result.get("base")

                #сообщение об успехе
                msg = (
                    f"{ts} {action} "
                    f"user='{username}' user_id={user_id} "
                    f"currency='{code or currency_code}' amount={amt or amount} "
                    f"rate={rate} base='{base}' result=OK"
                )

                if verbose and isinstance(result, dict):
                    if "before" in result and "after" in result:
                        msg += (f" before={fmt(result.get('before'))}"
                            f" after={fmt(result.get('after'))}")
                    if "cost_usd" in result:
                        msg += f" cost_usd={fmt(result.get('cost_usd'))}"
                    if "revenue_usd" in result:
                        msg += f" revenue_usd={fmt(result.get('revenue_usd'))}"

                logger.info(msg)
                return result

            except Exception as e:
                #логируем ошибку
                msg = (
                    f"{ts} {action} "
                    f"user='{username}' user_id={user_id} "
                    f"currency='{currency_code}' amount={amount} "
                    f"result=ERROR error_type={type(e).__name__} error_message={e}"
                )
                logger.info(msg)
                raise

        return wrapper

    return decorator
