from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class JobDescriptionExtract(BaseModel):
    """Structured job requirements extracted from JD text using LLM."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="Uploaded Job Description", description="Specific job title or 'Uploaded Job Description'")
    required_skills: List[str] = Field(default_factory=list, description="List of individual mandatory technical and professional skills")
    min_experience: Optional[str] = Field(default=None, description="Minimum required years or level of experience, or None")
    description_text: str = Field(default="", description="Comprehensive job description text or summary")


class JobDescriptionCreate(BaseModel):
    """Schema for creating a new job description."""
    title: str = Field(..., min_length=1, description="Job title")
    description_text: str = Field(..., min_length=1, description="Full job description text")
    required_skills: Optional[List[str]] = Field(
        default_factory=list, description="List of required technical skills"
    )
    min_experience: Optional[str] = Field(
        default=None, description="Minimum required experience, e.g., '2 years'"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Job title cannot be empty or whitespace only.")
        return v.strip()

    @field_validator("description_text")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Job description text cannot be empty or whitespace only.")
        return v.strip()


class JobDescriptionResponse(BaseModel):
    """Schema returned for job description details."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_number: int
    title: str
    description_text: str
    required_skills: Optional[List[str]] = None
    min_experience: Optional[str] = None
    created_at: datetime
