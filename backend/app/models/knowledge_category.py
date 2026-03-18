from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class KnowledgeCategory(Base, BaseModelMixin):
    __tablename__ = "knowledge_category"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_category.id", ondelete="CASCADE"), nullable=True
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent = relationship("KnowledgeCategory", remote_side="KnowledgeCategory.id", back_populates="children")
    children = relationship("KnowledgeCategory", back_populates="parent", cascade="all, delete-orphan")
    knowledge_points = relationship("KnowledgePoint", back_populates="category_ref")
