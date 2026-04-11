from pika import ConnectionParameters, BlockingConnection
from config import CONNECTION_PARAMS


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