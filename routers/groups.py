from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from models import Group, GroupMember, User, Homework
from schemas import GroupCreate, GroupResponse, GroupResponseWithInvite, GroupUpdate, GroupStatusUpdate, HomeworkResponse
from dependencies import get_current_user, get_teacher_user, get_student_user
from utils import generate_invite_link
from datetime import datetime, timezone
from scheduler import schedule_homework_reminder
from bot_notifier import send_new_homework_notification
from pydantic import BaseModel, Field
import secrets
import string
import logging
import urllib.parse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


def generate_invite_code(length: int = 8) -> str:
    """Генерирует уникальный код приглашения."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class JoinGroupRequest(BaseModel):
    """Схема для присоединения к группе по invite-коду."""
    inviteCode: str = Field(..., description="Invite код группы")

    class Config:
        populate_by_name = True


@router.post("/join", response_model=GroupResponse)
async def join_group(
    join_data: JoinGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_student_user)
):
    """
    Присоединиться к группе по invite-коду.
    Доступно только для студентов.
    
    Принимает inviteCode, который может быть в формате:
    - Просто код: "XYZ1A2B3C"
    - С префиксом: "group_XYZ1A2B3C" (префикс будет удален)
    """
    invite_code = join_data.inviteCode.strip()
    
    # Удаляем префикс "group_" если он есть (фронтенд может добавлять его)
    if invite_code.startswith("group_"):
        invite_code = invite_code[6:]  # Убираем "group_"
    
    # Декодируем URL-кодированный invite_code (на случай если он был закодирован)
    invite_code = urllib.parse.unquote(invite_code)
    
    # Ищем группу по invite-коду
    group = db.query(Group).filter(Group.invite_code == invite_code).first()
    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found. Please check the invite code."
        )
    
    # Проверяем, что группа активна
    if not group.is_active:
        raise HTTPException(
            status_code=400,
            detail="This group is currently paused. Contact the teacher for more information."
        )
    
    # Проверяем, что пользователь не является учителем этой группы
    if group.teacher_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You are the teacher of this group. You cannot join it as a student."
        )
    
    # Проверяем, не состоит ли уже студент в группе
    existing_member = db.query(GroupMember).filter(
        GroupMember.group_id == group.id,
        GroupMember.student_id == current_user.id
    ).first()
    
    if existing_member:
        # Уже в группе - возвращаем информацию о группе
        logger.info(f"Student {current_user.tg_id} already a member of group {group.id}")
    else:
        # Добавляем студента в группу
        try:
            new_member = GroupMember(
                group_id=group.id,
                student_id=current_user.id
            )
            db.add(new_member)
            db.commit()
            logger.info(f"Student {current_user.tg_id} joined group {group.id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding student to group: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to join group"
            )
    
    # Получаем список студентов группы (tg_id)
    members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    students = []
    for member in members:
        student = db.query(User).filter(User.id == member.student_id).first()
        if student:
            students.append(student.tg_id)
    
    # Возвращаем информацию о группе
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


@router.get("/{group_id}/invite-link", response_model=GroupResponseWithInvite)
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
    
    # Получаем список студентов группы (tg_id)
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    students = []
    for member in members:
        student = db.query(User).filter(User.id == member.student_id).first()
        if student:
            students.append(student.tg_id)
    
    invite_link = generate_invite_link(group.invite_code)
    
    return GroupResponseWithInvite(
        id=group.id,
        teacherId=group.teacher_id,
        name=group.name,
        inviteCode=group.invite_code,
        isActive=group.is_active,
        createdAt=group.created_at,
        students=students,
        inviteLink=invite_link
    )


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
    
    # Формируем ответы с правильным форматом студентов
    result = []
    for group in all_groups:
        members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
        students = []
        for member in members:
            student = db.query(User).filter(User.id == member.student_id).first()
            if student:
                students.append(student.tg_id)
        
        group_dict = {
            "id": group.id,
            "name": group.name,
            "teacherId": group.teacher_id,
            "inviteCode": group.invite_code,
            "isActive": group.is_active,
            "createdAt": group.created_at,
            "students": students
        }
        result.append(GroupResponse(**group_dict))
    
    return result


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


class HomeworkCreateForGroup(BaseModel):
    """Схема для создания ДЗ для группы (без group_id, так как он в пути)"""
    description: str
    deadline: datetime

    class Config:
        populate_by_name = True


@router.get("/{group_id}/homework", response_model=list[HomeworkResponse])
async def get_homework_for_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список домашних заданий для группы.
    Доступно для учителя группы или учеников, состоящих в группе.
    """
    # Проверяем, что группа существует
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
    
    # Получаем домашние задания для группы
    homeworks = db.query(Homework).filter(
        Homework.group_id == group_id
    ).order_by(Homework.deadline.desc()).all()
    
    return [HomeworkResponse.model_validate(h) for h in homeworks]


@router.post("/{group_id}/homework", response_model=HomeworkResponse)
async def create_homework_for_group(
    group_id: int,
    homework_data: HomeworkCreateForGroup,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """
    Создать домашнее задание для группы.
    Доступно только для учителя группы.
    
    Принимает:
    - description: Описание задания
    - deadline: Дедлайн (в UTC)
    
    Триггерирует планировщик для отправки уведомлений за 1 час до дедлайна.
    """
    # Проверяем, что группа существует и пользователь является её учителем
    group = db.query(Group).filter(Group.id == group_id).first()
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
        group_id=group_id,
        description=homework_data.description,
        deadline=deadline_utc
    )
    
    db.add(homework)
    db.commit()
    db.refresh(homework)
    
    # Планируем напоминание через APScheduler
    schedule_homework_reminder(homework.id, deadline_utc, group_id)
    
    # Отправляем уведомления всем ученикам группы о новом ДЗ в фоновом режиме
    # Проверяем, что группа активна (уведомления отправляются только для активных групп)
    if group.is_active:
        members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        for member in members:
            student = db.query(User).filter(User.id == member.student_id).first()
            if student and student.is_active:
                # Добавляем задачу в фоновые задачи FastAPI
                background_tasks.add_task(send_new_homework_notification, student.tg_id, homework, group)
    
    return HomeworkResponse.model_validate(homework)

