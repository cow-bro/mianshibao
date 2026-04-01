from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


class InterviewStage(str, Enum):
    WELCOME = "WELCOME"
    RESUME_DIG = "RESUME_DIG"
    TECH_QA = "TECH_QA"
    CANDIDATE_QUESTION = "CANDIDATE_QUESTION"
    END = "END"
    HUMAN_INTERVENTION_WAITING = "HUMAN_INTERVENTION_WAITING"
    HUMAN_INTERVENTION_IN_PROGRESS = "HUMAN_INTERVENTION_IN_PROGRESS"


class WebSocketMessageType(str, Enum):
    ANSWER = "ANSWER"
    SKIP = "SKIP"
    END_INTERVIEW = "END_INTERVIEW"
    TOKEN = "token"
    MESSAGE = "message"
    STATE_CHANGE = "state_change"
    REPORT_READY = "report_ready"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class InterviewStartRequest(BaseModel):
    resume_id: int | None = None
    position_id: int | None = None
    target_company: str | None = None
    target_position: str | None = None
    job_description: str = ""
    max_total_questions: int = Field(default=12, ge=3, le=30)
    max_resume_dig_questions: int = Field(default=4, ge=1, le=15)
    max_tech_qa_questions: int = Field(default=6, ge=1, le=15)
    max_interview_duration: int = Field(default=3600, ge=300, le=7200)


class InterviewStartResponse(BaseModel):
    session_id: int
    status: str
    current_stage: InterviewStage


class InterviewHumanInterventionRequest(BaseModel):
    message: str | None = None
    operator_id: int | None = None


class AnswerScore(BaseModel):
    question_index: int
    question: str
    answer: str
    score: float = Field(..., ge=0, le=10)
    dimension: str
    comment: str


class InterviewReport(BaseModel):
    session_id: str
    user_id: str
    target_company: str
    target_position: str
    interview_duration_seconds: int
    total_questions: int

    overall_score: float = Field(..., ge=0, le=100)
    professional_knowledge_score: float = Field(..., ge=0, le=100)
    project_experience_score: float = Field(..., ge=0, le=100)
    logical_thinking_score: float = Field(..., ge=0, le=100)
    communication_score: float = Field(..., ge=0, le=100)
    position_match_score: float = Field(..., ge=0, le=100)

    highlights: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    recommended_knowledge_points: list[dict] = Field(default_factory=list)
    interview_summary: str
    generated_at: datetime


class InterviewState(TypedDict):
    session_id: str
    user_id: str
    resume_id: str
    target_company: str
    target_position: str
    job_description: str
    status: Literal["INIT", "ONGOING", "ENDED"]

    current_stage: InterviewStage
    current_question_index: int
    resume_dig_question_count: int
    tech_qa_question_count: int
    candidate_question_rounds: int
    max_total_questions: int
    max_resume_dig_questions: int
    max_tech_qa_questions: int
    interview_start_time: str
    interview_duration_seconds: int
    max_interview_duration: int

    parsed_resume: dict
    current_resume_focus: str | None
    current_tech_stack_focus: list[str] | None

    message_history: list[dict]
    current_question: str | None
    current_answer: str | None
    answer_quality_scores: list[dict]

    is_human_intervention_enabled: bool
    human_intervention_status: InterviewStage | None
    human_operator_id: str | None

    created_at: str
    updated_at: str
    rag_retrieved_knowledge: NotRequired[list[dict]]
    report: NotRequired[dict]
    trace_id: NotRequired[str]
    _next_node: NotRequired[str]
    _persisted_messages: NotRequired[int]
    opening_intro_requested: NotRequired[bool]
