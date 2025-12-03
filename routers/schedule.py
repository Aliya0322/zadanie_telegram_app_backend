from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Schedule, Group, User, GroupMember
from schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from dependencies import get_teacher_user, get_current_user
from typing import Optional

router = APIRouter(prefix="/api/v1/schedule", tags=["schedule"])


@router.get("/", response_model=list[ScheduleResponse])
async def get_schedule(
    groupId: Optional[int] = Query(None, description="Фильтр по ID группы"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить расписание.
    
    Если указан groupId, возвращает расписание только для этой группы.
    Если groupId не указан, возвращает расписание для всех групп пользователя.
    Доступно для учителя группы или учеников, состоящих в группе.
    """
    if groupId:
        # Проверяем доступ к группе
        group = db.query(Group).filter(Group.id == groupId).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Проверяем права доступа: пользователь должен быть либо учителем, либо учеником группы
        is_teacher = group.teacher_id == current_user.id
        is_student = db.query(GroupMember).filter(
            GroupMember.group_id == groupId,
            GroupMember.student_id == current_user.id
        ).first() is not None
        
        if not (is_teacher or is_student):
            raise HTTPException(
                status_code=403,
                detail="Access denied. You must be a teacher or member of this group."
            )
        
        schedules = db.query(Schedule).filter(Schedule.group_id == groupId).all()
    else:
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
            return []
        
        schedules = db.query(Schedule).filter(Schedule.group_id.in_(group_ids)).all()
    
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.post("/", response_model=ScheduleResponse)
async def create_schedule_item(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Добавить занятие в расписание.
    Только для учителя группы.
    """
    group = db.query(Group).filter(Group.id == schedule_data.groupId).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    schedule_item = Schedule(
        group_id=schedule_data.groupId,
        day_of_week=schedule_data.dayOfWeek,
        time_at=schedule_data.timeAt,
        duration=schedule_data.duration,
        meeting_link=schedule_data.meetingLink
    )
    
    db.add(schedule_item)
    db.commit()
    db.refresh(schedule_item)
    
    return ScheduleResponse.model_validate(schedule_item)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule_item(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Редактировать занятие в расписании.
    Доступно только для учителя группы.
    """
    # Получаем элемент расписания
    schedule_item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule_item:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    
    # Проверяем, что пользователь является учителем группы
    group = db.query(Group).filter(Group.id == schedule_item.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    # Обновляем только переданные поля
    # Используем by_alias=True чтобы получить snake_case имена полей для SQLAlchemy
    update_data = schedule_data.model_dump(exclude_unset=True, by_alias=True)
    for field, value in update_data.items():
        setattr(schedule_item, field, value)
    
    db.commit()
    db.refresh(schedule_item)
    
    return ScheduleResponse.model_validate(schedule_item)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_item(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """Удалить занятие из расписания."""
    schedule_item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule_item:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    
    group = db.query(Group).filter(Group.id == schedule_item.group_id).first()
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    db.delete(schedule_item)
    db.commit()
    return None

