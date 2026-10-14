import os
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.entities import JobRole, Candidate, CandidateMatch, Shortlist
from backend.app.schemas.schemas import GenerateDocxRequest, GenerateDocxResponse, GeneratePdfRequest
from backend.app.auth.dependencies import get_current_manager
from backend.app.services.document_service import create_shortlist_docx, create_shortlist_pdf, DOCUMENTS_DIR

router = APIRouter(prefix="/api/documents", tags=["Documents"])
logger = logging.getLogger("talentmatch.documents")

@router.post("/generate-pdf")
def generate_shortlist_pdf_endpoint(
    payload: GeneratePdfRequest,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Generates a professional PDF containing ONLY recruiter-selected shortlisted candidates.
    Returns the PDF directly as a downloadable file response.
    """
    logger.info(
        f"PDF Generation request received from manager ID={current_manager.id} ({current_manager.email}). "
        f"Selected candidate count: {len(payload.candidate_ids) if payload.candidate_ids else 0}, "
        f"Candidate IDs: {payload.candidate_ids}, Job Role ID: {payload.job_role_id}"
    )

    # 1. Validation: Candidate IDs non-empty
    if not payload.candidate_ids or len(payload.candidate_ids) == 0:
        logger.warning("PDF Generation rejected: No candidate IDs provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one candidate."
        )

    # 2. Fetch Job Role metadata if specified
    job_role = None
    if payload.job_role_id:
        job_role = db.query(JobRole).filter(JobRole.id == payload.job_role_id).first()
        if not job_role:
            logger.warning(f"Job role ID={payload.job_role_id} not found in database.")
            # We don't necessarily fail if candidates exist, but log warning

    # 3. Fetch Candidates from Database
    candidates = db.query(Candidate).filter(Candidate.id.in_(payload.candidate_ids)).all()
    if not candidates:
        logger.error(f"No candidates found in database for provided IDs: {payload.candidate_ids}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"None of the selected candidate IDs ({payload.candidate_ids}) were found in the database."
        )

    # Check for any missing IDs
    found_ids = {c.id for c in candidates}
    missing_ids = [cid for cid in payload.candidate_ids if cid not in found_ids]
    if missing_ids:
        logger.warning(f"Some selected candidate IDs were not found: {missing_ids}")

    # 4. Determine Metadata
    company_name = (
        job_role.company_name if job_role
        else (current_manager.company_name if current_manager and current_manager.company_name else "TalentMatch Recruiter")
    )
    role_name = job_role.role_name if job_role else "Campus Recruitment Drive"
    
    if job_role and job_role.college:
        college_name = job_role.college.name
    elif candidates and candidates[0].college:
        college_name = candidates[0].college.name
    else:
        college_name = "Campus Placement Drive"

    # 5. Build candidates data list
    candidates_data = []
    for cand in candidates:
        match_rec = None
        if job_role:
            match_rec = db.query(CandidateMatch).filter(
                CandidateMatch.candidate_id == cand.id,
                CandidateMatch.job_role_id == job_role.id
            ).first()
        else:
            match_rec = db.query(CandidateMatch).filter(
                CandidateMatch.candidate_id == cand.id
            ).order_by(CandidateMatch.match_score.desc()).first()

        sl_rec = None
        if job_role:
            sl_rec = db.query(Shortlist).filter(
                Shortlist.candidate_id == cand.id,
                Shortlist.job_role_id == job_role.id
            ).first()
        else:
            sl_rec = db.query(Shortlist).filter(
                Shortlist.candidate_id == cand.id
            ).first()

        # Matched skills
        if match_rec and match_rec.matched_skills:
            try:
                matched_skills = json.loads(match_rec.matched_skills) if isinstance(match_rec.matched_skills, str) else match_rec.matched_skills
            except Exception:
                matched_skills = [s.skill_name for s in cand.skills]
        else:
            matched_skills = [s.skill_name for s in cand.skills]

        # Missing skills / gap
        if match_rec and match_rec.missing_skills:
            try:
                missing_skills = json.loads(match_rec.missing_skills) if isinstance(match_rec.missing_skills, str) else match_rec.missing_skills
            except Exception:
                missing_skills = []
        else:
            missing_skills = []

        match_score = float(match_rec.match_score) if match_rec else 75.0
        recruitment_status = sl_rec.status if sl_rec else "Shortlisted"

        candidates_data.append({
            "id": cand.id,
            "name": cand.name,
            "candidate_code": cand.candidate_code,
            "email": cand.email,
            "phone": cand.phone,
            "department": cand.department,
            "cgpa": cand.cgpa,
            "match_score": match_score,
            "status": recruitment_status,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        })

    # Sort candidates by match score descending
    candidates_data.sort(key=lambda x: x["match_score"], reverse=True)

    # 6. Generate PDF
    try:
        logger.info(f"PDF generation started for {len(candidates_data)} selected candidate(s)...")
        pdf_bytes = create_shortlist_pdf(
            company_name=company_name,
            college_name=college_name,
            role_name=role_name,
            candidates_data=candidates_data
        )
        logger.info(f"PDF generation completed successfully ({len(pdf_bytes)} bytes).")
    except Exception as exc:
        logger.error(f"Error occurred during PDF generation: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(exc)}"
        )

    # 7. Return downloadable PDF file response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="TalentMatch_Shortlisted_Candidates.pdf"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.post("/shortlist", response_model=GenerateDocxResponse)
def generate_shortlist_document(
    payload: GenerateDocxRequest,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Generates a professional Word Document (.docx) for recruiter-selected shortlisted candidates.
    """
    job_role = db.query(JobRole).filter(JobRole.id == payload.job_role_id).first()
    if not job_role:
        raise HTTPException(status_code=404, detail="Job role not found")

    candidates = db.query(Candidate).filter(Candidate.id.in_(payload.candidate_ids)).all()
    if not candidates:
        raise HTTPException(status_code=400, detail="No valid candidates selected")

    college_name = job_role.college.name if job_role.college else (candidates[0].college.name if candidates[0].college else "Campus Recruitment")

    candidates_data = []
    for cand in candidates:
        match_rec = db.query(CandidateMatch).filter(
            CandidateMatch.candidate_id == cand.id,
            CandidateMatch.job_role_id == job_role.id
        ).first()

        sl_rec = db.query(Shortlist).filter(
            Shortlist.candidate_id == cand.id,
            Shortlist.job_role_id == job_role.id
        ).first()

        matched_skills = json.loads(match_rec.matched_skills) if (match_rec and match_rec.matched_skills) else [s.skill_name for s in cand.skills]
        missing_skills = json.loads(match_rec.missing_skills) if (match_rec and match_rec.missing_skills) else []

        projects = [{"project_name": p.project_name, "description": p.description} for p in cand.projects]
        internships = [{"company": i.company, "description": i.description} for i in cand.internships]
        certifications = [{"name": c.name} for c in cand.certifications]

        candidates_data.append({
            "name": cand.name,
            "candidate_code": cand.candidate_code,
            "email": cand.email,
            "phone": cand.phone,
            "department": cand.department,
            "cgpa": cand.cgpa,
            "match_score": match_rec.match_score if match_rec else 75.0,
            "status": sl_rec.status if sl_rec else "Shortlisted",
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "projects": projects,
            "internships": internships,
            "certifications": certifications,
            "ai_explanation": match_rec.ai_explanation if match_rec else "Candidate demonstrated strong skills alignment."
        })

    # Sort candidates by match score descending
    candidates_data.sort(key=lambda x: x["match_score"], reverse=True)

    file_path, filename = create_shortlist_docx(
        company_name=job_role.company_name,
        college_name=college_name,
        role_name=job_role.role_name,
        candidates_data=candidates_data,
        include_full_details=payload.include_full_details
    )

    logger.info(f"Generated shortlist DOCX: {filename} with {len(candidates_data)} candidates")

    return GenerateDocxResponse(
        message="Shortlist document generated successfully",
        filename=filename,
        download_url=f"/api/documents/shortlist/{filename}/download",
        candidate_count=len(candidates_data)
    )

@router.get("/shortlist/{filename}/download")
def download_shortlist_docx(
    filename: str,
    current_manager = Depends(get_current_manager)
):
    """
    Downloads the generated Word Document (.docx).
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(DOCUMENTS_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested document not found or expired")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
