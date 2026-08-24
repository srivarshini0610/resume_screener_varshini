from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_tables
from app.routers import candidates, jobs, screening, applications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created
    create_tables()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="Smart Resume Screener API",
    description="AI-Powered Resume Screening and Candidate Matching API using Llama 3.1 8B, FastAPI, and MySQL.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(candidates.router, prefix="/api/candidates", tags=["Candidates"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["Applications"])
app.include_router(screening.router, prefix="/api/screening", tags=["Screening"])


@app.get("/", summary="Root endpoint")
def root():
    return {"message": "Smart Resume Screener API"}


@app.get("/health", summary="Health check endpoint")
def health_check():
    return {"status": "healthy"}
