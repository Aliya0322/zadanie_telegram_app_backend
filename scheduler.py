from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import SessionLocal
from models import Homework, Group, GroupMember, User, Schedule, DayOfWeek
from bot_notifier import send_homework_reminder, send_class_reminder
import pytz
import asyncio
import calendar

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
        
        # Проверяем, что группа активна (не приостановлена)
        if not group.is_active:
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



def schedule_class_reminders():
    """
    Планирует напоминания о занятиях на сегодня и завтра.
    Запускается каждый день в 00:01 UTC.
    Для каждого занятия планируется напоминание за 1 час до начала.
    """
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    tomorrow = today + timedelta(days=1)
    
    day_mapping = {
        'monday': DayOfWeek.MONDAY,
        'tuesday': DayOfWeek.TUESDAY,
        'wednesday': DayOfWeek.WEDNESDAY,
        'thursday': DayOfWeek.THURSDAY,
        'friday': DayOfWeek.FRIDAY,
        'saturday': DayOfWeek.SATURDAY,
        'sunday': DayOfWeek.SUNDAY,
    }
    
    today_day_name = calendar.day_name[today.weekday()].lower()
    tomorrow_day_name = calendar.day_name[tomorrow.weekday()].lower()
    
    today_day = day_mapping.get(today_day_name)
    tomorrow_day = day_mapping.get(tomorrow_day_name)
    
    db: Session = SessionLocal()
    try:
        # Находим все занятия на сегодня и завтра для активных групп с расписанием
        day_filters = []
        if today_day:
            day_filters.append(Schedule.day_of_week == today_day)
        if tomorrow_day:
            day_filters.append(Schedule.day_of_week == tomorrow_day)
        
        if not day_filters:
            return
        
        schedules = db.query(Schedule).join(Group).filter(
            or_(*day_filters),
            Schedule.meeting_link.isnot(None),  # Только если есть ссылка
            Group.is_active == True  # Только для активных групп
        ).all()
        
        for item in schedules:
            # Определяем, на какой день приходится это занятие
            if item.day_of_week == today_day:
                target_date = today
            elif item.day_of_week == tomorrow_day:
                target_date = tomorrow
            else:
                continue  # Пропускаем, если не сегодня и не завтра
            
            # Вычисляем время начала занятия
            class_time_utc = datetime.combine(target_date, item.time_at).replace(tzinfo=timezone.utc)
            # Время напоминания - за 1 час до начала занятия
            reminder_time = class_time_utc - timedelta(hours=1)
            
            # Планируем напоминание только если время еще не прошло
            if reminder_time > now_utc:
                job_id = f"class_reminder_{item.id}_{target_date}"
                
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
        
        # Проверяем, что группа активна (не приостановлена)
        if not group.is_active:
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

