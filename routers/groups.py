from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Group, GroupMember, User
from schemas import GroupCreate, GroupResponse, GroupResponseWithInvite
from dependencies import get_current_user, get_teacher_user
from utils import generate_invite_link
import secrets
import string

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
    
    # Возвращаем группу с ссылкой
    response = GroupResponseWithInvite(
        id=group.id,
        teacher_id=group.teacher_id,
        name=group.name,
        invite_code=group.invite_code,
        created_at=group.created_at,
        invite_link=invite_link
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
        "group_id": group.id,
        "group_name": group.name,
        "invite_code": group.invite_code,
        "invite_link": invite_link
    }


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
    
    # Объединяем и убираем дубликаты
    all_groups = list(set(teacher_groups + student_groups))
    
    return all_groups

