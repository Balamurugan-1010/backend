import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.entities import (
    Candidate, JobRole, College, CandidateMatch, Shortlist, CandidateSkill
)
from backend.app.schemas.schemas import (
    MatchingRunRequest, CandidateMatchOut, CompareRequest, CompareCandidateOut, CandidateOut
)
from backend.app.auth.dependencies import get_current_manager
from backend.app.ml.matching import matching_engine
from backend.app.routers.candidates import candidate_to_out

router = APIRouter(prefix="/api/matching", tags=["AI Matching"])
logger = logging.getLogger("talentmatch.matching")

@router.post("/run", response_model=List[CandidateMatchOut])
def run_ai_matching(
    payload: MatchingRunRequest,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Executes AI Screening and Candidate Ranking for the selected Job Role and College.
    """
    job_role = db.query(JobRole).filter(JobRole.id == payload.job_role_id).first()
    if not job_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found")

    # Filter candidates by college if college_id is specified
    query = db.query(Candidate)
    if payload.college_id:
        query = query.filter(Candidate.college_id == payload.college_id)

    candidates = query.all()
    if not candidates:
        return []

    required_skills = [s.skill_name for s in job_role.required_skills if s.required]
    preferred_skills = [s.skill_name for s in job_role.required_skills if not s.required]

    job_data = {
        "role_name": job_role.role_name,
        "company_name": job_role.company_name,
        "job_description": job_role.job_description,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "minimum_cgpa": job_role.minimum_cgpa,
        "eligible_departments": job_role.eligible_departments or ""
    }

    results: List[CandidateMatchOut] = []

    # Get existing shortlists for this job role to attach status
    shortlists = {
        s.candidate_id: s for s in db.query(Shortlist).filter(Shortlist.job_role_id == job_role.id).all()
    }

    for cand in candidates:
        cand_skills = [s.skill_name for s in cand.skills]
        cand_projects = [{"project_name": p.project_name, "description": p.description} for p in cand.projects]
        cand_internships = [{"company": i.company, "description": i.description, "duration": i.duration} for i in cand.internships]
        resume_text = cand.resume.extracted_text if cand.resume else ""

        cand_data = {
            "name": cand.name,
            "skills": cand_skills,
            "resume_text": resume_text,
            "projects": cand_projects,
            "internships": cand_internships,
            "cgpa": cand.cgpa,
            "department": cand.department
        }

        # Run AI matching
        eval_result = matching_engine.evaluate_candidate(cand_data, job_data)

        # Skip candidates failing eligibility if only_eligible is requested
        if payload.only_eligible and not eval_result["is_eligible"]:
            continue

        # Save or update CandidateMatch in DB
        match_record = db.query(CandidateMatch).filter(
            CandidateMatch.candidate_id == cand.id,
            CandidateMatch.job_role_id == job_role.id
        ).first()

        if not match_record:
            match_record = CandidateMatch(
                candidate_id=cand.id,
                job_role_id=job_role.id,
                match_score=eval_result["match_score"],
                skill_score=eval_result["skill_score"],
                similarity_score=eval_result["similarity_score"],
                project_score=eval_result["project_score"],
                experience_score=eval_result["experience_score"],
                education_score=eval_result["education_score"],
                matched_skills=json.dumps(eval_result["matched_skills"]),
                missing_skills=json.dumps(eval_result["missing_skills"]),
                ai_explanation=eval_result["ai_explanation"]
            )
            db.add(match_record)
        else:
            match_record.match_score = eval_result["match_score"]
            match_record.skill_score = eval_result["skill_score"]
            match_record.similarity_score = eval_result["similarity_score"]
            match_record.project_score = eval_result["project_score"]
            match_record.experience_score = eval_result["experience_score"]
            match_record.education_score = eval_result["education_score"]
            match_record.matched_skills = json.dumps(eval_result["matched_skills"])
            match_record.missing_skills = json.dumps(eval_result["missing_skills"])
            match_record.ai_explanation = eval_result["ai_explanation"]

        sl_info = shortlists.get(cand.id)
        current_status = sl_info.status if sl_info else "Not Shortlisted"
        sl_id = sl_info.id if sl_info else None

        results.append(CandidateMatchOut(
            id=match_record.id,
            candidate_id=cand.id,
            candidate_code=cand.candidate_code,
            candidate_name=cand.name,
            email=cand.email,
            phone=cand.phone,
            college_id=cand.college_id,
            college_name=cand.college.name if cand.college else "Unknown College",
            department=cand.department,
            cgpa=cand.cgpa,
            graduation_year=cand.graduation_year,
            match_score=eval_result["match_score"],
            skill_score=eval_result["skill_score"],
            similarity_score=eval_result["similarity_score"],
            project_score=eval_result["project_score"],
            experience_score=eval_result["experience_score"],
            education_score=eval_result["education_score"],
            matched_skills=eval_result["matched_skills"],
            missing_skills=eval_result["missing_skills"],
            ai_explanation=eval_result["ai_explanation"],
            is_eligible=eval_result["is_eligible"],
            status=current_status,
            shortlist_id=sl_id
        ))

    db.commit()

    # Sort candidates by Match Score descending (Candidate Ranking)
    results.sort(key=lambda x: x.match_score, reverse=True)
    return results

@router.get("/{job_role_id}", response_model=List[CandidateMatchOut])
def get_existing_matches(
    job_role_id: int,
    college_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    query = db.query(CandidateMatch).filter(CandidateMatch.job_role_id == job_role_id)
    matches = query.all()

    shortlists = {
        s.candidate_id: s for s in db.query(Shortlist).filter(Shortlist.job_role_id == job_role_id).all()
    }

    results = []
    for m in matches:
        cand = m.candidate
        if college_id and cand.college_id != college_id:
            continue

        matched_skills = json.loads(m.matched_skills) if m.matched_skills else []
        missing_skills = json.loads(m.missing_skills) if m.missing_skills else []

        sl_info = shortlists.get(cand.id)
        current_status = sl_info.status if sl_info else "Not Shortlisted"
        sl_id = sl_info.id if sl_info else None

        results.append(CandidateMatchOut(
            id=m.id,
            candidate_id=cand.id,
            candidate_code=cand.candidate_code,
            candidate_name=cand.name,
            email=cand.email,
            phone=cand.phone,
            college_id=cand.college_id,
            college_name=cand.college.name if cand.college else "",
            department=cand.department,
            cgpa=cand.cgpa,
            graduation_year=cand.graduation_year,
            match_score=m.match_score,
            skill_score=m.skill_score or 0.0,
            similarity_score=m.similarity_score or 0.0,
            project_score=m.project_score or 0.0,
            experience_score=m.experience_score or 0.0,
            education_score=m.education_score or 0.0,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            ai_explanation=m.ai_explanation or "",
            is_eligible=True,
            status=current_status,
            shortlist_id=sl_id
        ))

    results.sort(key=lambda x: x.match_score, reverse=True)
    return results

@router.post("/compare", response_model=List[CompareCandidateOut])
def compare_candidates(
    payload: CompareRequest,
    db: Session = Depends(get_db),
    current_manager = Depends(get_current_manager)
):
    """
    Compares 2-4 selected candidates side-by-side for recruiter evaluation.
    """
    if len(payload.candidate_ids) < 2 or len(payload.candidate_ids) > 4:
        raise HTTPException(
            status_code=400,
            detail="Please select between 2 and 4 candidates to compare."
        )

    candidates = db.query(Candidate).filter(Candidate.id.in_(payload.candidate_ids)).all()
    results = []

    for cand in candidates:
        c_out = candidate_to_out(cand)
        match_record = db.query(CandidateMatch).filter(
            CandidateMatch.candidate_id == cand.id,
            CandidateMatch.job_role_id == payload.job_role_id
        ).first()

        match_out = None
        if match_record:
            matched_skills = json.loads(match_record.matched_skills) if match_record.matched_skills else []
            missing_skills = json.loads(match_record.missing_skills) if match_record.missing_skills else []
            match_out = CandidateMatchOut(
                id=match_record.id,
                candidate_id=cand.id,
                candidate_code=cand.candidate_code,
                candidate_name=cand.name,
                email=cand.email,
                phone=cand.phone,
                college_id=cand.college_id,
                college_name=cand.college.name if cand.college else "",
                department=cand.department,
                cgpa=cand.cgpa,
                graduation_year=cand.graduation_year,
                match_score=match_record.match_score,
                skill_score=match_record.skill_score or 0.0,
                similarity_score=match_record.similarity_score or 0.0,
                project_score=match_record.project_score or 0.0,
                experience_score=match_record.experience_score or 0.0,
                education_score=match_record.education_score or 0.0,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                ai_explanation=match_record.ai_explanation or "",
                is_eligible=True
            )

        results.append(CompareCandidateOut(candidate=c_out, match=match_out))

    return results
