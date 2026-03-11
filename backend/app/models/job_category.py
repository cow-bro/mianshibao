from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class JobCategory(Base, BaseModelMixin):
    """岗位大类表 — 顶层分类，如 互联网技术、金融、经管、市场营销."""

    __tablename__ = "job_category"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    positions = relationship(
        "JobPosition", back_populates="category", cascade="all, delete-orphan"
    )
