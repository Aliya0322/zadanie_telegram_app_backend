from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Homework, Group, User, HomeworkCompletion
from schemas import HomeworkCreate, HomeworkResponse
from dependencies import get_current_user, get_teacher_user, get_student_user
from datetime import datetime, timezone
from scheduler import schedule_homework_reminder
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/homework", tags=["homework"])


class HomeworkCreateRequest(BaseModel):
    """Схема для создания ДЗ с group_id"""
    group_id: int
    description: str
    deadline: datetime


@router.post("/", response_model=HomeworkResponse)
async def create_homework(
    homework_data: HomeworkCreateRequest,
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
    
    return homework


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

