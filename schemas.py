from pydantic import BaseModel, Field, model_serializer, field_validator
from typing import Optional, List, Union
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


class UserResponse(BaseModel):
    id: int
    tgId: int = Field(alias="tg_id")
    role: UserRole
    timezone: str
    firstName: Optional[str] = Field(None, alias="first_name")
    lastName: Optional[str] = Field(None, alias="last_name")
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    isActive: bool = Field(alias="is_active")
    createdAt: datetime = Field(alias="created_at")

    class Config:
        from_attributes = True
        populate_by_name = True
    
    @model_serializer
    def ser_model(self):
        # Сериализуем с именами полей (camelCase), а не alias'ами
        return {
            "id": self.id,
            "tgId": self.tgId,
            "role": self.role,
            "timezone": self.timezone,
            "firstName": self.firstName,
            "lastName": self.lastName,
            "patronymic": self.patronymic,
            "birthdate": self.birthdate.isoformat() if self.birthdate else None,  # Явно обрабатываем None и datetime
            "isActive": self.isActive,
            "createdAt": self.createdAt.isoformat() if isinstance(self.createdAt, datetime) else self.createdAt
        }


class UserUpdate(BaseModel):
    firstName: str = Field(alias="first_name")
    lastName: str = Field(alias="last_name")
    patronymic: Optional[str] = None
    birthdate: Optional[Union[datetime, str]] = None  # Принимаем и строку, и datetime
    timezone: str  # Обязательное поле - пользователь должен указать вручную

    class Config:
        populate_by_name = True
    
    @field_validator('birthdate', mode='before')
    @classmethod
    def parse_birthdate(cls, v):
        """Принимает строку ISO или datetime и преобразует в datetime."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                # Убираем пробелы
                v = v.strip()
                # Заменяем Z на +00:00 для fromisoformat
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except (ValueError, AttributeError):
                raise ValueError(f"Invalid date format: {v}. Expected ISO format (e.g., '2025-12-03T15:39:30.662Z')")
        raise ValueError(f"Invalid birthdate type: {type(v)}. Expected string or datetime.")


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
    
    @model_serializer
    def ser_model(self):
        # Сериализуем с именами полей (camelCase), а не alias'ами
        return {
            "id": self.id,
            "name": self.name,
            "teacherId": self.teacherId,
            "inviteCode": self.inviteCode,
            "isActive": self.isActive,
            "createdAt": self.createdAt.isoformat() if isinstance(self.createdAt, datetime) else self.createdAt,
            "students": self.students
        }


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
    inviteLink: str

    class Config:
        populate_by_name = True
    
    @model_serializer
    def ser_model(self):
        # Получаем базовые поля от родителя и добавляем inviteLink
        base_dict = super().ser_model()
        base_dict["inviteLink"] = self.inviteLink
        return base_dict


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


class ScheduleResponse(BaseModel):
    id: int
    groupId: int = Field(alias="group_id")
    dayOfWeek: DayOfWeek = Field(alias="day_of_week")
    timeAt: time = Field(alias="time_at")
    duration: Optional[int] = None
    meetingLink: Optional[str] = Field(None, alias="meeting_link")

    class Config:
        from_attributes = True
        populate_by_name = True
    
    @model_serializer
    def ser_model(self):
        # Сериализуем с именами полей (camelCase), а не alias'ами
        return {
            "id": self.id,
            "groupId": self.groupId,
            "dayOfWeek": self.dayOfWeek,
            "timeAt": self.timeAt,
            "duration": self.duration,
            "meetingLink": self.meetingLink
        }


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
    
    @model_serializer
    def ser_model(self):
        # Сериализуем с именами полей (camelCase), а не alias'ами
        # timeAt нужно сериализовать как строку (HH:MM:SS), чтобы фронтенд мог использовать .split()
        return {
            "id": self.id,
            "groupName": self.groupName,
            "dayOfWeek": self.dayOfWeek,
            "timeAt": str(self.timeAt) if self.timeAt else None,  # Преобразуем time в строку
            "meetingLink": self.meetingLink
        }


class DashboardResponse(BaseModel):
    userRole: UserRole = Field(alias="user_role")
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    patronymic: Optional[str] = None
    birthdate: Optional[datetime] = None
    groups: List[DashboardGroupResponse]
    todaySchedule: List[TodayScheduleResponse]
    activeHomeworks: List[HomeworkResponse]

    class Config:
        populate_by_name = True

