import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(ROOT_ENV):
    load_dotenv(dotenv_path=ROOT_ENV, override=True)
else:
    load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("talentmatch")

from backend.app.database import engine, Base
from backend.app.routers import (
    auth,
    candidates,
    colleges,
    job_roles,
    matching,
    shortlists,
    documents,
    stats,
    assessments,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist
    logger.info("Initializing TalentMatch database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("TalentMatch API server started and database tables verified.")
    yield
    # Shutdown
    logger.info("TalentMatch API server shutting down.")

app = FastAPI(
    title="TalentMatch API",
    description="AI-Powered Resume Screening & Candidate Ranking System for Campus Recruitment",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8000",
]

# Add Vercel deployment URL if available
VERCEL_URL = os.getenv("VERCEL_URL")
if VERCEL_URL:
    ALLOWED_ORIGINS.append(f"https://{VERCEL_URL}")

VERCEL_PROJECT_DOMAIN = os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
if VERCEL_PROJECT_DOMAIN:
    ALLOWED_ORIGINS.append(f"https://{VERCEL_PROJECT_DOMAIN}")

env_origins = os.getenv("ALLOWED_ORIGINS")
if env_origins:
    ALLOWED_ORIGINS.extend([origin.strip() for origin in env_origins.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(colleges.router)
app.include_router(job_roles.router)
app.include_router(matching.router)
app.include_router(shortlists.router)
app.include_router(documents.router)
app.include_router(stats.router)
app.include_router(assessments.router)

# Health Check Endpoint
@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "TalentMatch API",
        "version": "1.0.0"
    }

# Global Exception Handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.method} {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )
