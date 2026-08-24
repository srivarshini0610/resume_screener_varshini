from sqlalchemy.orm import Session
from app.models.candidate import Candidate
from app.models.job_description import JobDescription
from app.models.evaluation import Evaluation, EvaluationStatus
from app.services.llm_service import evaluate_candidate


def evaluate_candidate_against_job(
    candidate_id: int,
    job_id: int,
    db: Session,
) -> Evaluation:
    """
    Evaluates a specific candidate against a target job description.
    Reuses existing evaluations if already present in MySQL database, avoiding redundant LLM API calls.
    If not previously evaluated, invokes Llama 3.1 8B matching and persists the new evaluation record.

    Args:
        candidate_id: Primary key of Candidate.
        job_id: Primary key of JobDescription.
        db: Active SQLAlchemy Session.

    Returns:
        The saved or existing Evaluation ORM record.

    Raises:
        ValueError: If candidate or job does not exist.
        RuntimeError: If database persistence fails.
    """
    # 1. Retrieve Candidate
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise ValueError(f"Candidate with ID {candidate_id} does not exist.")

    # 2. Retrieve JobDescription
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise ValueError(f"Job Description with ID {job_id} does not exist.")

    # 3. Check for existing evaluation to avoid redundant LLM calls
    existing_eval = (
        db.query(Evaluation)
        .filter(
            Evaluation.candidate_id == candidate_id,
            Evaluation.job_id == job_id,
        )
        .first()
    )

    if existing_eval is not None:
        print(f"[SCREENING] Candidate {candidate_id} already evaluated for Job {job_id} - skipping LLM", flush=True)
        return existing_eval

    # 4. If no existing evaluation, invoke LLM
    print(f"[SCREENING] Candidate {candidate_id} has no evaluation for Job {job_id} - running LLM", flush=True)
    llm_result = evaluate_candidate(candidate, job)

    # 5. Map recommendation to EvaluationStatus enum
    rec_str = str(llm_result.recommendation).upper()
    if rec_str == "SHORTLISTED":
        status_enum = EvaluationStatus.SHORTLISTED
    elif rec_str == "REJECTED":
        status_enum = EvaluationStatus.REJECTED
    else:
        status_enum = EvaluationStatus.REVIEW

    # 6. Save new evaluation record in MySQL
    try:
        evaluation_record = Evaluation(
            candidate_id=candidate_id,
            job_id=job_id,
            match_score=llm_result.match_score,
            justification=llm_result.justification,
            matching_skills=llm_result.matching_skills,
            missing_skills=llm_result.missing_skills,
            strengths=llm_result.strengths,
            weaknesses=llm_result.weaknesses,
            status=status_enum,
        )
        db.add(evaluation_record)
        db.commit()
        db.refresh(evaluation_record)
        return evaluation_record

    except Exception as db_err:
        db.rollback()
        raise RuntimeError(f"Database error while saving evaluation: {str(db_err)}") from db_err
