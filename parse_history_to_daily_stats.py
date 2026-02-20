"""
ПАРСЕР ИСТОРИИ СООБЩЕНИЙ
Импортирует данные из parsed_history.json в DailyStatistic
"""

import json
import sys
from datetime import datetime
from sqlalchemy import func
from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.daily_statistic import DailyStatistic
# Импортируем все остальные модели для регистрации в Base.metadata
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.models.tg_at_user_tag import UserTagAssociation

# Устанавливаем кодировку для вывода
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def parse_and_import_history(json_file_path='parsed_history.json', batch_size=1000):
    """
    Парсит JSON файл с историей сообщений и добавляет в DailyStatistic
    
    :param json_file_path: Путь к файлу
    :param batch_size: Сколько записей обрабатывать за раз (для оптимизации)
    """
    
    print(f"[FILE] Reading {json_file_path}...")
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        messages = json.load(f)
    
    print(f"[OK] Loaded {len(messages)} messages")
    print(f"[PROCESS] Starting import to DB...\n")
    
    # Группируем сообщения по (user_id, дата)
    stats_data = {}  # { (telegram_user_id, date): {counts} }
    user_ids = set()  # Для проверки существования пользователей
    
    # Этап 1: Группируем по дням и пользователям
    print("[STEP 1] Grouping data...")
    for i, msg in enumerate(messages):
        if i % 100000 == 0:
            print(f"   Processed {i}/{len(messages)}...")
        
        try:
            from_user = msg.get('from_user', '')
            
            # Пропускаем сообщения от каналов (channel123456)
            if not from_user or from_user.startswith('channel'):
                continue
            
            tg_user_id = int(from_user)
            msg_type = msg.get('type', 'text')
            msg_text = msg.get('text', '')
            date_str = msg.get('date', '')
            
            # Парсим дату
            msg_date = datetime.fromisoformat(date_str).date()
            
            # Определяем тип контента
            if msg_type in ['text', 'poll']:
                # Проверяем, это ли nya (сообщение начинается с /nya)
                if msg_text.startswith('/nya'):
                    stat_type = 'nya'
                else:
                    stat_type = 'text'
            else:
                stat_type = msg_type  # photo, video, sticker и т.д.
            
            # Ключ для группировки
            key = (tg_user_id, msg_date)
            
            if key not in stats_data:
                stats_data[key] = {
                    'tg_id': tg_user_id,
                    'date': msg_date,
                    'msg_count': 0,
                    'photo_count': 0,
                    'video_count': 0,
                    'sticker_count': 0,
                    'nya_count': 0,
                }
            
            # Увеличиваем счетчик
            if stat_type == 'text':
                stats_data[key]['msg_count'] += 1
            elif stat_type == 'photo':
                stats_data[key]['photo_count'] += 1
            elif stat_type == 'video_file':
                stats_data[key]['video_count'] += 1
            elif stat_type == 'sticker':
                stats_data[key]['sticker_count'] += 1
            elif stat_type == 'nya':
                stats_data[key]['nya_count'] += 1
            
            user_ids.add(tg_user_id)
            
        except (ValueError, KeyError) as e:
            print(f"[WARN] Error processing message: {e}")
            continue
    
    print(f"[OK] Grouped {len(stats_data)} records (user_id, date)")
    print(f"[OK] Unique users: {len(user_ids)}\n")
    
    # Этап 2: Создаем или находим пользователей
    print("[STEP 2] Processing users...")
    user_id_map = {}  # { tg_id -> user_id in DB }
    
    with session_scope() as session:
        for tg_id in user_ids:
            user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
            
            if user is None:
                # Создаем нового пользователя
                user = TelegramUser(tg_id=tg_id)
                session.add(user)
                session.flush()  # Чтобы получить ID
            
            user_id_map[tg_id] = user.id
    
    print(f"[OK] Processed {len(user_id_map)} users\n")
    
    # Этап 3: Импортируем данные в DailyStatistic
    print("[STEP 3] Import to DailyStatistic...")
    
    imported_count = 0
    skipped_count = 0
    
    with session_scope() as session:
        for i, ((tg_id, msg_date), counts) in enumerate(stats_data.items()):
            if i % 10000 == 0:
                print(f"   Imported {i}/{len(stats_data)}...")
            
            user_id = user_id_map[tg_id]
            
            # Проверяем, существует ли уже запись за этот день
            existing = session.query(DailyStatistic).filter_by(
                user_id=user_id,
                date=msg_date
            ).first()
            
            if existing:
                # Сумме к существующей записи
                existing.msg_count += counts['msg_count']
                existing.photo_count += counts['photo_count']
                existing.video_count += counts['video_count']
                existing.sticker_count += counts['sticker_count']
                existing.nya_count += counts['nya_count']
                existing.calculate_percentages()
                skipped_count += 1
            else:
                # Создаем новую запись
                daily_stat = DailyStatistic(
                    user_id=user_id,
                    date=msg_date,
                    msg_count=counts['msg_count'],
                    photo_count=counts['photo_count'],
                    video_count=counts['video_count'],
                    sticker_count=counts['sticker_count'],
                    nya_count=counts['nya_count'],
                )
                daily_stat.calculate_percentages()
                session.add(daily_stat)
                imported_count += 1
            
            # Батчим для оптимизации
            if (i + 1) % batch_size == 0:
                session.commit()
    
    print(f"\n[OK] Import completed!")
    print(f"[STAT] Created new records: {imported_count}")
    print(f"[STAT] Updated existing: {skipped_count}")
    print(f"[STAT] Total processed: {imported_count + skipped_count}")
    print(f"[STAT] Users: {len(user_id_map)}")


def get_import_stats():
    """
    Выводит статистику импортированных данных
    """
    with session_scope() as session:
        total_records = session.query(DailyStatistic).count()
        users_with_history = session.query(DailyStatistic.user_id.distinct()).count()
        
        total_messages = session.query(
            func.sum(DailyStatistic.msg_count)
        ).scalar() or 0
        
        date_range = session.query(
            func.min(DailyStatistic.date),
            func.max(DailyStatistic.date)
        ).first()
        
        print("\n[IMPORT STATS]:")
        print(f"   Total records in DailyStatistic: {total_records}")
        print(f"   Users with history: {users_with_history}")
        print(f"   Total messages: {total_messages}")
        if date_range[0]:
            print(f"   Period: {date_range[0]} to {date_range[1]}")


if __name__ == "__main__":
    import os
    
    # Убедимся что таблица существует
    from telegram_bot.tg_db import Base, engine
    Base.metadata.create_all(bind=engine)
    
    # Путь к файлу
    json_path = 'parsed_history.json'
    
    if not os.path.exists(json_path):
        print(f"[ERROR] File {json_path} not found!")
        sys.exit(1)
    
    # Запускаем импорт
    parse_and_import_history(json_path)
    
    # Выводим статистику
    get_import_stats()
