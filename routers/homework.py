from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Homework, Group, User, HomeworkCompletion, GroupMember
from schemas import HomeworkCreate, HomeworkUpdate, HomeworkResponse
from dependencies import get_current_user, get_teacher_user, get_student_user
from datetime import datetime, timezone
from scheduler import schedule_homework_reminder, cancel_homework_reminder
from bot_notifier import send_new_homework_notification
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/homework", tags=["homework"])


@router.get("/", response_model=list[HomeworkResponse])
async def get_homework_list(
    group_id: Optional[int] = Query(None, description="Фильтр по ID группы"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список домашних заданий.
    
    Если указан group_id, возвращает задания только для этой группы.
    Если group_id не указан, возвращает все задания для групп пользователя.
    """
    # Получаем группы пользователя
    teacher_groups = db.query(Group).filter(Group.teacher_id == current_user.id).all()
    
    student_memberships = db.query(GroupMember).filter(
        GroupMember.student_id == current_user.id
    ).all()
    student_groups = [membership.group for membership in student_memberships]
    
    all_groups = list(set(teacher_groups + student_groups))
    group_ids = [group.id for group in all_groups]
    
    if not group_ids:
        return []
    
    # Если указан group_id, проверяем доступ и фильтруем
    if group_id:
        if group_id not in group_ids:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this group"
            )
        homeworks = db.query(Homework).filter(Homework.group_id == group_id).order_by(Homework.deadline.desc()).all()
    else:
        # Возвращаем все задания для групп пользователя
        homeworks = db.query(Homework).filter(
            Homework.group_id.in_(group_ids)
        ).order_by(Homework.deadline.desc()).all()
    
    return homeworks


@router.get("/{homework_id}", response_model=HomeworkResponse)
async def get_homework(
    homework_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить домашнее задание по ID.
    Доступно только для учителя группы или учеников, состоящих в группе.
    """
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Проверяем права доступа
    group = db.query(Group).filter(Group.id == homework.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    is_teacher = group.teacher_id == current_user.id
    is_student = db.query(GroupMember).filter(
        GroupMember.group_id == homework.group_id,
        GroupMember.student_id == current_user.id
    ).first() is not None
    
    if not (is_teacher or is_student):
        raise HTTPException(
            status_code=403,
            detail="Access denied. You must be a teacher or member of this group."
        )
    
    return homework


class HomeworkCreateRequest(BaseModel):
    """Схема для создания ДЗ с group_id"""
    group_id: int
    description: str
    deadline: datetime


@router.post("/", response_model=HomeworkResponse)
async def create_homework(
    homework_data: HomeworkCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Выдать новое домашнее задание.
    
    Принимает:
    - group_id: ID группы
    - description: Описание задания
    - deadline: Дедлайн (в UTC)
    
    Триггерирует планировщик для отправки уведомлений за 1 час до дедлайна.
    """
    # Проверяем, что группа существует и пользователь является её учителем
    group = db.query(Group).filter(Group.id == homework_data.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    # Проверяем, что группа активна (не приостановлена)
    if not group.is_active:
        raise HTTPException(
            status_code=400, 
            detail="Cannot create homework for paused group. Please resume the group first."
        )
    
    # Убеждаемся, что deadline в UTC
    deadline_utc = homework_data.deadline
    if deadline_utc.tzinfo is None:
        deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
    else:
        deadline_utc = deadline_utc.astimezone(timezone.utc)
    
    homework = Homework(
        group_id=homework_data.group_id,
        description=homework_data.description,
        deadline=deadline_utc
    )
    
    db.add(homework)
    db.commit()
    db.refresh(homework)
    
    # Планируем напоминание через APScheduler
    schedule_homework_reminder(homework.id, deadline_utc, homework_data.group_id)
    
    # Отправляем уведомления всем ученикам группы о новом ДЗ в фоновом режиме
    # Проверяем, что группа активна (уведомления отправляются только для активных групп)
    if group.is_active:
        members = db.query(GroupMember).filter(GroupMember.group_id == homework_data.group_id).all()
        for member in members:
            student = db.query(User).filter(User.id == member.student_id).first()
            if student and student.is_active:
                # Добавляем задачу в фоновые задачи FastAPI
                background_tasks.add_task(send_new_homework_notification, student.tg_id, homework, group)
    
    return homework


@router.put("/{homework_id}", response_model=HomeworkResponse)
async def update_homework(
    homework_id: int,
    homework_data: HomeworkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Редактировать домашнее задание.
    Доступно только для учителя группы.
    При изменении дедлайна перепланируется напоминание.
    """
    # Получаем домашнее задание
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Проверяем, что пользователь является учителем группы
    group = db.query(Group).filter(Group.id == homework.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    # Сохраняем старый дедлайн для проверки изменений
    old_deadline = homework.deadline
    deadline_changed = False
    
    # Обновляем только переданные поля
    update_data = homework_data.model_dump(exclude_unset=True)
    
    # Если изменяется дедлайн, обрабатываем его
    if "deadline" in update_data:
        deadline_utc = update_data["deadline"]
        if deadline_utc.tzinfo is None:
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        else:
            deadline_utc = deadline_utc.astimezone(timezone.utc)
        update_data["deadline"] = deadline_utc
        deadline_changed = (deadline_utc != old_deadline)
    
    # Обновляем поля
    for field, value in update_data.items():
        setattr(homework, field, value)
    
    db.commit()
    db.refresh(homework)
    
    # Если дедлайн изменился, отменяем старое напоминание и планируем новое
    if deadline_changed:
        cancel_homework_reminder(homework_id)
        schedule_homework_reminder(homework.id, homework.deadline, homework.group_id)
    
    return homework


@router.delete("/{homework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_homework(
    homework_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Удалить домашнее задание.
    Доступно только для учителя группы.
    При удалении отменяется запланированное напоминание.
    """
    # Получаем домашнее задание
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Проверяем, что пользователь является учителем группы
    group = db.query(Group).filter(Group.id == homework.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    # Отменяем запланированное напоминание
    cancel_homework_reminder(homework_id)
    
    # Удаляем домашнее задание
    db.delete(homework)
    db.commit()
    
    return None


@router.post("/{homework_id}/complete")
async def complete_homework(
    homework_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_student_user)
):
    """Ученик отмечает задание как выполненное."""
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Проверяем, что ученик состоит в группе
    group_member = db.query(GroupMember).filter(
        GroupMember.group_id == homework.group_id,
        GroupMember.student_id == current_user.id
    ).first()
    
    if not group_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # Проверяем, не выполнено ли уже задание
    existing_completion = db.query(HomeworkCompletion).filter(
        HomeworkCompletion.homework_id == homework_id,
        HomeworkCompletion.student_id == current_user.id
    ).first()
    
    if existing_completion:
        raise HTTPException(status_code=400, detail="Homework already completed")
    
    completion = HomeworkCompletion(
        homework_id=homework_id,
        student_id=current_user.id
    )
    
    db.add(completion)
    db.commit()
    
    return {"message": "Homework marked as completed", "completion_id": completion.id}

