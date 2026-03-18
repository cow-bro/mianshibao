from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class KnowledgeBookmark(Base, BaseModelMixin):
    __tablename__ = "knowledge_bookmark"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_bookmark"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_point.id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="knowledge_bookmarks")
    knowledge_point = relationship("KnowledgePoint", back_populates="bookmarks")
