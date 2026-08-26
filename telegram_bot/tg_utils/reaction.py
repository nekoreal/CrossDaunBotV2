import requests
from config import TELEGRAM_TOKEN

user={
    '874183602':"🔥",
    '670305019':"🎃",
    '1941380895':'😘'
}

status_emoji={
    "no":"💩",
    "yes":"💯",
    "wait":"🤔"
}

def send_react(chat_id, message_id, status:str="yes"):
    '''
     "no":"💩",
     "yes":"💯",
     "wait":"❓"'''
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMessageReaction'
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'reaction': [
            {
                'type': 'emoji',
                'emoji': status_emoji[status]
            }
        ],
        'is_big': False
    }
    response = requests.post(url, json=data)
    result = response.json()

def send_react_for_user(chat_id, message_id, user_id):
    try:
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reaction': [
                {
                    'type': 'emoji',
                    'emoji': user[f"{user_id}"]
                }
            ],
            'is_big': False
        }
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMessageReaction'
        response = requests.post(url, json=data)
        result = response.json()
    except:
        pass