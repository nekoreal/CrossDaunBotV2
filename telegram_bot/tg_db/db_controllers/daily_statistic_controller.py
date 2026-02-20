from datetime import date
from ..import session_scope
from ..models.daily_statistic import DailyStatistic
from ..models.tg_user import TelegramUser 


def add_daily_stat(user_id, stat_type, statistic_date=None):
    """
    Добавляет или обновляет дневную статистику пользователя
    
    :param user_id: ID пользователя в БД
    :param stat_type: Тип контента ('text', 'photo', 'video', 'sticker', 'nya')
    :param statistic_date: Дата (по умолчанию сегодня)
    """ 
    if statistic_date is None:
        statistic_date = date.today()
    
    with session_scope() as session: 
        daily = session.query(DailyStatistic).filter_by(
            user_id=user_id,
            date=statistic_date
        ).first()
         

        if daily is None: 
            daily = DailyStatistic(user_id=user_id, date=statistic_date)
            session.add(daily)
            session.flush()
        
         
        if stat_type == 'text':
            daily.msg_count += 1
        elif stat_type == 'photo':
            daily.photo_count += 1
        elif stat_type == 'video':
            daily.video_count += 1
        elif stat_type == 'sticker':
            daily.sticker_count += 1
        elif stat_type == 'nya':
            daily.nya_count += 1
         
        daily.calculate_percentages()
        session.commit() 
        return daily.to_dict()
    


def get_daily_stat(user_id, statistic_date=None):
    """
    Получает дневную статистику пользователя
    
    :param user_id: ID пользователя в БД
    :param statistic_date: Дата (по умолчанию сегодня)
    :return: dict с статистикой или None
    """
    if statistic_date is None:
        statistic_date = date.today()
    
    with session_scope() as session:
        daily = session.query(DailyStatistic).filter_by(
            user_id=user_id,
            date=statistic_date
        ).first()
        
        return daily.to_dict() if daily else None


def get_user_stats_period(user_id, start_date, end_date):
    """
    Получает статистику пользователя за период
    
    :param user_id: ID пользователя
    :param start_date: Начальная дата
    :param end_date: Конечная дата
    :return: Список статистики за период
    """
    with session_scope() as session:
        stats = session.query(DailyStatistic).filter(
            DailyStatistic.user_id == user_id,
            DailyStatistic.date >= start_date,
            DailyStatistic.date <= end_date
        ).order_by(DailyStatistic.date).all()
        
        return [s.to_dict() for s in stats]


def get_group_stat_by_date(statistic_date=None):
    """
    Получает общую статистику группы за день (сумма всех пользователей)
    
    :param statistic_date: Дата (по умолчанию сегодня)
    :return: dict с суммарной статистикой
    """
    if statistic_date is None:
        statistic_date = date.today()
    
    with session_scope() as session:
        stats = session.query(DailyStatistic).filter_by(date=statistic_date).all()
        
        if not stats:
            return None
        
        total_msg = sum(s.msg_count for s in stats)
        total_photo = sum(s.photo_count for s in stats)
        total_video = sum(s.video_count for s in stats)
        total_sticker = sum(s.sticker_count for s in stats)
        total_nya = sum(s.nya_count for s in stats)
        total = total_msg + total_photo + total_video + total_sticker + total_nya
        
        return {
            "date": statistic_date.isoformat(),
            "msg_count": total_msg,
            "photo_count": total_photo,
            "video_count": total_video,
            "sticker_count": total_sticker,
            "nya_count": total_nya,
            "total_count": total,
            "active_users": len(stats),
            "msg_percentage": (total_msg / total * 100) if total > 0 else 0,
            "photo_percentage": (total_photo / total * 100) if total > 0 else 0,
            "video_percentage": (total_video / total * 100) if total > 0 else 0,
            "sticker_percentage": (total_sticker / total * 100) if total > 0 else 0,
            "nya_percentage": (total_nya / total * 100) if total > 0 else 0,
        }


def get_group_stats_period(start_date, end_date):
    """
    Получает статистику группы за период
    
    :param start_date: Начальная дата
    :param end_date: Конечная дата
    :return: Список статистики по дням
    """
    with session_scope() as session:
        # Группируем по дате
        from sqlalchemy import func
        
        stats = session.query(
            DailyStatistic.date,
            func.sum(DailyStatistic.msg_count).label('msg_count'),
            func.sum(DailyStatistic.photo_count).label('photo_count'),
            func.sum(DailyStatistic.video_count).label('video_count'),
            func.sum(DailyStatistic.sticker_count).label('sticker_count'),
            func.sum(DailyStatistic.nya_count).label('nya_count'),
            func.count(DailyStatistic.user_id.distinct()).label('active_users'),
        ).filter(
            DailyStatistic.date >= start_date,
            DailyStatistic.date <= end_date
        ).group_by(DailyStatistic.date).order_by(DailyStatistic.date).all()
        
        result = []
        for stat in stats:
            total = stat.msg_count + stat.photo_count + stat.video_count + stat.sticker_count + stat.nya_count
            result.append({
                "date": stat.date.isoformat(),
                "msg_count": stat.msg_count,
                "photo_count": stat.photo_count,
                "video_count": stat.video_count,
                "sticker_count": stat.sticker_count,
                "nya_count": stat.nya_count,
                "total_count": total,
                "active_users": stat.active_users,
                "msg_percentage": (stat.msg_count / total * 100) if total > 0 else 0,
                "photo_percentage": (stat.photo_count / total * 100) if total > 0 else 0,
                "video_percentage": (stat.video_count / total * 100) if total > 0 else 0,
                "sticker_percentage": (stat.sticker_count / total * 100) if total > 0 else 0,
                "nya_percentage": (stat.nya_count / total * 100) if total > 0 else 0,
            })
        
        return result
 