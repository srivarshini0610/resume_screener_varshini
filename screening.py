from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.candidate import Candidate
from app.models.job_description import JobDescription
from app.models.evaluation import Evaluation
from app.models.candidate_job import CandidateJob
from app.schemas.evaluation_schema import (
    ScreeningRequest,
    EvaluationResponse,
    ScreeningBatchResponse,
)
from app.services.screening_engine import evaluate_candidate_against_job

router = APIRouter()


def _build_evaluation_response(eval_record: Evaluation) -> EvaluationResponse:
    """Helper to convert Evaluation ORM record to EvaluationResponse schema with candidate_name."""
    cand_name = eval_record.candidate.full_name if eval_record.candidate else None
    return EvaluationResponse(
        id=eval_record.id,
        candidate_id=eval_record.candidate_id,
        candidate_name=cand_name,
        job_id=eval_record.job_id,
        match_score=float(eval_record.match_score),
        justification=eval_record.justification,
        matching_skills=eval_record.matching_skills or [],
        missing_skills=eval_record.missing_skills or [],
        strengths=eval_record.strengths or [],
        weaknesses=eval_record.weaknesses or [],
        status=str(eval_record.status.value if hasattr(eval_record.status, "value") else eval_record.status),
        evaluated_at=eval_record.evaluated_at,
    )


@router.post(
    "/evaluate",
    response_model=ScreeningBatchResponse,
    summary="Screen selected candidates against a target Job Description",
)
def screen_candidates(
    request: ScreeningRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates ONLY candidates who belong to the selected job description.
    Never evaluates all candidates across the entire database indiscriminately.
    """
    # 1. Validate Job exists
    job = db.query(JobDescription).filter(JobDescription.id == request.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {request.job_id} not found.",
        )

    # 2. Determine target candidates associated with this Job
    if request.candidate_ids and len(request.candidate_ids) > 0:
        valid_links = (
            db.query(CandidateJob)
            .filter(
                CandidateJob.job_id == job.id,
                CandidateJob.candidate_id.in_(request.candidate_ids),
            )
            .all()
        )
        if valid_links:
            valid_cand_ids = [link.candidate_id for link in valid_links]
            candidates = db.query(Candidate).filter(Candidate.id.in_(valid_cand_ids)).all()
        else:
            # Fallback for explicit candidate IDs
            candidates = db.query(Candidate).filter(Candidate.id.in_(request.candidate_ids)).all()
            for cand in candidates:
                existing_link = (
                    db.query(CandidateJob)
                    .filter(
                        CandidateJob.candidate_id == cand.id,
                        CandidateJob.job_id == job.id,
                    )
                    .first()
                )
                if not existing_link:
                    db.add(CandidateJob(candidate_id=cand.id, job_id=job.id))
            db.commit()

        if not candidates:
            return ScreeningBatchResponse(job_id=job.id, evaluations=[])
    else:
        # Retrieve all candidates associated with this specific job
        candidate_links = (
            db.query(CandidateJob)
            .filter(CandidateJob.job_id == job.id)
            .all()
        )
        if not candidate_links:
            return ScreeningBatchResponse(job_id=job.id, evaluations=[])

        associated_cand_ids = [link.candidate_id for link in candidate_links]
        candidates = (
            db.query(Candidate)
            .filter(Candidate.id.in_(associated_cand_ids))
            .all()
        )
        if not candidates:
            return ScreeningBatchResponse(job_id=job.id, evaluations=[])

    # 3. Evaluate each target candidate (skipping LLM if cached in evaluations table)
    evaluated_records = []
    for cand in candidates:
        try:
            eval_record = evaluate_candidate_against_job(cand.id, job.id, db)
            evaluated_records.append(eval_record)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error screening candidate '{cand.full_name}' (ID: {cand.id}): {str(e)}",
            )

    # 4. Sort evaluations descending by match_score
    evaluated_records.sort(key=lambda x: float(x.match_score), reverse=True)

    # 5. Format response
    response_list = [_build_evaluation_response(rec) for rec in evaluated_records]
    return ScreeningBatchResponse(
        job_id=job.id,
        evaluations=response_list,
    )


@router.get(
    "/results/{job_id}",
    response_model=List[EvaluationResponse],
    summary="Get all ranked candidate evaluation results for a job",
)
def get_screening_results(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns only evaluation records that exist for the specific job, sorted by match_score descending.
    """
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {job_id} not found.",
        )

    evaluations = (
        db.query(Evaluation)
        .filter(Evaluation.job_id == job_id)
        .order_by(desc(Evaluation.match_score))
        .all()
    )

    return [_build_evaluation_response(rec) for rec in evaluations]


@router.get(
    "/evaluation/{evaluation_id}",
    response_model=EvaluationResponse,
    summary="Get single evaluation record details by ID",
)
def get_single_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns full evaluation details and justification by primary key evaluation_id.
    """
    eval_record = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not eval_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation record with ID {evaluation_id} not found.",
        )

    return _build_evaluation_response(eval_record)
