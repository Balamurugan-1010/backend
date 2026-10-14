from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database import get_db
from backend.app.models.entities import College, Candidate
from backend.app.schemas.schemas import CollegeOut, CollegeCreate
from backend.app.auth.dependencies import get_current_manager

from collections import defaultdict

router = APIRouter(prefix="/api/colleges", tags=["Colleges"])

@router.get("", response_model=List[CollegeOut])
def get_colleges(db: Session = Depends(get_db)):
    colleges = db.query(College).order_by(College.name).all()
    all_candidates = db.query(Candidate.college_id, Candidate.cgpa, Candidate.department).all()
    cand_by_col = defaultdict(list)
    for c in all_candidates:
        cand_by_col[c.college_id].append(c)

    results = []
    for col in colleges:
        candidates = cand_by_col[col.id]
        total_cand = len(candidates)
        eligible_cand = sum(1 for c in candidates if c.cgpa >= 7.0)
        depts = sorted(list({c.department for c in candidates if c.department}))
        avg_cgpa = round(sum(c.cgpa for c in candidates) / total_cand, 2) if total_cand > 0 else 0.0

        results.append(CollegeOut(
            id=col.id,
            name=col.name,
            location=col.location,
            total_candidates=total_cand,
            eligible_candidates=eligible_cand,
            departments=depts,
            average_cgpa=avg_cgpa
        ))

    return results

@router.get("/{id}", response_model=CollegeOut)
def get_college(id: int, db: Session = Depends(get_db)):
    col = db.query(College).filter(College.id == id).first()
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="College not found")
    
    candidates = db.query(Candidate).filter(Candidate.college_id == col.id).all()
    total_cand = len(candidates)
    eligible_cand = sum(1 for c in candidates if c.cgpa >= 7.0)
    depts = sorted(list({c.department for c in candidates if c.department}))
    avg_cgpa = round(sum(c.cgpa for c in candidates) / total_cand, 2) if total_cand > 0 else 0.0

    return CollegeOut(
        id=col.id,
        name=col.name,
        location=col.location,
        total_candidates=total_cand,
        eligible_candidates=eligible_cand,
        departments=depts,
        average_cgpa=avg_cgpa
    )

@router.post("", response_model=CollegeOut)
def create_college(
    payload: CollegeCreate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    existing = db.query(College).filter(College.name == payload.name.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="College with this name already exists")
    col = College(name=payload.name.strip(), location=payload.location or "Tamil Nadu, India")
    db.add(col)
    db.commit()
    db.refresh(col)
    return CollegeOut(
        id=col.id,
        name=col.name,
        location=col.location,
        total_candidates=0,
        eligible_candidates=0,
        departments=[],
        average_cgpa=0.0
    )
