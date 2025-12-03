from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Group, GroupMember, User
from schemas import GroupCreate, GroupResponse, GroupResponseWithInvite, GroupUpdate, GroupStatusUpdate
from dependencies import get_current_user, get_teacher_user
from utils import generate_invite_link
import secrets
import string
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


def generate_invite_code(length: int = 8) -> str:
    """Генерирует уникальный код приглашения."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post("/", response_model=GroupResponseWithInvite)
async def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Создать новую группу (только для учителей).
    Автоматически генерирует уникальный токен и ссылку-приглашение.
    """
    # Генерируем уникальный invite_code (используется как invite_token)
    while True:
        invite_code = generate_invite_code()
        existing = db.query(Group).filter(Group.invite_code == invite_code).first()
        if not existing:
            break
    
    group = Group(
        teacher_id=current_user.id,
        name=group_data.name,
        invite_code=invite_code
    )
    
    db.add(group)
    db.commit()
    db.refresh(group)
    
    # Генерируем ссылку-приглашение
    invite_link = generate_invite_link(group.invite_code)
    
    # Возвращаем группу с ссылкой (студентов пока нет, так как группа только создана)
    response = GroupResponseWithInvite(
        id=group.id,
        teacherId=group.teacher_id,
        name=group.name,
        inviteCode=group.invite_code,
        isActive=group.is_active,
        createdAt=group.created_at,
        students=[],  # Пустой список, так как группа только создана
        inviteLink=invite_link
    )
    
    return response


@router.get("/{group_id}/invite-link")
async def get_invite_link(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить ссылку-приглашение для группы.
    Доступно только учителю группы.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only group teacher can get invite link")
    
    invite_link = generate_invite_link(group.invite_code)
    
    return {
        "groupId": group.id,
        "groupName": group.name,
        "inviteCode": group.invite_code,
        "inviteLink": invite_link
    }


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить группу по ID.
    Доступно только для учителя группы или учеников, состоящих в группе.
    """
    # Получаем группу
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа: пользователь должен быть либо учителем, либо учеником группы
    is_teacher = group.teacher_id == current_user.id
    is_student = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == current_user.id
    ).first() is not None
    
    if not (is_teacher or is_student):
        raise HTTPException(
            status_code=403,
            detail="Access denied. You must be a teacher or member of this group."
        )
    
    # Получаем список студентов группы (tg_id)
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    students = []
    for member in members:
        student = db.query(User).filter(User.id == member.student_id).first()
        if student:
            students.append(student.tg_id)
    
    # Создаем ответ с добавлением студентов
    group_dict = {
        "id": group.id,
        "name": group.name,
        "teacherId": group.teacher_id,
        "inviteCode": group.invite_code,
        "isActive": group.is_active,
        "createdAt": group.created_at,
        "students": students
    }
    return GroupResponse(**group_dict)


@router.get("/", response_model=list[GroupResponse])
async def get_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список групп, где пользователь является учителем или учеником."""
    # Группы где пользователь учитель
    teacher_groups = db.query(Group).filter(Group.teacher_id == current_user.id).all()
    
    # Группы где пользователь ученик
    student_memberships = db.query(GroupMember).filter(
        GroupMember.student_id == current_user.id
    ).all()
    student_groups = [membership.group for membership in student_memberships]
    
    # Объединяем и убираем дубликаты по ID (объекты SQLAlchemy не хешируемые)
    all_groups_dict = {group.id: group for group in teacher_groups + student_groups}
    all_groups = list(all_groups_dict.values())
    
    return [GroupResponse.model_validate(g) for g in all_groups]


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Обновить название группы.
    Доступно только для учителя группы.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only group teacher can update group")
    
    group.name = group_data.name
    db.commit()
    db.refresh(group)
    
    logger.info(f"Group {group_id} name updated to '{group_data.name}' by teacher {current_user.tg_id}")
    return GroupResponse.model_validate(group)


@router.patch("/{group_id}/status", response_model=GroupResponse)
async def update_group_status(
    group_id: int,
    status_data: GroupStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Приостановить или возобновить группу.
    Доступно только для учителя группы.
    
    Если группа приостановлена (is_active=False), бот не отправляет уведомления участникам.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only group teacher can update group status")
    
    group.is_active = status_data.isActive
    db.commit()
    db.refresh(group)
    
    status_text = "возобновлена" if status_data.isActive else "приостановлена"
    logger.info(f"Group {group_id} {status_text} by teacher {current_user.tg_id}")
    
    return GroupResponse.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Удалить группу.
    Доступно только для учителя группы.
    
    При удалении группы каскадно удаляются:
    - Все участники группы
    - Все домашние задания
    - Все расписание
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only group teacher can delete group")
    
    db.delete(group)
    db.commit()
    
    logger.info(f"Group {group_id} deleted by teacher {current_user.tg_id}")
    return None


@router.delete("/{group_id}/students/{student_tg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student_from_group(
    group_id: int,
    student_tg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Удалить ученика из группы.
    Доступно только для учителя группы.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Проверяем права доступа
    if group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only group teacher can remove students")
    
    # Находим студента по tg_id
    student = db.query(User).filter(User.tg_id == student_tg_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Находим членство в группе
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == student.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="Student is not a member of this group")
    
    db.delete(membership)
    db.commit()
    
    logger.info(f"Student {student_tg_id} removed from group {group_id} by teacher {current_user.tg_id}")
    return None

