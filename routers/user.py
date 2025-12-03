from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User, Schedule, Homework, GroupMember, Group, DayOfWeek
from schemas import (
    UserScheduleResponse, ScheduleResponse, HomeworkResponse,
    DashboardResponse, DashboardGroupResponse, TodayScheduleResponse
)
from dependencies import get_current_user
from datetime import datetime, timezone, date
import calendar

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить все данные для главного экрана дашборда.
    
    Возвращает:
    - user_role (Teacher/Student)
    - Список групп пользователя
    - Расписание на сегодня
    - Активные домашние задания
    """
    # Получаем все группы пользователя
    teacher_groups = db.query(Group).filter(Group.teacher_id == current_user.id).all()
    
    student_memberships = db.query(GroupMember).filter(
        GroupMember.student_id == current_user.id
    ).all()
    student_groups = [membership.group for membership in student_memberships]
    
    # Убираем дубликаты по ID (объекты SQLAlchemy не хешируемые)
    all_groups_dict = {group.id: group for group in teacher_groups + student_groups}
    all_groups = list(all_groups_dict.values())
    group_ids = [group.id for group in all_groups]
    
    # Формируем список групп для дашборда
    dashboard_groups = []
    for group in all_groups:
        # Получаем имя учителя (ФИО или tg_id)
        teacher = db.query(User).filter(User.id == group.teacher_id).first()
        if teacher:
            if teacher.last_name and teacher.first_name:
                teacher_name_parts = [teacher.last_name, teacher.first_name]
                if teacher.patronymic:
                    teacher_name_parts.append(teacher.patronymic)
                teacher_name = " ".join(teacher_name_parts)
            else:
                teacher_name = f"ID: {teacher.tg_id}"
        else:
            teacher_name = "Unknown"
        
        # Подсчитываем количество учеников
        student_count = db.query(GroupMember).filter(
            GroupMember.group_id == group.id
        ).count()
        
        dashboard_groups.append(DashboardGroupResponse(
            id=group.id,
            name=group.name,
            inviteCode=group.invite_code,
            teacherName=teacher_name,
            studentCount=student_count
        ))
    
    # Получаем расписание на сегодня
    today = date.today()
    day_name = calendar.day_name[today.weekday()].lower()
    
    # Маппинг английских названий дней на наши enum
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
    today_schedule = []
    
    if today_day and group_ids:
        schedules = db.query(Schedule).filter(
            Schedule.group_id.in_(group_ids),
            Schedule.day_of_week == today_day
        ).all()
        
        for schedule in schedules:
            group = db.query(Group).filter(Group.id == schedule.group_id).first()
            today_schedule.append(TodayScheduleResponse(
                id=schedule.id,
                groupName=group.name if group else "Unknown",
                dayOfWeek=schedule.day_of_week,
                timeAt=schedule.time_at,
                meetingLink=schedule.meeting_link
            ))
    
    # Получаем активные домашние задания (дедлайн еще не прошел)
    now_utc = datetime.now(timezone.utc)
    active_homeworks = []
    
    if group_ids:
        homeworks = db.query(Homework).filter(
            Homework.group_id.in_(group_ids),
            Homework.deadline > now_utc
        ).order_by(Homework.deadline.asc()).all()
        
        active_homeworks = [HomeworkResponse.model_validate(h) for h in homeworks]
    
    return DashboardResponse(
        userRole=current_user.role,
        groups=dashboard_groups,
        todaySchedule=today_schedule,
        activeHomeworks=active_homeworks
    )


@router.get("/schedule", response_model=UserScheduleResponse)
async def get_user_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить расписание и активные ДЗ для текущего пользователя."""
    # Получаем все группы пользователя
    teacher_groups = db.query(Group).filter(Group.teacher_id == current_user.id).all()
    
    student_memberships = db.query(GroupMember).filter(
        GroupMember.student_id == current_user.id
    ).all()
    student_groups = [membership.group for membership in student_memberships]
    
    # Убираем дубликаты по ID (объекты SQLAlchemy не хешируемые)
    all_groups_dict = {group.id: group for group in teacher_groups + student_groups}
    all_groups = list(all_groups_dict.values())
    group_ids = [group.id for group in all_groups]
    
    if not group_ids:
        return UserScheduleResponse(schedules=[], activeHomeworks=[])
    
    # Получаем расписание для всех групп
    schedules = db.query(Schedule).filter(Schedule.group_id.in_(group_ids)).all()
    
    # Получаем активные домашние задания (дедлайн еще не прошел)
    now_utc = datetime.now(timezone.utc)
    active_homeworks = db.query(Homework).filter(
        Homework.group_id.in_(group_ids),
        Homework.deadline > now_utc
    ).all()
    
    return UserScheduleResponse(
        schedules=[ScheduleResponse.model_validate(s) for s in schedules],
        activeHomeworks=[HomeworkResponse.model_validate(h) for h in active_homeworks]
    )

