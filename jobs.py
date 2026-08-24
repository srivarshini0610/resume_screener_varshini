import re
import uuid
import aiofiles
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job_description import JobDescription, JobCounter
from app.schemas.job_schema import JobDescriptionCreate, JobDescriptionResponse
from app.services.pdf_parser import extract_text_from_file
from app.services.llm_service import extract_job_profile

router = APIRouter()

# Storage directory for uploaded documents
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def get_next_job_number(db: Session) -> int:
    """
    Computes the next permanent sequential job number: MAX(existing job_number or tracker) + 1.
    If no jobs exist, starts at 1.
    Guarantees numbers are never reused even after deletions.
    """
    counter = db.query(JobCounter).filter(JobCounter.id == 1).first()
    max_job_num = db.query(func.max(JobDescription.job_number)).scalar() or 0
    last_val = counter.last_job_number if counter else 0

    next_num = max(max_job_num, last_val) + 1

    if counter:
        counter.last_job_number = next_num
    else:
        counter = JobCounter(id=1, last_job_number=next_num)
        db.add(counter)

    return next_num


@router.post(
    "/",
    response_model=JobDescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new job description manually",
)
def create_job_description(
    job_in: JobDescriptionCreate,
    db: Session = Depends(get_db),
):
    """
    Creates and stores a new job description record in the database from manual form input.
    """
    try:
        next_job_num = get_next_job_number(db)
        job = JobDescription(
            job_number=next_job_num,
            title=job_in.title,
            description_text=job_in.description_text,
            required_skills=job_in.required_skills or [],
            min_experience=job_in.min_experience,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence error while creating job description: {str(e)}",
        )


@router.post(
    "/upload",
    response_model=JobDescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a Job Description document (PDF or TXT)",
)
async def upload_job_description(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accepts a PDF or TXT Job Description document, extracts raw text using PyMuPDF / UTF-8,
    extracts structured requirements (title, skills, experience) using Llama 3.1 8B,
    and creates a new JobDescription database record.
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

    # 2. Save uploaded file to disk
    sanitized_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    unique_filename = f"jd_{uuid.uuid4().hex[:10]}_{sanitized_name}"
    saved_file_path = UPLOAD_DIR / unique_filename

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded Job Description file is empty (0 bytes).",
            )

        async with aiofiles.open(saved_file_path, "wb") as out_file:
            await out_file.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded JD file to disk: {str(e)}",
        )

    # 3. Extract text from the saved file using existing parser
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

    # 4. Extract structured JD profile using LLM
    try:
        extracted_data = extract_job_profile(raw_text)
    except ValueError as llm_err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Job Specification Extraction failed: {str(llm_err)}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during AI JD parsing: {str(err)}",
        )

    # 5. Persist JobDescription into MySQL Database
    try:
        next_job_num = get_next_job_number(db)
        job = JobDescription(
            job_number=next_job_num,
            title=extracted_data["title"],
            description_text=extracted_data["description_text"],
            required_skills=extracted_data.get("required_skills") or [],
            min_experience=extracted_data.get("min_experience"),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as db_err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database persistence error while saving job description: {str(db_err)}",
        )


@router.get(
    "/",
    response_model=List[JobDescriptionResponse],
    summary="Retrieve all job descriptions",
)
def get_all_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Returns a list of all stored job descriptions ordered by creation date.
    """
    try:
        jobs = (
            db.query(JobDescription)
            .order_by(JobDescription.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return jobs
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job descriptions from database.",
        )


@router.get(
    "/{job_id}",
    response_model=JobDescriptionResponse,
    summary="Get a single job description by ID",
)
def get_job_by_id(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns the full details of a specific job description by primary key ID.
    """
    try:
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job description with ID {job_id} not found.",
            )
        return job
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching job description.",
        )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a job description by ID",
)
def delete_job_by_id(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Deletes a job description record and its associated candidate links and evaluations.
    """
    try:
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job description with ID {job_id} not found.",
            )
        db.delete(job)
        db.commit()
        return {"message": f"Job description with ID {job_id} deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while deleting job description: {str(e)}",
        )
