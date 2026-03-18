import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class LearningStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    READING = "READING"
    MASTERED = "MASTERED"


class KnowledgeLearningProgress(Base, BaseModelMixin):
    __tablename__ = "knowledge_learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_learning_progress"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_point.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[LearningStatus] = mapped_column(
        Enum(LearningStatus, name="knowledge_learning_status", native_enum=False),
        default=LearningStatus.UNREAD,
        nullable=False,
    )
    read_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="knowledge_learning_progress")
    knowledge_point = relationship("KnowledgePoint", back_populates="learning_progress")
