from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, time
from models import UserRole, DayOfWeek


# User schemas
class UserBase(BaseModel):
    tg_id: int
    role: UserRole
    timezone: str = "UTC"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: str
    last_name: str
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    timezone: str  # Обязательное поле - пользователь должен указать вручную


# Group schemas
class GroupBase(BaseModel):
    name: str


class GroupCreate(GroupBase):
    pass


class GroupResponse(GroupBase):
    id: int
    teacher_id: int
    invite_code: str
    is_active: bool
    created_at: datetime
    students: List[int] = []

    class Config:
        from_attributes = True


class GroupUpdate(BaseModel):
    """Схема для обновления названия группы."""
    name: str


class GroupStatusUpdate(BaseModel):
    """Схема для обновления статуса группы."""
    is_active: bool


class GroupResponseWithInvite(GroupResponse):
    """Расширенный ответ с ссылкой-приглашением."""
    invite_link: str


# Homework schemas
class HomeworkBase(BaseModel):
    description: str
    deadline: datetime


class HomeworkCreate(HomeworkBase):
    pass


class HomeworkUpdate(BaseModel):
    """Схема для обновления домашнего задания. Все поля опциональные."""
    description: Optional[str] = None
    deadline: Optional[datetime] = None


class HomeworkResponse(HomeworkBase):
    id: int
    group_id: int
    created_at: datetime
    reminder_sent: bool

    class Config:
        from_attributes = True


# Schedule schemas
class ScheduleBase(BaseModel):
    day_of_week: DayOfWeek
    time_at: time
    duration: Optional[int] = None  # Продолжительность в минутах
    meeting_link: Optional[str] = None


class ScheduleCreate(ScheduleBase):
    group_id: int


class ScheduleUpdate(BaseModel):
    """Схема для обновления расписания. Все поля опциональные."""
    day_of_week: Optional[DayOfWeek] = None
    time_at: Optional[time] = None
    duration: Optional[int] = None
    meeting_link: Optional[str] = None


class ScheduleResponse(ScheduleBase):
    id: int
    group_id: int

    class Config:
        from_attributes = True


# Combined response schemas
class UserScheduleResponse(BaseModel):
    schedules: List[ScheduleResponse]
    active_homeworks: List[HomeworkResponse]


# Auth schemas
class LoginResponse(BaseModel):
    user: UserResponse
    is_new_user: bool
    message: str


# Dashboard schemas
class DashboardGroupResponse(BaseModel):
    id: int
    name: str
    invite_code: str
    teacher_name: str = ""
    student_count: int = 0

    class Config:
        from_attributes = True


class TodayScheduleResponse(BaseModel):
    id: int
    group_name: str
    day_of_week: DayOfWeek
    time_at: time
    meeting_link: Optional[str] = None

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    user_role: UserRole
    groups: List[DashboardGroupResponse]
    today_schedule: List[TodayScheduleResponse]
    active_homeworks: List[HomeworkResponse]

