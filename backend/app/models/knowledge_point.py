import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class KnowledgePointType(str, enum.Enum):
    KNOWLEDGE = "KNOWLEDGE"
    QUESTION = "QUESTION"


class DifficultyLevel(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class KnowledgePoint(Base, BaseModelMixin):
    __tablename__ = "knowledge_point"

    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[KnowledgePointType] = mapped_column(
        Enum(KnowledgePointType, name="knowledge_point_type", native_enum=False),
        nullable=False,
    )
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level", native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    wrong_questions = relationship(
        "WrongQuestion", back_populates="knowledge_point", cascade="all, delete-orphan"
    )
