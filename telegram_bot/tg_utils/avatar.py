import requests
from io import BytesIO
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import logger
import telebot
from PIL import Image 

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def get_user_avatar( 
    telegram_bot,
    user_id 
):
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

def get_and_resize_chat_photo(
        telegram_bot,
        chat_id=TELEGRAM_CHAT_ID,
        x=64,
        y=64,
):
    try: 
        chat = telegram_bot.get_chat(chat_id)
        
        if not chat.photo:
            print("У чата нет аватарки.")
            return False
 
        file_id = chat.photo.small_file_id
        file_info = telegram_bot.get_file(file_id)
         
        downloaded_file = telegram_bot.download_file(file_info.file_path)
        image_stream = BytesIO(downloaded_file)
         
        with Image.open(image_stream) as img: 
            resized_img = img.resize((64, 64), Image.Resampling.LANCZOS)
             
            resized_img.save("static/chat_icon_64.png") 
            return True

    except Exception as e:
        print(f"Ошибка: {e}")
        return False