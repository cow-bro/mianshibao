import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class InterviewStatus(str, enum.Enum):
    INIT = "INIT"
    ONGOING = "ONGOING"
    ENDED = "ENDED"


class InterviewSession(Base, BaseModelMixin):
    __tablename__ = "interview_session"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume.id", ondelete="SET NULL"), nullable=True
    )
    target_company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status", native_enum=False),
        default=InterviewStatus.INIT,
        nullable=False,
    )
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user = relationship("User", back_populates="interview_sessions")
    resume = relationship("Resume", back_populates="interview_sessions")
    messages = relationship(
        "InterviewMessage", back_populates="session", cascade="all, delete-orphan"
    )
