from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class InterviewReport(Base, BaseModelMixin):
    __tablename__ = "interview_report"

    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    target_company: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    interview_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    professional_knowledge_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    project_experience_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    logical_thinking_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    communication_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position_match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    highlights: Mapped[list] = mapped_column(JSONB, nullable=False)
    weaknesses: Mapped[list] = mapped_column(JSONB, nullable=False)
    improvement_suggestions: Mapped[list] = mapped_column(JSONB, nullable=False)
    recommended_knowledge_points: Mapped[list] = mapped_column(JSONB, nullable=False)
    interview_summary: Mapped[str] = mapped_column(Text, nullable=False)
    answer_scores: Mapped[list] = mapped_column(JSONB, nullable=False)

    session = relationship("InterviewSession", back_populates="report")
    user = relationship("User")
