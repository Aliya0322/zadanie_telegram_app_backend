from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, DateTime, Boolean, Time, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base


class UserRole(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    timezone = Column(String, default="UTC")
    
    # Personal Info
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    patronymic = Column(String, nullable=True)
    birthdate = Column(DateTime(timezone=True), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    groups_as_teacher = relationship("Group", back_populates="teacher", foreign_keys="Group.teacher_id")
    group_memberships = relationship("GroupMember", back_populates="student")
    completed_homeworks = relationship("HomeworkCompletion", back_populates="student")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    invite_code = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)  # False = группа приостановлена
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    teacher = relationship("User", back_populates="groups_as_teacher", foreign_keys=[teacher_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    homeworks = relationship("Homework", back_populates="group", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="members")
    student = relationship("User", back_populates="group_memberships")


class Homework(Base):
    __tablename__ = "homework"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reminder_sent = Column(Boolean, default=False)

    # Relationships
    group = relationship("Group", back_populates="homeworks")
    completions = relationship("HomeworkCompletion", back_populates="homework", cascade="all, delete-orphan")


class HomeworkCompletion(Base):
    __tablename__ = "homework_completions"

    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    homework = relationship("Homework", back_populates="completions")
    student = relationship("User", back_populates="completed_homeworks")


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(SQLEnum(DayOfWeek), nullable=False)
    time_at = Column(Time, nullable=False)
    duration = Column(Integer, nullable=True)  # Продолжительность в минутах
    meeting_link = Column(String, nullable=True)  # Zoom/Google Meet link

    # Relationships
    group = relationship("Group", back_populates="schedules")

