import threading
import re
from functools import wraps
from time import sleep
from typing import Callable

def sleep_func(time_sleep:int=15) -> Callable:
    def wrapper(func:Callable) -> Callable:
        @wraps(func)
        def inner(*args, **kwargs):
            sleep(time_sleep)
            return func(*args, **kwargs)
        return inner
    return wrapper



def run_in_thread(target_func, *args, time_sleep:int=None, **kwargs):
    """
    Запускает функцию target_func в отдельном потоке.
    Аргументы *args и **kwargs передаются в функцию.
    """
    if time_sleep:
        target_func = sleep_func(time_sleep)(target_func)
    thread = threading.Thread(target=target_func, args=args, kwargs=kwargs)
    thread.start()
    return thread

def escape_markdown(text):
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)