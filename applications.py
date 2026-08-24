from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job_description import JobDescription
from app.models.candidate_application import CandidateApplication
from app.schemas.application_schema import ApplicationCreate, ApplicationResponse

router = APIRouter()


def _format_application_response(app_record: CandidateApplication) -> ApplicationResponse:
    cand_name = app_record.candidate.full_name if app_record.candidate else None
    cand_skills = app_record.candidate.skills if app_record.candidate else []
    job_title = app_record.job.title if app_record.job else None
    return ApplicationResponse(
        id=app_record.id,
        candidate_id=app_record.candidate_id,
        job_id=app_record.job_id,
        status=app_record.status,
        applied_at=app_record.applied_at,
        candidate_name=cand_name,
        job_title=job_title,
        candidate_skills=cand_skills,
    )


@router.post(
    "/",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign/Apply candidate to a Job Description",
)
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a candidate-to-job application association.
    Prevents duplicate applications for the same candidate_id + job_id pair.
    """
    # 1. Validate Candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {payload.candidate_id} not found.",
        )

    # 2. Validate Job exists
    job = db.query(JobDescription).filter(JobDescription.id == payload.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {payload.job_id} not found.",
        )

    # 3. Check for existing application (prevent duplicates)
    existing_app = (
        db.query(CandidateApplication)
        .filter(
            CandidateApplication.candidate_id == payload.candidate_id,
            CandidateApplication.job_id == payload.job_id,
        )
        .first()
    )
    if existing_app:
        return _format_application_response(existing_app)

    # 4. Create new application
    new_app = CandidateApplication(
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        status="APPLIED",
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return _format_application_response(new_app)


@router.get(
    "/job/{job_id}",
    response_model=List[ApplicationResponse],
    summary="Get all candidates who applied to a specific Job Description",
)
def get_applications_by_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves all candidate applications associated with the given job_id."""
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {job_id} not found.",
        )

    applications = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.job_id == job_id)
        .order_by(CandidateApplication.created_at.asc())
        .all()
    )
    return [_format_application_response(app) for app in applications]


@router.get(
    "/candidate/{candidate_id}",
    response_model=List[ApplicationResponse],
    summary="Get all job roles a specific candidate applied to",
)
def get_applications_by_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves all job applications for a specific candidate."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found.",
        )

    applications = (
        db.query(CandidateApplication)
        .filter(CandidateApplication.candidate_id == candidate_id)
        .order_by(CandidateApplication.created_at.desc())
        .all()
    )
    return [_format_application_response(app) for app in applications]


@router.get(
    "/",
    response_model=List[ApplicationResponse],
    summary="Get all applications",
)
def get_all_applications(
    db: Session = Depends(get_db),
):
    """Retrieves all candidate applications across all jobs."""
    applications = (
        db.query(CandidateApplication)
        .order_by(CandidateApplication.applied_at.desc())
        .all()
    )
    return [_format_application_response(app) for app in applications]
