import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
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
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_position.id", ondelete="SET NULL"), nullable=True
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
    interview_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_interview_duration: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    max_total_questions: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    max_resume_dig_questions: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    max_tech_qa_questions: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    is_human_intervention_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_intervention_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    human_operator_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    user = relationship(
        "User",
        back_populates="interview_sessions",
        foreign_keys=[user_id],
    )
    human_operator = relationship(
        "User",
        foreign_keys=[human_operator_id],
    )
    resume = relationship("Resume", back_populates="interview_sessions")
    position = relationship("JobPosition", back_populates="interview_sessions")
    messages = relationship(
        "InterviewMessage", back_populates="session", cascade="all, delete-orphan"
    )
    report = relationship("InterviewReport", uselist=False, back_populates="session")
