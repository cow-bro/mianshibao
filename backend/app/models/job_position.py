import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class PositionLevel(str, enum.Enum):
    INTERN = "INTERN"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"


class JobPosition(Base, BaseModelMixin):
    """具体岗位表 — 如 Java后端开发、前端开发、产品经理."""

    __tablename__ = "job_position"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("job_category.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[PositionLevel] = mapped_column(
        Enum(PositionLevel, name="position_level", native_enum=False),
        default=PositionLevel.JUNIOR,
        nullable=False,
    )
    required_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("JobCategory", back_populates="positions")
    knowledge_links = relationship(
        "PositionKnowledge", back_populates="position", cascade="all, delete-orphan"
    )
    interview_sessions = relationship(
        "InterviewSession", back_populates="position"
    )
