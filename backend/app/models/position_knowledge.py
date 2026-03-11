import enum

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class KnowledgeRelevance(str, enum.Enum):
    CORE = "CORE"
    IMPORTANT = "IMPORTANT"
    OPTIONAL = "OPTIONAL"


class PositionKnowledge(Base, BaseModelMixin):
    """岗位-知识点关联表 — 多对多关系，标注知识点对岗位的重要程度."""

    __tablename__ = "position_knowledge"
    __table_args__ = (
        UniqueConstraint("position_id", "knowledge_point_id", name="uq_position_knowledge"),
    )

    position_id: Mapped[int] = mapped_column(
        ForeignKey("job_position.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_point.id", ondelete="CASCADE"), nullable=False
    )
    relevance: Mapped[KnowledgeRelevance] = mapped_column(
        Enum(KnowledgeRelevance, name="knowledge_relevance", native_enum=False),
        default=KnowledgeRelevance.IMPORTANT,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    position = relationship("JobPosition", back_populates="knowledge_links")
    knowledge_point = relationship("KnowledgePoint", back_populates="position_links")
