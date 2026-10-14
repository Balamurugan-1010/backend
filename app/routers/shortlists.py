import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.entities import Shortlist, Candidate, JobRole, CandidateMatch
from backend.app.schemas.schemas import ShortlistCreate, ShortlistStatusUpdate, ShortlistOut
from backend.app.auth.dependencies import get_current_manager

router = APIRouter(prefix="/api/shortlists", tags=["Shortlists"])
logger = logging.getLogger("talentmatch.shortlists")

VALID_STATUSES = ["Shortlisted", "Assessment", "Interview", "Selected", "Rejected"]

def shortlist_to_out(s: Shortlist, db: Session) -> ShortlistOut:
    match = db.query(CandidateMatch).filter(
        CandidateMatch.candidate_id == s.candidate_id,
        CandidateMatch.job_role_id == s.job_role_id
    ).first()

    return ShortlistOut(
        id=s.id,
        candidate_id=s.candidate.id,
        candidate_code=s.candidate.candidate_code,
        candidate_name=s.candidate.name,
        email=s.candidate.email,
        phone=s.candidate.phone,
        college_name=s.candidate.college.name if s.candidate.college else "",
        department=s.candidate.department,
        cgpa=s.candidate.cgpa,
        job_role_id=s.job_role.id,
        role_name=s.job_role.role_name,
        company_name=s.job_role.company_name,
        status=s.status,
        match_score=match.match_score if match else 0.0,
        shortlisted_at=s.shortlisted_at,
        updated_at=s.updated_at
    )

@router.post("", response_model=List[ShortlistOut])
def create_shortlist(
    payload: ShortlistCreate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Shortlist single or multiple candidates for a job role.
    """
    job_role = db.query(JobRole).filter(JobRole.id == payload.job_role_id).first()
    if not job_role:
        raise HTTPException(status_code=404, detail="Job role not found")

    created = []
    for cand_id in payload.candidate_ids:
        existing = db.query(Shortlist).filter(
            Shortlist.candidate_id == cand_id,
            Shortlist.job_role_id == payload.job_role_id
        ).first()

        if existing:
            existing.status = payload.status or "Shortlisted"
            existing.updated_at = datetime.utcnow()
            sl_entry = existing
        else:
            sl_entry = Shortlist(
                candidate_id=cand_id,
                job_role_id=payload.job_role_id,
                manager_id=current_manager.id,
                status=payload.status or "Shortlisted"
            )
            db.add(sl_entry)
        created.append(sl_entry)

    db.commit()
    for s in created:
        db.refresh(s)

    return [shortlist_to_out(s, db) for s in created]

@router.get("", response_model=List[ShortlistOut])
def get_all_shortlists(
    job_role_id: Optional[int] = None,
    college_id: Optional[int] = None,
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    query = db.query(Shortlist).join(Candidate)

    if job_role_id:
        query = query.filter(Shortlist.job_role_id == job_role_id)
    if college_id:
        query = query.filter(Candidate.college_id == college_id)
    if department and department != "All":
        query = query.filter(Candidate.department == department)
    if status_filter and status_filter != "All":
        query = query.filter(Shortlist.status == status_filter)

    items = query.order_by(desc(Shortlist.shortlisted_at)).all()
    return [shortlist_to_out(s, db) for s in items]

@router.put("/{id}", response_model=ShortlistOut)
def update_shortlist_status(
    id: int,
    payload: ShortlistStatusUpdate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")

    sl = db.query(Shortlist).filter(Shortlist.id == id).first()
    if not sl:
        raise HTTPException(status_code=404, detail="Shortlist record not found")

    sl.status = payload.status
    sl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sl)
    return shortlist_to_out(sl, db)

@router.delete("/{id}")
def delete_shortlist(
    id: int,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    sl = db.query(Shortlist).filter(Shortlist.id == id).first()
    if not sl:
        raise HTTPException(status_code=404, detail="Shortlist entry not found")
    db.delete(sl)
    db.commit()
    return {"message": "Candidate removed from shortlist"}
