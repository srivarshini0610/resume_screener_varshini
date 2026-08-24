from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import relationship
from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    raw_text = Column(LONGTEXT, nullable=False)
    skills = Column(JSON, nullable=True)
    experience = Column(JSON, nullable=True)
    education = Column(JSON, nullable=True)
    file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    evaluations = relationship(
        "Evaluation",
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    candidate_jobs = relationship(
        "CandidateJob",
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Alias for backward compatibility
    @property
    def applications(self):
        return self.candidate_jobs

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, full_name='{self.full_name}')>"
