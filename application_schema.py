from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidate_id: int = Field(..., description="ID of candidate")
    job_id: int = Field(..., description="ID of job description")


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    candidate_id: int
    job_id: int
    status: str
    applied_at: datetime
    candidate_name: Optional[str] = None
    job_title: Optional[str] = None
    candidate_skills: Optional[List[str]] = None
