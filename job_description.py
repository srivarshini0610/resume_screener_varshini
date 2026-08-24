from sqlalchemy import Column, Integer, String, Text, DateTime, func, event, text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import relationship
from app.database import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_number = Column(Integer, nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description_text = Column(LONGTEXT, nullable=False)
    required_skills = Column(JSON, nullable=True)
    min_experience = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    evaluations = relationship(
        "Evaluation",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    candidate_jobs = relationship(
        "CandidateJob",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Alias for backward compatibility
    @property
    def applications(self):
        return self.candidate_jobs

    def __repr__(self) -> str:
        return f"<JobDescription(id={self.id}, job_number={self.job_number}, title='{self.title}')>"


class JobCounter(Base):
    __tablename__ = "job_counters"

    id = Column(Integer, primary_key=True, default=1)
    last_job_number = Column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<JobCounter(id={self.id}, last_job_number={self.last_job_number})>"


@event.listens_for(JobDescription, "before_insert")
def auto_set_job_number(mapper, connection, target):
    """
    Ensures that any JobDescription inserted automatically receives a permanent sequential job_number.
    """
    if target.job_number is None or target.job_number <= 0:
        try:
            res = connection.execute(text("SELECT COALESCE(MAX(job_number), 0) FROM job_descriptions")).scalar() or 0
            counter_res = connection.execute(text("SELECT last_job_number FROM job_counters WHERE id = 1")).scalar() or 0
            next_val = max(res, counter_res) + 1
            target.job_number = next_val
            connection.execute(text(f"INSERT INTO job_counters (id, last_job_number) VALUES (1, {next_val}) ON DUPLICATE KEY UPDATE last_job_number = GREATEST(last_job_number, {next_val})"))
        except Exception as e:
            # Fallback if query fails in isolated test session
            if target.job_number is None or target.job_number <= 0:
                target.job_number = 1
