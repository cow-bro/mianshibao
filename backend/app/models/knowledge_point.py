import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class KnowledgeScope(str, enum.Enum):
    GENERAL = "GENERAL"
    POSITION = "POSITION"


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
    scope: Mapped[KnowledgeScope] = mapped_column(
        Enum(KnowledgeScope, name="knowledge_scope", native_enum=False),
        default=KnowledgeScope.GENERAL,
        nullable=False,
    )
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
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_category.id", ondelete="SET NULL"), nullable=True
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    wrong_questions = relationship(
        "WrongQuestion", back_populates="knowledge_point", cascade="all, delete-orphan"
    )
    position_links = relationship(
        "PositionKnowledge", back_populates="knowledge_point", cascade="all, delete-orphan"
    )
    category_ref = relationship("KnowledgeCategory", back_populates="knowledge_points")
    owner = relationship("User", back_populates="personal_knowledge_points")
    bookmarks = relationship(
        "KnowledgeBookmark", back_populates="knowledge_point", cascade="all, delete-orphan"
    )
    learning_progress = relationship(
        "KnowledgeLearningProgress", back_populates="knowledge_point", cascade="all, delete-orphan"
    )
