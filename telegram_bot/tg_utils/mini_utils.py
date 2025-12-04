import threading
import re


def run_in_thread(target_func, *args, **kwargs):
    """
    Запускает функцию target_func в отдельном потоке.
    Аргументы *args и **kwargs передаются в функцию.
    """
    thread = threading.Thread(target=target_func, args=args, kwargs=kwargs)
    thread.start()
    return thread

def escape_markdown(text):
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)