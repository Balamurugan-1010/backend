import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.entities import (
    Candidate, College, Resume, CandidateSkill, Project, Internship, Certification
)
from backend.app.schemas.schemas import CandidateCreate, CandidateOut, ProjectItem, InternshipItem, CertificationItem
from backend.app.services.resume_service import (
    process_and_save_resume, generate_candidate_code
)
from backend.app.auth.dependencies import get_current_manager

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])
logger = logging.getLogger("talentmatch.candidates")

def candidate_to_out(c: Candidate) -> CandidateOut:
    skills = [s.skill_name for s in c.skills]
    projects = [ProjectItem(project_name=p.project_name, description=p.description) for p in c.projects]
    internships = [InternshipItem(company=i.company, description=i.description, duration=i.duration) for i in c.internships]
    certifications = [CertificationItem(name=crt.name, issuer=crt.issuer) for crt in c.certifications]
    has_res = c.resume is not None

    return CandidateOut(
        id=c.id,
        candidate_code=c.candidate_code,
        name=c.name,
        email=c.email,
        phone=c.phone,
        college_id=c.college_id,
        college_name=c.college.name if c.college else "Unknown College",
        department=c.department,
        graduation_year=c.graduation_year,
        cgpa=c.cgpa,
        areas_of_interest=c.areas_of_interest or "",
        created_at=c.created_at,
        skills=skills,
        projects=projects,
        internships=internships,
        certifications=certifications,
        has_resume=has_res
    )

# ----------------- PUBLIC STUDENT REGISTRATION -----------------
@router.post("", response_model=CandidateOut)
def register_candidate(payload: CandidateCreate, db: Session = Depends(get_db)):
    """
    Public student details submission.
    No login required for students.
    """
    logger.info(f"New student registration request for: {payload.email}")
    # Check or create College
    if payload.college_name and payload.college_name.strip():
        college_clean = payload.college_name.strip()
        college = db.query(College).filter(College.name.ilike(college_clean)).first()
        if not college:
            college = College(name=college_clean, location="Tamil Nadu, India")
            db.add(college)
            db.commit()
            db.refresh(college)
    else:
        # Default to first partner college
        college = db.query(College).first()
        if not college:
            college = College(name="Dr. Mahalingam College of Engineering and Technology", location="Pollachi, Coimbatore")
            db.add(college)
            db.commit()
            db.refresh(college)

    dept = payload.department.strip() if (payload.department and payload.department.strip()) else "Computer Science and Engineering"
    grad_year = payload.graduation_year if payload.graduation_year else 2026
    cgpa_val = round(float(payload.cgpa), 2) if payload.cgpa is not None else 8.0

    code = generate_candidate_code(db)
    new_candidate = Candidate(
        candidate_code=code,
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        phone=payload.phone.strip(),
        college_id=college.id,
        department=dept,
        graduation_year=grad_year,
        cgpa=cgpa_val,
        areas_of_interest=payload.areas_of_interest or ""
    )
    db.add(new_candidate)
    db.commit()
    db.refresh(new_candidate)

    # Save initial skills if provided
    if payload.skills:
        for s in payload.skills:
            if s and s.strip():
                db.add(CandidateSkill(candidate_id=new_candidate.id, skill_name=s.strip()))

    # Save initial projects if provided
    if payload.projects:
        for p in payload.projects:
            if p.project_name and p.project_name.strip():
                db.add(Project(candidate_id=new_candidate.id, project_name=p.project_name.strip(), description=p.description or ""))

    # Save initial internships if provided
    if payload.internships:
        for i in payload.internships:
            if i.company and i.company.strip():
                db.add(Internship(candidate_id=new_candidate.id, company=i.company.strip(), description=i.description or "", duration=i.duration or ""))

    # Save initial certifications if provided
    if payload.certifications:
        for c in payload.certifications:
            if c.name and c.name.strip():
                db.add(Certification(candidate_id=new_candidate.id, name=c.name.strip(), issuer=c.issuer or ""))

    db.commit()
    db.refresh(new_candidate)
    logger.info(f"Candidate registered successfully: {new_candidate.candidate_code} (ID: {new_candidate.id})")
    return candidate_to_out(new_candidate)

@router.post("/{candidate_id}/resume")
async def upload_candidate_resume(
    candidate_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Public resume upload for candidate.
    Extracts text, skills, and sections automatically.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    logger.info(f"Processing resume upload for Candidate {candidate.candidate_code} ({file.filename})")
    resume_record = await process_and_save_resume(file, candidate_id, db)
    db.refresh(candidate)

    return {
        "message": "Resume submitted and parsed successfully",
        "candidate_id": candidate.id,
        "candidate_code": candidate.candidate_code,
        "original_filename": resume_record.original_filename,
        "extracted_skills_count": len(candidate.skills),
        "skills": [s.skill_name for s in candidate.skills]
    }

# ----------------- PROTECTED MANAGER ENDPOINTS -----------------
@router.get("", response_model=List[CandidateOut])
def get_all_candidates(
    college_id: Optional[int] = None,
    department: Optional[str] = None,
    min_cgpa: Optional[float] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    query = db.query(Candidate)

    if college_id:
        query = query.filter(Candidate.college_id == college_id)
    if department and department != "All":
        query = query.filter(Candidate.department == department)
    if min_cgpa:
        query = query.filter(Candidate.cgpa >= min_cgpa)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Candidate.name.ilike(s)) |
            (Candidate.email.ilike(s)) |
            (Candidate.candidate_code.ilike(s)) |
            (Candidate.department.ilike(s))
        )

    candidates = query.order_by(desc(Candidate.created_at)).all()
    return [candidate_to_out(c) for c in candidates]

@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate_by_id(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate_to_out(c)

@router.get("/{candidate_id}/resume/download")
def download_candidate_resume(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Secure authenticated resume download for recruiters.
    """
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not c or not c.resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found for this candidate")

    file_path = c.resume.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume file missing from storage")

    return FileResponse(
        path=file_path,
        filename=f"{c.candidate_code}_{c.name.replace(' ', '_')}_Resume.pdf",
        media_type="application/pdf"
    )
