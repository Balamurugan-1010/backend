from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.models.entities import Assessment, Candidate, JobRole
from backend.app.auth.dependencies import get_current_manager

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])

class AssessmentCreate(BaseModel):
    candidate_id: int
    job_role_id: int
    assessment_type: str = "Technical Coding Round"
    score: float = 0.0
    status: str = "Scheduled"

class AssessmentUpdate(BaseModel):
    score: Optional[float] = None
    status: Optional[str] = None

@router.get("")
def get_assessments(
    job_role_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    query = db.query(Assessment)
    if job_role_id:
        query = query.filter(Assessment.job_role_id == job_role_id)
    items = query.order_by(desc(Assessment.created_at)).all()
    results = []
    for a in items:
        results.append({
            "id": a.id,
            "candidate_id": a.candidate_id,
            "candidate_code": a.candidate.candidate_code if a.candidate else "",
            "candidate_name": a.candidate.name if a.candidate else "",
            "department": a.candidate.department if a.candidate else "",
            "cgpa": a.candidate.cgpa if a.candidate else 0.0,
            "job_role_id": a.job_role_id,
            "role_name": a.job_role.role_name if a.job_role else "",
            "assessment_type": a.assessment_type,
            "score": a.score,
            "status": a.status,
            "created_at": a.created_at
        })
    return results

@router.post("")
def create_assessment(
    payload: AssessmentCreate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    ass = Assessment(
        candidate_id=payload.candidate_id,
        job_role_id=payload.job_role_id,
        assessment_type=payload.assessment_type,
        score=payload.score,
        status=payload.status
    )
    db.add(ass)
    db.commit()
    db.refresh(ass)
    return {"message": "Assessment scheduled", "id": ass.id}

@router.put("/{id}")
def update_assessment(
    id: int,
    payload: AssessmentUpdate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    ass = db.query(Assessment).filter(Assessment.id == id).first()
    if not ass:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if payload.score is not None:
        ass.score = payload.score
    if payload.status is not None:
        ass.status = payload.status
    db.commit()
    return {"message": "Assessment updated"}
