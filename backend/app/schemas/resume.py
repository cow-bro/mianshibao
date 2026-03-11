from __future__ import annotations

from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    summary: str | None = None


class EducationExperience(BaseModel):
    school: str
    degree: str | None = None
    major: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class WorkExperience(BaseModel):
    company: str
    position: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProjectExperience(BaseModel):
    project_name: str
    role: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ResumeStructured(BaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    education_experiences: list[EducationExperience] = Field(default_factory=list)
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    project_experiences: list[ProjectExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ResumeScoreResult(BaseModel):
    overall_score: float
    dimension_scores: dict[str, float]
    suggestions: str


class ResumeOptimizeResult(BaseModel):
    optimized_content: str
    optimized_file_url: str | None = None
