from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base


class CandidateJob(Base):
    __tablename__ = "candidate_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job"),
    )

    # Relationships
    candidate = relationship("Candidate", back_populates="candidate_jobs")
    job = relationship("JobDescription", back_populates="candidate_jobs")

    # Backward compatibility properties
    @property
    def applied_at(self):
        return self.created_at

    @property
    def status(self):
        return "APPLIED"

    def __repr__(self) -> str:
        return f"<CandidateJob(candidate_id={self.candidate_id}, job_id={self.job_id})>"


# Alias for backward compatibility
CandidateApplication = CandidateJob
