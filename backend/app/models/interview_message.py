import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
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
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship("InterviewSession", back_populates="messages")
