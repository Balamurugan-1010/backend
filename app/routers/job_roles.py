import os
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.entities import JobRole, JobRequiredSkill, College
from backend.app.schemas.schemas import JobRoleCreate, JobRoleOut, JobSkillInput
from backend.app.auth.dependencies import get_current_manager
from backend.app.services.resume_service import extract_text_from_pdf_bytes
from backend.app.ml.skill_extraction import extract_skills_from_text, normalize_skill

router = APIRouter(prefix="/api/job-roles", tags=["Job Roles"])
logger = logging.getLogger("talentmatch.job_roles")

# On Vercel serverless, only /tmp is writable
if os.getenv("VERCEL"):
    JD_UPLOAD_DIR = "/tmp/uploads/jd"
else:
    JD_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "jd"))
os.makedirs(JD_UPLOAD_DIR, exist_ok=True)

def role_to_out(r: JobRole) -> JobRoleOut:
    skills = [JobSkillInput(skill_name=s.skill_name, required=s.required) for s in r.required_skills]
    return JobRoleOut(
        id=r.id,
        manager_id=r.manager_id,
        college_id=r.college_id,
        company_name=r.company_name,
        role_name=r.role_name,
        job_description=r.job_description,
        minimum_cgpa=r.minimum_cgpa,
        eligible_departments=r.eligible_departments or "",
        experience_requirement=r.experience_requirement or "",
        created_at=r.created_at,
        required_skills=skills
    )

@router.get("", response_model=List[JobRoleOut])
def get_all_job_roles(
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    roles = db.query(JobRole).order_by(desc(JobRole.created_at)).all()
    return [role_to_out(r) for r in roles]

@router.get("/{id}", response_model=JobRoleOut)
def get_job_role_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    role = db.query(JobRole).filter(JobRole.id == id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found")
    return role_to_out(role)

@router.post("", response_model=JobRoleOut)
def create_job_role(
    payload: JobRoleCreate,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    logger.info(f"Creating job role: {payload.role_name} for company: {payload.company_name}")
    new_role = JobRole(
        manager_id=current_manager.id,
        college_id=payload.college_id,
        company_name=payload.company_name.strip(),
        role_name=payload.role_name.strip(),
        job_description=payload.job_description.strip(),
        minimum_cgpa=float(payload.minimum_cgpa),
        eligible_departments=payload.eligible_departments.strip(),
        experience_requirement=payload.experience_requirement or "Freshers / 0-1 Years"
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)

    # Add required & preferred skills with normalization
    for item in payload.required_skills:
        clean_skill = normalize_skill(item.skill_name)
        if clean_skill:
            db.add(JobRequiredSkill(
                job_role_id=new_role.id,
                skill_name=clean_skill,
                required=item.required
            ))
    db.commit()
    db.refresh(new_role)
    return role_to_out(new_role)

@router.post("/parse-jd-pdf")
async def parse_jd_pdf(
    file: UploadFile = File(...),
    current_manager = Depends(get_current_manager)
):
    """
    Extracts text and auto-detects technical skills from an uploaded Job Description PDF.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF JD files are supported")

    content = await file.read()
    extracted_text = extract_text_from_pdf_bytes(content)
    detected_skills = extract_skills_from_text(extracted_text)

    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "detected_skills": detected_skills
    }

@router.delete("/{id}")
def delete_job_role(
    id: int,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    role = db.query(JobRole).filter(JobRole.id == id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Job role not found")
    db.delete(role)
    db.commit()
    return {"message": "Job role deleted successfully"}
