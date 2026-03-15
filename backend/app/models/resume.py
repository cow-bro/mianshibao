from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class Resume(Base, BaseModelMixin):
    __tablename__ = "resume"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parsed_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimension_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="resumes")
    interview_sessions = relationship(
        "InterviewSession", back_populates="resume", cascade="all, delete-orphan"
    )
