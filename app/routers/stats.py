from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.entities import Candidate, College, JobRole, Shortlist
from backend.app.schemas.schemas import DashboardStatsOut
from backend.app.auth.dependencies import get_current_manager
from backend.app.routers.candidates import candidate_to_out

router = APIRouter(prefix="/api/stats", tags=["Dashboard Statistics"])

@router.get("/dashboard", response_model=DashboardStatsOut)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    total_candidates = db.query(Candidate).count()
    total_colleges = db.query(College).count()
    active_job_roles = db.query(JobRole).count()
    shortlisted_candidates = db.query(Shortlist).count()

    recent_cand_records = db.query(Candidate).order_by(desc(Candidate.created_at)).limit(5).all()
    recent_submissions = [candidate_to_out(c) for c in recent_cand_records]

    colleges = db.query(College).all()
    top_colleges = []
    for col in colleges:
        count = db.query(Candidate).filter(Candidate.college_id == col.id).count()
        top_colleges.append({
            "id": col.id,
            "name": col.name,
            "candidates_count": count
        })
    top_colleges.sort(key=lambda x: x["candidates_count"], reverse=True)

    return DashboardStatsOut(
        total_candidates=total_candidates,
        total_colleges=total_colleges,
        active_job_roles=active_job_roles,
        shortlisted_candidates=shortlisted_candidates,
        recent_submissions=recent_submissions,
        top_colleges=top_colleges[:5]
    )
