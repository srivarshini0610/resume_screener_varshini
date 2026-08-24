import os
import re
import uuid
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job_description import JobDescription
from app.models.candidate_job import CandidateJob
from app.schemas.candidate_schema import CandidateResponse, CandidateProfile
from app.services.pdf_parser import extract_text_from_file
from app.services.llm_service import extract_candidate_profile

router = APIRouter()

# Uploads storage directory
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


@router.post(
    "/upload",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resume and auto-associate candidate with the active Job",
)
async def upload_resume(
    file: UploadFile = File(...),
    job_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Accepts a PDF or TXT resume, extracts raw text,
    structures candidate information with LLM (Llama 3.1 8B),
    persists or updates the candidate record, and automatically associates
    the candidate with the currently active job_id if provided.
    Does NOT trigger LLM screening evaluation automatically.
    """
    # 1. Validate filename and extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded or filename is missing.",
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Only .pdf and .txt files are allowed.",
        )

    # 2. Generate safe unique filename and save to uploads/
    sanitized_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    unique_filename = f"{uuid.uuid4().hex[:10]}_{sanitized_name}"
    saved_file_path = UPLOAD_DIR / unique_filename

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        async with aiofiles.open(saved_file_path, "wb") as out_file:
            await out_file.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file to disk: {str(e)}",
        )

    # 3. Extract text from the saved file
    try:
        raw_text = extract_text_from_file(str(saved_file_path))
    except ValueError as ve:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as ex:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document parsing error: {str(ex)}",
        )

    # 4. Extract structured profile using LLM
    try:
        extracted_data = extract_candidate_profile(raw_text)
        profile = CandidateProfile.model_validate(extracted_data)
    except ValueError as llm_err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Profile Extraction failed: {str(llm_err)}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during AI parsing: {str(err)}",
        )

    # 5. Persist Candidate into MySQL Database
    try:
        # Check if candidate with same email already exists to reuse profile
        candidate = None
        if profile.email and profile.email.strip():
            candidate = db.query(Candidate).filter(Candidate.email == profile.email.strip()).first()

        if candidate:
            # Update existing candidate details
            candidate.full_name = profile.full_name or candidate.full_name
            candidate.phone = profile.phone or candidate.phone
            candidate.skills = profile.skills or candidate.skills
            if profile.experience:
                candidate.experience = [item.model_dump() for item in profile.experience]
            if profile.education:
                candidate.education = [item.model_dump() for item in profile.education]
            candidate.raw_text = raw_text
            candidate.file_path = str(saved_file_path)
            db.commit()
            db.refresh(candidate)
        else:
            candidate = Candidate(
                full_name=profile.full_name or None,
                email=profile.email or None,
                phone=profile.phone or None,
                skills=profile.skills or [],
                experience=[item.model_dump() for item in profile.experience] if profile.experience else [],
                education=[item.model_dump() for item in profile.education] if profile.education else [],
                raw_text=raw_text,
                file_path=str(saved_file_path),
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

        # 6. Automatically associate candidate with active Job if job_id was provided
        if job_id is not None and int(job_id) > 0:
            target_job = db.query(JobDescription).filter(JobDescription.id == int(job_id)).first()
            if target_job:
                existing_link = (
                    db.query(CandidateJob)
                    .filter(
                        CandidateJob.candidate_id == candidate.id,
                        CandidateJob.job_id == target_job.id,
                    )
                    .first()
                )
                if not existing_link:
                    link = CandidateJob(
                        candidate_id=candidate.id,
                        job_id=target_job.id,
                    )
                    db.add(link)
                    db.commit()

    except Exception as db_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence error while saving candidate record: {str(db_err)}",
        )

    return candidate


@router.get(
    "/job/{job_id}",
    response_model=List[CandidateResponse],
    summary="Get all candidates associated with a specific Job Description",
)
def get_candidates_by_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Retrieves all candidates associated with the target job."""
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {job_id} not found.",
        )

    candidate_links = (
        db.query(CandidateJob)
        .filter(CandidateJob.job_id == job_id)
        .order_by(CandidateJob.created_at.asc())
        .all()
    )

    candidate_ids = [link.candidate_id for link in candidate_links]
    if not candidate_ids:
        return []

    candidates = (
        db.query(Candidate)
        .filter(Candidate.id.in_(candidate_ids))
        .all()
    )

    # Maintain chronological order of association
    cand_map = {c.id: c for c in candidates}
    return [cand_map[cid] for cid in candidate_ids if cid in cand_map]


@router.get(
    "/grouped-by-job",
    summary="Get all candidates grouped by their associated Job Roles",
)
def get_candidates_grouped_by_job(
    db: Session = Depends(get_db),
):
    """Retrieves all job descriptions along with their associated candidates."""
    jobs = db.query(JobDescription).order_by(JobDescription.created_at.asc()).all()
    all_candidates = db.query(Candidate).order_by(Candidate.id.asc()).all()
    cand_map = {c.id: c for c in all_candidates}

    all_links = db.query(CandidateJob).order_by(CandidateJob.created_at.asc()).all()

    # Map job_id -> list of candidate objects
    job_cand_map: Dict[int, List[Any]] = {j.id: [] for j in jobs}
    associated_cand_ids = set()

    for link in all_links:
        if link.job_id in job_cand_map and link.candidate_id in cand_map:
            job_cand_map[link.job_id].append(cand_map[link.candidate_id])
            associated_cand_ids.add(link.candidate_id)

    result = []
    for job in jobs:
        cands_for_job = job_cand_map.get(job.id, [])
        result.append({
            "job_id": job.id,
            "job_number": job.job_number,
            "job_title": job.title,
            "candidates": [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "email": c.email,
                    "skills": c.skills or [],
                }
                for c in cands_for_job
            ],
        })

    # Unassigned candidates (if any)
    unassigned = [
        {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "skills": c.skills or [],
        }
        for c in all_candidates
        if c.id not in associated_cand_ids
    ]

    return {
        "grouped_jobs": result,
        "unassigned_candidates": unassigned,
    }


@router.get(
    "/",
    response_model=List[CandidateResponse],
    summary="List all stored candidates",
)
def get_all_candidates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Retrieve all candidate records ordered by creation date."""
    candidates = (
        db.query(Candidate)
        .order_by(Candidate.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return candidates


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    summary="Get candidate profile by ID",
)
def get_candidate_by_id(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve a single candidate profile by primary key."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found.",
        )
    return candidate
