import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class InterviewMessageRole(str, enum.Enum):
    INTERVIEWER = "INTERVIEWER"
    CANDIDATE = "CANDIDATE"


class InterviewMessage(Base, BaseModelMixin):
    __tablename__ = "interview_message"

    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[InterviewMessageRole] = mapped_column(
        Enum(InterviewMessageRole, name="interview_message_role", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship("InterviewSession", back_populates="messages")
