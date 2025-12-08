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
import logging

logger = logging.getLogger(__name__)

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
    Запускается каждый день в 00:01 UTC и каждый час для перепланирования.
    Для каждого занятия планируется напоминание за 1 час до начала.
    """
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    tomorrow = today + timedelta(days=1)
    
    logger.info(f"Starting schedule_class_reminders at {now_utc}, today={today}, tomorrow={tomorrow}")
    
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
        
        # Сначала получаем все расписания без фильтра по meeting_link для диагностики
        all_schedules = db.query(Schedule).join(Group).filter(
            or_(*day_filters),
            Group.is_active == True  # Только для активных групп
        ).all()
        
        logger.info(
            f"Found {len(all_schedules)} total schedules for today ({today_day_name}) and tomorrow ({tomorrow_day_name})"
        )
        
        # Логируем расписания без meeting_link
        schedules_without_link = [s for s in all_schedules if not s.meeting_link]
        if schedules_without_link:
            logger.warning(
                f"Found {len(schedules_without_link)} schedules without meeting_link: "
                f"{[s.id for s in schedules_without_link]}"
            )
        
        # Фильтруем только с meeting_link
        schedules = [s for s in all_schedules if s.meeting_link]
        
        logger.info(
            f"Found {len(schedules)} schedules with meeting_link for today ({today_day_name}) "
            f"and tomorrow ({tomorrow_day_name})"
        )
        
        for item in schedules:
            # Определяем, на какой день приходится это занятие
            if item.day_of_week == today_day:
                target_date = today
            elif item.day_of_week == tomorrow_day:
                target_date = tomorrow
            else:
                continue  # Пропускаем, если не сегодня и не завтра
            
            # Получаем учителя группы для определения часового пояса
            teacher = db.query(User).filter(User.id == item.group.teacher_id).first()
            if not teacher:
                logger.warning(f"Teacher not found for group {item.group_id}, skipping schedule {item.id}")
                continue
            
            # Используем часовой пояс учителя для интерпретации времени занятия
            try:
                teacher_tz = pytz.timezone(teacher.timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone {teacher.timezone} for teacher {teacher.id}, using UTC")
                teacher_tz = pytz.UTC
            
            # Вычисляем время начала занятия в часовом поясе учителя
            # Время в базе данных интерпретируется как локальное время учителя
            class_time_teacher_tz = teacher_tz.localize(datetime.combine(target_date, item.time_at))
            # Конвертируем в UTC для определения абсолютного времени занятия
            class_time_utc = class_time_teacher_tz.astimezone(timezone.utc)
            
            logger.info(
                f"Schedule {item.id}: class at {class_time_teacher_tz.strftime('%Y-%m-%d %H:%M %Z')} "
                f"({class_time_utc.strftime('%Y-%m-%d %H:%M UTC')})"
            )
            
            # Получаем всех учеников группы для планирования индивидуальных напоминаний
            members = db.query(GroupMember).filter(GroupMember.group_id == item.group_id).all()
            
            if not members:
                logger.warning(f"No members found for group {item.group_id}, schedule {item.id}")
            
            logger.info(
                f"Processing schedule {item.id} (group {item.group_id}): "
                f"{len(members)} members, class at {item.time_at}"
            )
            
            scheduled_count = 0
            for member in members:
                student = db.query(User).filter(User.id == member.student_id).first()
                if not student or not student.is_active:
                    continue
                
                # Используем часовой пояс ученика для расчета времени напоминания
                try:
                    student_tz = pytz.timezone(student.timezone)
                except pytz.exceptions.UnknownTimeZoneError:
                    logger.warning(f"Unknown timezone {student.timezone} for student {student.id}, using UTC")
                    student_tz = pytz.UTC
                
                # Конвертируем время занятия в часовой пояс ученика
                class_time_student_tz = class_time_utc.astimezone(student_tz)
                # Время напоминания - за 1 час до начала занятия в часовом поясе ученика
                reminder_time_student_tz = class_time_student_tz - timedelta(hours=1)
                # Конвертируем в UTC для планирования
                reminder_time_utc = reminder_time_student_tz.astimezone(timezone.utc)
                
                # Планируем напоминание только если время еще не прошло
                # И если занятие еще не началось (напоминание должно быть до начала занятия)
                if reminder_time_utc > now_utc and class_time_utc > now_utc:
                    job_id = f"class_reminder_{item.id}_{target_date}_student_{student.id}"
                    
                    # Проверяем, не запланировано ли уже это напоминание
                    try:
                        existing_job = scheduler.get_job(job_id)
                        if existing_job:
                            # Если задача уже существует и время совпадает, пропускаем
                            if existing_job.next_run_time and abs((existing_job.next_run_time - reminder_time_utc).total_seconds()) < 60:
                                logger.debug(f"Reminder {job_id} already scheduled, skipping")
                                scheduled_count += 1
                                continue
                    except Exception as e:
                        logger.debug(f"Could not check existing job {job_id}: {e}")
                    
                    scheduler.add_job(
                        send_class_reminder_to_student_job,
                        trigger=DateTrigger(run_date=reminder_time_utc),
                        args=[item.id, student.id],
                        id=job_id,
                        replace_existing=True
                    )
                    logger.info(
                        f"Scheduled reminder for student {student.id} (tz: {student.timezone}): "
                        f"class at {class_time_student_tz.strftime('%Y-%m-%d %H:%M %Z')}, "
                        f"reminder at {reminder_time_student_tz.strftime('%Y-%m-%d %H:%M %Z')} "
                        f"({reminder_time_utc.strftime('%Y-%m-%d %H:%M UTC')})"
                    )
                    scheduled_count += 1
                else:
                    if reminder_time_utc <= now_utc:
                        logger.warning(
                            f"Reminder time for student {student.id} ({reminder_time_utc}) has already passed "
                            f"(now: {now_utc}), skipping"
                        )
                    elif class_time_utc <= now_utc:
                        logger.warning(
                            f"Class time for student {student.id} ({class_time_utc}) has already passed "
                            f"(now: {now_utc}), skipping reminder"
                        )
            
            logger.info(f"Scheduled {scheduled_count} reminders for schedule {item.id}")
    finally:
        db.close()


async def send_class_reminder_to_student_job(schedule_id: int, student_id: int):
    """Задача для отправки напоминания о занятии конкретному ученику."""
    db: Session = SessionLocal()
    try:
        schedule_item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule_item:
            logger.warning(f"Schedule {schedule_id} not found")
            return
            
        group = db.query(Group).filter(Group.id == schedule_item.group_id).first()
        if not group:
            logger.warning(f"Group not found for schedule {schedule_id}")
            return
        
        # Проверяем, что группа активна (не приостановлена)
        if not group.is_active:
            logger.warning(f"Group {group.id} is not active, skipping reminder")
            return
        
        student = db.query(User).filter(User.id == student_id).first()
        if not student or not student.is_active:
            logger.warning(f"Student {student_id} not found or not active")
            return
        
        try:
            await send_class_reminder(student.tg_id, group, schedule_item, student.timezone)
            logger.info(f"Sent reminder to student {student.id} (tg_id: {student.tg_id}) for schedule {schedule_id}")
        except Exception as e:
            logger.error(f"Error sending reminder to student {student.id} (tg_id: {student.tg_id}): {e}")
    finally:
        db.close()


def start_scheduler():
    """Запускает планировщик."""
    # Ежедневная задача по планированию напоминаний о классах в 00:01 UTC
    scheduler.add_job(
        schedule_class_reminders,
        trigger=CronTrigger(hour=0, minute=1),
        id="daily_class_scheduler",
        replace_existing=True
    )
    
    # Также запускаем каждый час для перепланирования напоминаний, которые могли быть пропущены
    # Это гарантирует, что напоминания будут запланированы даже если приложение перезапустилось
    scheduler.add_job(
        schedule_class_reminders,
        trigger=CronTrigger(minute=0),  # Каждый час в 00 минут
        id="hourly_class_scheduler",
        replace_existing=True
    )
    
    # Запускаем сразу при старте, чтобы запланировать на сегодня
    scheduler.add_job(
        schedule_class_reminders,
        id="initial_class_scheduler",
        replace_existing=True
    )
    
    scheduler.start()


def shutdown_scheduler():
    """Останавливает планировщик."""
    scheduler.shutdown()


def get_scheduled_jobs_info():
    """Возвращает информацию о запланированных задачах для диагностики."""
    jobs = scheduler.get_jobs()
    return {
        "total_jobs": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "func": job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
                "args": job.args,
            }
            for job in jobs
        ]
    }

