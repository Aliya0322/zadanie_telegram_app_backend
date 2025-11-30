from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Homework, Group, GroupMember, User
from bot_notifier import send_homework_reminder
import pytz
import asyncio

scheduler = AsyncIOScheduler()


def schedule_homework_reminder(homework_id: int, deadline_utc: datetime, group_id: int):
    """
    Планирует отправку напоминания о домашнем задании.
    Напоминание отправляется за 1 час до дедлайна.
    """
    # Напоминание за 1 час до дедлайна
    reminder_time = deadline_utc - timedelta(hours=1)
    
    # Если время уже прошло, не планируем
    if reminder_time <= datetime.now(timezone.utc):
        return
    
    scheduler.add_job(
        send_homework_reminder_job,
        trigger=DateTrigger(run_date=reminder_time),
        args=[homework_id, group_id],
        id=f"homework_reminder_{homework_id}",
        replace_existing=True
    )


def cancel_homework_reminder(homework_id: int):
    """
    Отменяет запланированное напоминание о домашнем задании.
    """
    job_id = f"homework_reminder_{homework_id}"
    try:
        scheduler.remove_job(job_id)
    except:
        # Задача может быть уже удалена или не существовать
        pass


async def send_homework_reminder_job(homework_id: int, group_id: int):
    """Задача для отправки напоминания о домашнем задании."""
    db: Session = SessionLocal()
    try:
        homework = db.query(Homework).filter(Homework.id == homework_id).first()
        if not homework or homework.reminder_sent:
            return
        
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            return
        
        # Получаем всех учеников группы
        members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        
        for member in members:
            student = db.query(User).filter(User.id == member.student_id).first()
            if not student or not student.is_active:
                continue
            
            # Отправляем напоминание с учетом часового пояса пользователя
            await send_homework_reminder(student.tg_id, homework, group, student.timezone)
        
        # Помечаем, что напоминание отправлено
        homework.reminder_sent = True
        db.commit()
    finally:
        db.close()


from apscheduler.triggers.cron import CronTrigger
from models import Schedule, DayOfWeek
from bot_notifier import send_homework_reminder, send_class_reminder
import calendar

# ... (предыдущие импорты) ...

def schedule_class_reminders():
    """
    Планирует проверку занятий на текущий день.
    Запускается каждое утро.
    """
    # Очищаем старые задачи напоминаний о классах (опционально)
    # scheduler.remove_all_jobs() # Осторожно, удалит и домашки!
    
    today = datetime.now(timezone.utc).date()
    day_name = calendar.day_name[today.weekday()].lower()
    
    day_mapping = {
        'monday': DayOfWeek.MONDAY,
        'tuesday': DayOfWeek.TUESDAY,
        'wednesday': DayOfWeek.WEDNESDAY,
        'thursday': DayOfWeek.THURSDAY,
        'friday': DayOfWeek.FRIDAY,
        'saturday': DayOfWeek.SATURDAY,
        'sunday': DayOfWeek.SUNDAY,
    }
    
    today_day = day_mapping.get(day_name)
    if not today_day:
        return

    db: Session = SessionLocal()
    try:
        # Находим все занятия на сегодня
        schedules = db.query(Schedule).filter(
            Schedule.day_of_week == today_day,
            Schedule.meeting_link.isnot(None) # Только если есть ссылка
        ).all()
        
        for item in schedules:
            # Вычисляем время напоминания (за 1 час до начала)
            # item.time_at - это время дня. Нужно создать datetime на сегодня.
            # Предполагаем, что time_at хранится в UTC
            
            class_time_utc = datetime.combine(today, item.time_at).replace(tzinfo=timezone.utc)
            reminder_time = class_time_utc - timedelta(hours=1)
            
            # Если время напоминания в будущем
            if reminder_time > datetime.now(timezone.utc):
                job_id = f"class_reminder_{item.id}_{today}"
                
                scheduler.add_job(
                    send_class_reminder_job,
                    trigger=DateTrigger(run_date=reminder_time),
                    args=[item.id],
                    id=job_id,
                    replace_existing=True
                )
    finally:
        db.close()


async def send_class_reminder_job(schedule_id: int):
    """Задача для отправки напоминания о занятии."""
    db: Session = SessionLocal()
    try:
        schedule_item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule_item:
            return
            
        group = db.query(Group).filter(Group.id == schedule_item.group_id).first()
        if not group:
            return
            
        members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
        
        for member in members:
            student = db.query(User).filter(User.id == member.student_id).first()
            if not student or not student.is_active:
                continue
                
            await send_class_reminder(student.tg_id, group, schedule_item, student.timezone)
    finally:
        db.close()


def start_scheduler():
    """Запускает планировщик."""
    # Ежедневная задача по планированию напоминаний о классах (например, в 00:01 UTC)
    scheduler.add_job(
        schedule_class_reminders,
        trigger=CronTrigger(hour=0, minute=1),
        id="daily_class_scheduler",
        replace_existing=True
    )
    
    # Запускаем сразу при старте, чтобы запланировать на сегодня
    scheduler.add_job(schedule_class_reminders)
    
    scheduler.start()


def shutdown_scheduler():
    """Останавливает планировщик."""
    scheduler.shutdown()

