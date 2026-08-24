from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Create SQLAlchemy engine for MySQL
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

# Create SessionLocal factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative Base for ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and ensures proper cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Create all tables defined in Base metadata in the database,
    and execute safe, idempotent migrations for job_number and JobCounter.
    """
    import app.models  # noqa: F401
    from sqlalchemy import text, inspect, func
    from app.models.job_description import JobDescription, JobCounter

    # 1. Create all missing tables (including job_counters)
    Base.metadata.create_all(bind=engine)

    # 2. Check and migrate job_descriptions table for job_number column
    with engine.connect() as conn:
        inspector = inspect(conn)
        columns = [c["name"] for c in inspector.get_columns("job_descriptions")] if "job_descriptions" in inspector.get_table_names() else []
        
        if "job_descriptions" in inspector.get_table_names() and "job_number" not in columns:
            conn.execute(text("ALTER TABLE job_descriptions ADD COLUMN job_number INT NULL;"))
            conn.commit()

    # 3. Backfill existing jobs with permanent sequential job_numbers (1, 2, 3, ...)
    db = SessionLocal()
    try:
        jobs = db.query(JobDescription).order_by(JobDescription.created_at.asc(), JobDescription.id.asc()).all()
        
        # Check if any jobs need numbering
        assigned_numbers = set()
        next_num = 1
        for job in jobs:
            if job.job_number is not None and job.job_number > 0:
                assigned_numbers.add(job.job_number)
                next_num = max(next_num, job.job_number + 1)
        
        for job in jobs:
            if job.job_number is None or job.job_number <= 0:
                while next_num in assigned_numbers:
                    next_num += 1
                job.job_number = next_num
                assigned_numbers.add(next_num)
                next_num += 1

        db.commit()

        # 4. Synchronize JobCounter
        max_job_num = db.query(func.max(JobDescription.job_number)).scalar() or 0
        counter = db.query(JobCounter).filter(JobCounter.id == 1).first()
        if not counter:
            counter = JobCounter(id=1, last_job_number=max_job_num)
            db.add(counter)
        else:
            if counter.last_job_number < max_job_num:
                counter.last_job_number = max_job_num
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning during job_number migration: {e}")
    finally:
        db.close()
