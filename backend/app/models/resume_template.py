import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BaseModelMixin


class ResumeQualityLevel(str, enum.Enum):
    EXCELLENT = "EXCELLENT"
    POOR = "POOR"


class ResumeTemplate(Base, BaseModelMixin):
    __tablename__ = "resume_template"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    quality_level: Mapped[ResumeQualityLevel] = mapped_column(
        Enum(ResumeQualityLevel, name="resume_quality_level", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    analysis: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
