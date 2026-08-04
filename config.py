from pika import ConnectionParameters, PlainCredentials
import os

rabbitmq_user = os.getenv("RABBITMQ_USER" )
rabbitmq_password = os.getenv("RABBITMQ_PASSWORD" )

credentials = PlainCredentials(rabbitmq_user, rabbitmq_password)
CONNECTION_PARAMS = ConnectionParameters(
    host='5.182.87.105',
    port=5672,
    virtual_host='/',
    credentials=credentials
)


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID=619593521153966101
DISCORD_CHANNEL_ID = 766736241960943653

INVITE_ROLE=1308902443974787112
BOT_USERNAME = 'CrossDaun#3072'


TELEGRAM_TOKEN = os.getenv("TELEGRAMM_TOKEN")
SQLALCHEMY_DATABASE_URI = os.getenv(
    "SQLALCHEMY_DATABASE_URI",
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@localhost:3306/{os.getenv('MYSQL_DATABASE')}"
)
TELEGRAM_CHAT_ID = -1001970834344

