import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class MasteryLevel(str, enum.Enum):
    UNFAMILIAR = "UNFAMILIAR"
    FAMILIAR = "FAMILIAR"
    MASTERED = "MASTERED"


class WrongQuestion(Base, BaseModelMixin):
    __tablename__ = "wrong_question"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_point.id", ondelete="CASCADE"), nullable=False
    )
    mastery_level: Mapped[MasteryLevel] = mapped_column(
        Enum(MasteryLevel, name="mastery_level", native_enum=False),
        default=MasteryLevel.UNFAMILIAR,
        nullable=False,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="wrong_questions")
    knowledge_point = relationship("KnowledgePoint", back_populates="wrong_questions")
