import json
from datetime import datetime

from pika import ConnectionParameters, BlockingConnection
from config import CONNECTION_PARAMS
from utils.logger import logger


def queue_sender(
        queue:str = "tg_notify",
        body:dict|list|None = None,
        type_msg:str="None",
        msg_from:str="CrossDaunBotV2",
        *args,
        **kwargs
):
    """
    :param type_msg: 
    :param msg_from:
    :param queue:
    :param body: желательно dict сюда
    """
    data=json.dumps({
        "time": str(datetime.now()),
        "type": type_msg,
        "from": msg_from,
        "data": body,
        **kwargs,
    })
    with BlockingConnection(CONNECTION_PARAMS) as connection:
        with connection.channel() as channel:
            channel.queue_declare(queue=queue)
            channel.basic_publish(exchange='',
                                  routing_key=queue,
                                  body=data)