from pika import ConnectionParameters, BlockingConnection
from config import CONNECTION_PARAMS
from utils.logger import logger


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def queue_sender(
        queue:str = "tg_notify",
        body="Empty"
):
    """
    :param queue:
    :param body: желательно джэйсона сюда
    """
    with BlockingConnection(CONNECTION_PARAMS) as connection:
        with connection.channel() as channel:
            channel.queue_declare(queue=queue)
            channel.basic_publish(exchange='',
                                  routing_key=queue,
                                  body=body)