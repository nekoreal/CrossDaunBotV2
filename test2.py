import json
from collections import defaultdict

# Инициализируем defaultdict, где значением по умолчанию будет еще один словарь со счетчиками
users = defaultdict(lambda: {"text": 0, "photo": 0, "video": 0, "sticker": 0})

with open('parsed_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    
    for i in data:
        user_id = i.get('from_user')
        msg_type = i.get('type')
        
        # Проверяем, что данные есть и тип сообщения нам интересен
        if user_id and msg_type in users[user_id]:
            users[user_id][msg_type] += 1

sorted_users = sorted(users.items(), key=lambda item: item[1]['text'], reverse=True)

for user, stats in sorted_users:
    print(f"Пользователь {user}: {stats}")