import enum
from sqlalchemy import Column, Integer, Text, DECIMAL, DateTime, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from app.database import Base


class EvaluationStatus(str, enum.Enum):
    SHORTLISTED = "SHORTLISTED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    match_score = Column(DECIMAL(3, 1), nullable=False)
    justification = Column(Text, nullable=False)
    matching_skills = Column(JSON, nullable=True)
    missing_skills = Column(JSON, nullable=True)
    strengths = Column(JSON, nullable=True)
    weaknesses = Column(JSON, nullable=True)
    status = Column(
        SQLEnum(EvaluationStatus, name="evaluation_status_enum", native_enum=True),
        nullable=False,
        default=EvaluationStatus.REVIEW,
    )
    evaluated_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    candidate = relationship("Candidate", back_populates="evaluations")
    job = relationship("JobDescription", back_populates="evaluations")

    def __repr__(self) -> str:
        return (
            f"<Evaluation(id={self.id}, candidate_id={self.candidate_id}, "
            f"job_id={self.job_id}, score={self.match_score}, status='{self.status}')>"
        )
