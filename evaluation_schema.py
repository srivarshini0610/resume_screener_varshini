from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class EvaluationResult(BaseModel):
    """Pydantic schema representing the structured evaluation result from the LLM."""
    match_score: float = Field(..., ge=1.0, le=10.0, description="Match score from 1.0 to 10.0")
    justification: str = Field(..., description="Detailed explanation of the score")
    matching_skills: List[str] = Field(default_factory=list, description="Skills meeting job requirements")
    missing_skills: List[str] = Field(default_factory=list, description="Required skills not present in resume")
    strengths: List[str] = Field(default_factory=list, description="Key candidate strengths for this role")
    weaknesses: List[str] = Field(default_factory=list, description="Key candidate gaps or limitations")
    recommendation: str = Field(..., description="Recommendation: SHORTLISTED, REVIEW, or REJECTED")

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in {"SHORTLISTED", "REVIEW", "REJECTED"}:
            raise ValueError("Recommendation must be exactly 'SHORTLISTED', 'REVIEW', or 'REJECTED'.")
        return cleaned

    @field_validator("match_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(float(v), 1)


class ScreeningRequest(BaseModel):
    """Request payload for screening candidates against a job description."""
    job_id: int = Field(..., description="Target Job Description ID")
    candidate_ids: Optional[List[int]] = Field(
        default=None, description="Optional list of Candidate IDs to screen (evaluates all if omitted or empty)"
    )


# Alias for backward compatibility
EvaluationRequest = ScreeningRequest


class EvaluationResponse(BaseModel):
    """Schema returned for a single candidate evaluation record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    candidate_name: Optional[str] = None
    job_id: int
    match_score: float
    justification: str
    matching_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    status: str
    evaluated_at: datetime


class ScreeningBatchResponse(BaseModel):
    """Batch screening response returning ranked evaluations for a job."""
    job_id: int
    evaluations: List[EvaluationResponse]
