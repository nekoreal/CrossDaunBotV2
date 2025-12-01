import requests
from io import BytesIO
from config import TELEGRAM_TOKEN
from utils.logger import logger

@logger(
    txtfile="telegram_bot.log",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def get_user_avatar( telegram_bot,user_id):
    """
    Получение аватара пользователя Telegram в виде BytesIO (если есть)
    """
    try:
        photos = telegram_bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos:
            photo = photos.photos[0][0]  # самый большой размер фото
            file_info = telegram_bot.get_file(photo.file_id)
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
            response = requests.get(file_url)
            if response.status_code == 200:
                return BytesIO(response.content)
    except Exception as e:
        print(f"Ошибка при получении аватара: {e}")
    return None