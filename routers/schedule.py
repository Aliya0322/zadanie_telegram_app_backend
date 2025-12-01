from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Schedule, Group, User
from schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from dependencies import get_teacher_user

router = APIRouter(prefix="/api/v1/schedule", tags=["schedule"])


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
    group = db.query(Group).filter(Group.id == schedule_data.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the teacher of this group")
    
    schedule_item = Schedule(
        group_id=schedule_data.group_id,
        day_of_week=schedule_data.day_of_week,
        time_at=schedule_data.time_at,
        duration=schedule_data.duration,
        meeting_link=schedule_data.meeting_link
    )
    
    db.add(schedule_item)
    db.commit()
    db.refresh(schedule_item)
    
    return schedule_item


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
    update_data = schedule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule_item, field, value)
    
    db.commit()
    db.refresh(schedule_item)
    
    return schedule_item


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

