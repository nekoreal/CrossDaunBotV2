from functools import wraps
from typing import Callable
from datetime import datetime
import asyncio

def logger(
    txtfile: str = "log.txt",
    print_log: bool = False,
    time_log: bool = False,
    raise_exc: bool = True,
    only_exc: bool = True,
):
    def wrapper(func: Callable) -> Callable:
        @wraps(func)
        async def async_inner(*args, **kwargs):
            res, exc = None, None
            try:
                res = await func(*args, **kwargs)
            except Exception as e:
                exc = e
            if (not only_exc) or exc:
                log = (
                    f"{datetime.now() if time_log else ''} "
                    f"\nfunc:{func.__name__}->{res}"
                    f"\nargs:{args} kwargs:{kwargs}"
                    f"{f'\n\nexc{exc}\n' if exc else ''}"
                )
                if print_log:
                    print(log)
                # Можно сделать асинхронную запись, но для простоты — обычная запись
                with open(txtfile, "a") as f:
                    f.write(log)
                if raise_exc and exc:
                    raise exc
            return res

        @wraps(func)
        def sync_inner(*args, **kwargs):
            res, exc = None, None
            try:
                res = func(*args, **kwargs)
            except Exception as e:
                exc = e
            if (not only_exc) or exc:
                log = (
                    f"{datetime.now() if time_log else ''} "
                    f"\nfunc:{func.__name__}->{res}"
                    f"\nargs:{args} kwargs:{kwargs}"
                    f"{f'\n\nexc{exc}\n' if exc else ''}"
                )
                if print_log:
                    print(log)
                with open(txtfile, "a") as f:
                    f.write(log)
                if raise_exc and exc:
                    raise exc
            return res
        if asyncio.iscoroutinefunction(func):
            return async_inner
        else:
            return sync_inner

    return wrapper

def make_log(
        txtfile: str = "log.txt",
        text:str= "Empty Log",
        print_log: bool = False,
        time_log: bool = True,
):
    log = (
        f"{datetime.now() if time_log else ''}"
        f"{text}"
    )
    if print_log:
        print(log)
    with open(txtfile, "a") as f:
        f.write(log)