import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class UserRole(str, enum.Enum):
    USER = "USER"
    VIP = "VIP"
    ADMIN = "ADMIN"


class User(Base, BaseModelMixin):
    __tablename__ = "user"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    interview_sessions = relationship(
        "InterviewSession", back_populates="user", cascade="all, delete-orphan"
    )
    wrong_questions = relationship(
        "WrongQuestion", back_populates="user", cascade="all, delete-orphan"
    )
