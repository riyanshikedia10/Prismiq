"""
Pydantic models for all data structures flowing through the pipeline.
Provides validation, serialization, and documentation in a single place.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class Importance(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class ExperienceLevel(str, Enum):
    ENTRY = "Entry"
    MID = "Mid"
    SENIOR = "Senior"


class SkillCategory(str, Enum):
    TECHNICAL = "Technical"
    BEHAVIORAL = "Behavioral"


class ResourceType(str, Enum):
    COURSE = "Course"
    BOOK = "Book"
    TOOL = "Tool"
    ARTICLE = "Article"


# ── Data Models ──────────────────────────────────────────────────────────────

class Skill(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = "Technical"
    importance: str = "Medium"
    company: Optional[str] = None
    role: Optional[str] = None
    source: Optional[str] = None
    frequency: Optional[int] = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class InterviewRound(BaseModel):
    name: str = Field(..., min_length=1)
    order: int = Field(..., ge=1)
    duration_min: int = Field(default=45, ge=10, le=180)
    skills_tested: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)
    round: str = ""
    difficulty: str = "Medium"
    skills_tested: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(
        default_factory=lambda: ["Entry", "Mid", "Senior"]
    )
    source: Optional[str] = None
    source_url: Optional[str] = None
    acceptance: Optional[str] = None


class LearningResource(BaseModel):
    name: str = Field(..., min_length=1)
    url: str = ""
    skill: str = ""
    type: str = "Article"


class CompanyData(BaseModel):
    """Full GPT-extracted data for one (role, company) pair."""
    rounds: list[InterviewRound] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    sample_questions: list[InterviewQuestion] = Field(default_factory=list)
    learning_resources: list[LearningResource] = Field(default_factory=list)


# ── LLM Response Models ──────────────────────────────────────────────────────

class GeneratedQuestion(BaseModel):
    """Response from the question generator."""
    question: str = Field(..., min_length=5)
    skills_tested: list[str] = Field(default_factory=list)
    difficulty: str = "Medium"
    round: str = ""
    hints: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Response from the answer evaluator."""
    score: int = Field(default=5, ge=1, le=10)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ideal_answer: str = ""
    skills_to_improve: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    recommended_resources: list[str] = Field(default_factory=list)


# ── Exceptions ───────────────────────────────────────────────────────────────

class PrismiqError(Exception):
    """Base exception for all Prismiq errors."""


class ConfigError(PrismiqError):
    """Raised when required configuration is missing or invalid."""


class ExtractionError(PrismiqError):
    """Raised when data extraction fails."""


class KGConnectionError(PrismiqError):
    """Raised when Neo4j connection fails."""


class KGQueryError(PrismiqError):
    """Raised when a Cypher query fails."""


class LLMError(PrismiqError):
    """Raised when an OpenAI API call fails after retries."""
