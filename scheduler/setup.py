from apscheduler.triggers.cron import CronTrigger
from telegram_bot.handlers.photo_change_poll import start_contest
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone  

scheduler = BackgroundScheduler(timezone=timezone('Europe/Moscow'))

 
def init_scheduler(): 
    scheduler.add_job(
        start_contest,
        trigger=CronTrigger(day=1, hour=0, minute=0),
        id='monthly_contest',
        args=(None,) 
    )
     
    if not scheduler.running:
        scheduler.start()