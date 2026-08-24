from datetime import datetime
from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class ExperienceItem(BaseModel):
    """Structured model for candidate work experience, internships, and projects."""
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="", description="Type of experience: 'job', 'internship', 'project', etc.")
    title: str = Field(default="", description="Job title, role, or project title")
    company_or_organization: str = Field(default="", description="Company, organization, or client name")
    duration: str = Field(default="", description="Duration or dates of the role/project")
    description: str = Field(default="", description="Key responsibilities or summary of work")
    technologies: List[str] = Field(default_factory=list, description="Technologies, tools, and libraries used")


class EducationItem(BaseModel):
    """Structured model for candidate educational background."""
    model_config = ConfigDict(extra="ignore")

    degree: str = Field(default="", description="Degree, certificate, or level (e.g. 'B.Tech', 'XII', 'X')")
    field: str = Field(default="", description="Field of study, major, or stream")
    institution: str = Field(default="", description="School, college, or university name")
    duration: str = Field(default="", description="Years attended or graduation year")
    grade: str = Field(default="", description="CGPA, GPA, percentage, or score")


class CandidateProfile(BaseModel):
    """Structured candidate profile extracted from a resume."""
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(default="", description="Full name of candidate")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Contact phone number")
    skills: List[str] = Field(default_factory=list, description="List of technical/domain skills")
    experience: List[ExperienceItem] = Field(
        default_factory=list, description="List of structured work experience or project records"
    )
    education: List[EducationItem] = Field(
        default_factory=list, description="List of structured educational qualifications"
    )


# Alias for backward compatibility with llm_service
CandidateParsedProfile = CandidateProfile


class CandidateResponse(BaseModel):
    """Schema returned after a candidate is stored in the database."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = None
    experience: Optional[List[Union[ExperienceItem, dict, str, Any]]] = None
    education: Optional[List[Union[EducationItem, dict, str, Any]]] = None
    file_path: Optional[str] = None
    created_at: datetime
