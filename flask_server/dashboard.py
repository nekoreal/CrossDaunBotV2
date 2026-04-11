import json

from flask import Flask, render_template, request
from datetime import date, timedelta, datetime

from rabbitmq import queue_sender
from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.models.tg_at_user_tag import UserTagAssociation
from telegram_bot.tg_db.models.daily_statistic import DailyStatistic
from telegram_bot.tg_db.db_controllers.daily_statistic_controller import (
    get_daily_stat,
    get_user_stats_period,
    get_group_stat_by_date,
    get_group_stats_period,
)
from telegram_bot.bot import bot
from config import TELEGRAM_CHAT_ID
from telegram_bot.tg_utils.avatar import get_and_resize_chat_photo
from telegram_bot.handlers.statistics import get_day_msg_count
from sqlalchemy import func
app = Flask(__name__)


from collections import defaultdict

def aggregate_list(stats_list):
            agg = defaultdict(lambda: {"msg":0,"photo":0,"video":0,"sticker":0,"nya":0,"total":0})
            for s in stats_list:
                a = agg[s.user_id]
                a["msg"] += s.msg_count
                a["photo"] += s.photo_count
                a["video"] += s.video_count
                a["sticker"] += s.sticker_count
                a["nya"] += s.nya_count
                a["total"] += s.msg_count + s.photo_count + s.video_count + s.sticker_count + s.nya_count
            return agg

def parse_device_type(user_agent):
    user_agent = user_agent.lower()
    if 'mobile' in user_agent:
        return 'mobile'
    elif 'tablet' in user_agent:
        return 'tablet'
    elif 'bot' in user_agent or 'crawler' in user_agent:
        return 'bot'
    else:
        return 'desktop'


@app.route('/')
def index():
    user_data = [
    {
        'timestamp': datetime.now().isoformat(),
        'endpoint': '/',
        'method': request.method,
    },{
        'ip': request.remote_addr,
        'real_ip': request.headers.get('X-Real-IP', request.remote_addr),
        'forwarded_for': request.headers.get('X-Forwarded-For', ''),
    },{
        'user_agent': request.headers.get('User-Agent', ''),
        'platform': request.user_agent.platform if hasattr(request, 'user_agent') else 'Unknown',
        'browser': request.user_agent.browser if hasattr(request, 'user_agent') else 'Unknown',
        'language': request.headers.get('Accept-Language', ''),
        'encoding': request.headers.get('Accept-Encoding', ''),
    },
    {
        'device_type': parse_device_type(request.headers.get('User-Agent', '')),
    }
    ]
    queue_sender("tg_notify",
                 body=json.dumps(user_data),
                 )

    today=date.today()
    month_start = today.replace(day=1) 

    
    with session_scope() as session:
        users = session.query(TelegramUser).all()
 
        min_date_result = session.query(func.min(DailyStatistic.date)).scalar()
        all_time_start = min_date_result or today
 
        stats_today = session.query(DailyStatistic).filter(DailyStatistic.date == today).all()
        stats_month = session.query(DailyStatistic).filter(DailyStatistic.date >= month_start).all()
         
        today_msg =  sum( s.total for s in stats_today ) 
 
        month_map = aggregate_list(stats_month)  

        users_data = []
        for user in users:
            d = user.to_dict() 
            
            try:
                member = bot.get_chat_member(TELEGRAM_CHAT_ID, user.tg_id)
                username= member.user.username or member.user.first_name or user.tg_id 
            except:
                username=f"ID:{user.tg_id}"

            m = month_map.get(user.id, {})
            d["month_messages"] = m.get("msg", 0)
            d["month_photos"] = m.get("photo", 0)
            d["month_videos"] = m.get("video", 0)
            d["month_stickers"] = m.get("sticker", 0)
            d["month_nya"] = m.get("nya", 0)
            d["month_total"] = m.get("total", 0)
            d["username_plain"] = username
            d["profile_url"] = f"tg://user?id={user.tg_id}"
            d["avatar"] = f"https://t.me/i/userpic/320/{username}.jpg" if username else "https://ui-avatars.com/api/?name=?"

            users_data.append(d)
 
    users_data = sorted(users_data, key=lambda x: x["msg_count"], reverse=True)
      
    
    data={
        "users": users_data,
        "today_msg_count": today_msg, 
        "all_time_msg": sum( u['msg_count'] for u in users_data),
        "month_user": max(users_data, key=lambda x: x["month_messages"]) if users_data else None,
    }  
    return render_template('index.html', data=data, reverse=True)

def run_flask():
    app.run(debug=False, host='0.0.0.0', port=5002)