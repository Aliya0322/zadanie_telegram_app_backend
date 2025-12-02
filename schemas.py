from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, time
from models import UserRole, DayOfWeek


# User schemas
class UserBase(BaseModel):
    tgId: int = Field(alias="tg_id")
    role: UserRole
    timezone: str = "UTC"
    firstName: Optional[str] = Field(None, alias="first_name")
    lastName: Optional[str] = Field(None, alias="last_name")
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    isActive: bool = Field(alias="is_active")
    createdAt: datetime = Field(alias="created_at")

    class Config:
        from_attributes = True
        populate_by_name = True


class UserUpdate(BaseModel):
    firstName: str = Field(alias="first_name")
    lastName: str = Field(alias="last_name")
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    timezone: str  # Обязательное поле - пользователь должен указать вручную

    class Config:
        populate_by_name = True


# Group schemas
class GroupBase(BaseModel):
    name: str


class GroupCreate(GroupBase):
    pass


class GroupResponse(GroupBase):
    id: int
    teacherId: int = Field(alias="teacher_id")
    inviteCode: str = Field(alias="invite_code")
    isActive: bool = Field(alias="is_active")
    createdAt: datetime = Field(alias="created_at")
    students: List[int] = []

    class Config:
        from_attributes = True
        populate_by_name = True


class GroupUpdate(BaseModel):
    """Схема для обновления названия группы."""
    name: str


class GroupStatusUpdate(BaseModel):
    """Схема для обновления статуса группы."""
    isActive: bool = Field(alias="is_active")

    class Config:
        populate_by_name = True


class GroupResponseWithInvite(GroupResponse):
    """Расширенный ответ с ссылкой-приглашением."""
    inviteLink: str = Field(alias="invite_link")


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
    groupId: int = Field(alias="group_id")
    createdAt: datetime = Field(alias="created_at")
    reminderSent: bool = Field(alias="reminder_sent")

    class Config:
        from_attributes = True
        populate_by_name = True


# Schedule schemas
class ScheduleBase(BaseModel):
    dayOfWeek: DayOfWeek = Field(alias="day_of_week")
    timeAt: time = Field(alias="time_at")
    duration: Optional[int] = None  # Продолжительность в минутах
    meetingLink: Optional[str] = Field(None, alias="meeting_link")

    class Config:
        populate_by_name = True


class ScheduleCreate(ScheduleBase):
    groupId: int = Field(alias="group_id")

    class Config:
        populate_by_name = True


class ScheduleUpdate(BaseModel):
    """Схема для обновления расписания. Все поля опциональные."""
    dayOfWeek: Optional[DayOfWeek] = Field(None, alias="day_of_week")
    timeAt: Optional[time] = Field(None, alias="time_at")
    duration: Optional[int] = None
    meetingLink: Optional[str] = Field(None, alias="meeting_link")

    class Config:
        populate_by_name = True


class ScheduleResponse(ScheduleBase):
    id: int
    groupId: int = Field(alias="group_id")

    class Config:
        from_attributes = True
        populate_by_name = True


# Combined response schemas
class UserScheduleResponse(BaseModel):
    schedules: List[ScheduleResponse]
    activeHomeworks: List[HomeworkResponse] = Field(alias="active_homeworks")

    class Config:
        populate_by_name = True


# Auth schemas
class LoginResponse(BaseModel):
    user: UserResponse
    isNewUser: bool = Field(alias="is_new_user")
    message: str

    class Config:
        populate_by_name = True


# Dashboard schemas
class DashboardGroupResponse(BaseModel):
    id: int
    name: str
    inviteCode: str = Field(alias="invite_code")
    teacherName: str = Field(default="", alias="teacher_name")
    studentCount: int = Field(default=0, alias="student_count")

    class Config:
        from_attributes = True
        populate_by_name = True


class TodayScheduleResponse(BaseModel):
    id: int
    groupName: str = Field(alias="group_name")
    dayOfWeek: DayOfWeek = Field(alias="day_of_week")
    timeAt: time = Field(alias="time_at")
    meetingLink: Optional[str] = Field(None, alias="meeting_link")

    class Config:
        from_attributes = True
        populate_by_name = True


class DashboardResponse(BaseModel):
    userRole: UserRole = Field(alias="user_role")
    groups: List[DashboardGroupResponse]
    todaySchedule: List[TodayScheduleResponse] = Field(alias="today_schedule")
    activeHomeworks: List[HomeworkResponse] = Field(alias="active_homeworks")

    class Config:
        populate_by_name = True

