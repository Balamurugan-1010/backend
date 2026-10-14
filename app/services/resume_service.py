import os
import uuid
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Tuple, List, Dict, Any
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.ml.preprocessing import clean_text, parse_resume_sections
from backend.app.ml.skill_extraction import extract_skills_from_text
from backend.app.models.entities import (
    Candidate, Resume, CandidateSkill, Project, Internship, Certification, College
)

# On Vercel serverless, only /tmp is writable; use local path for development
if os.getenv("VERCEL"):
    UPLOAD_DIR = "/tmp/uploads/resumes"
else:
    UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "resumes"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

def generate_candidate_code(db: Session) -> str:
    """Generate sequential unique code like TM-2026-00125."""
    year = datetime.utcnow().year
    count = db.query(Candidate).count() + 1
    return f"TM-{year}-{count:05d}"

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extracts plain text from PDF bytes using PyMuPDF (fitz).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text_list = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text:
                full_text_list.append(text)
        doc.close()
        return "\n".join(full_text_list).strip()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from the PDF file: {str(e)}"
        )

def parse_projects_from_text(projects_text: str) -> List[Dict[str, str]]:
    """Simple parser to extract project names and descriptions from project section."""
    if not projects_text:
        return []
    items = []
    # Split by bullet points or numbering
    parts = re.split(r"(?:^|\n)\s*(?:[•\-\*]|\d+\.)\s+", projects_text)
    for p in parts:
        cleaned = p.strip()
        if len(cleaned) > 10:
            lines = cleaned.splitlines()
            proj_name = lines[0][:100]
            desc = " ".join(lines[1:]) if len(lines) > 1 else cleaned
            items.append({"project_name": proj_name, "description": desc[:500]})
    if not items and len(projects_text) > 20:
        items.append({"project_name": "Major Academic Project", "description": projects_text[:500]})
    return items[:5]

def parse_internships_from_text(exp_text: str) -> List[Dict[str, str]]:
    """Extract internship / experience entries."""
    if not exp_text:
        return []
    items = []
    parts = re.split(r"(?:^|\n)\s*(?:[•\-\*]|\d+\.)\s+", exp_text)
    for p in parts:
        cleaned = p.strip()
        if len(cleaned) > 10:
            lines = cleaned.splitlines()
            comp_name = lines[0][:100]
            desc = " ".join(lines[1:]) if len(lines) > 1 else cleaned
            items.append({"company": comp_name, "description": desc[:500], "duration": "Internship"})
    if not items and ("intern" in exp_text.lower() or "experience" in exp_text.lower()):
        items.append({"company": "Industry Internship", "description": exp_text[:500], "duration": "2 Months"})
    return items[:4]

def parse_certifications_from_text(cert_text: str) -> List[Dict[str, str]]:
    """Extract certifications."""
    if not cert_text:
        return []
    items = []
    parts = re.split(r"(?:^|\n)\s*(?:[•\-\*]|\d+\.)\s+", cert_text)
    for p in parts:
        cleaned = p.strip()
        if len(cleaned) > 5:
            items.append({"name": cleaned[:120], "issuer": "Verified Course/Platform"})
    return items[:5]

def extract_academic_details_from_text(raw_text: str, db: Session) -> Dict[str, Any]:
    """
    Extracts CGPA, department, college, and graduation year from resume text.
    """
    details: Dict[str, Any] = {}
    if not raw_text:
        return details

    # CGPA / GPA extraction
    cgpa_match = re.search(r"(?:cgpa|gpa|aggregate|grade\s*point|score)[\s:=]*([0-9]\.[0-9]{1,2})", raw_text, re.IGNORECASE)
    if not cgpa_match:
        cgpa_match = re.search(r"\b([0-9]\.[0-9]{1,2})\s*(?:/|out of)\s*10(?:\.0)?\b", raw_text, re.IGNORECASE)
    if not cgpa_match:
        cgpa_match = re.search(r"\b([0-9]\.[0-9]{1,2})\s*(?:cgpa|gpa)\b", raw_text, re.IGNORECASE)

    if cgpa_match:
        try:
            val = float(cgpa_match.group(1))
            if 0.0 <= val <= 10.0:
                details["cgpa"] = round(val, 2)
        except ValueError:
            pass

    # Department extraction
    dept_mappings = [
        (r"\b(?:computer\s+science\s*(?:and|&)\s*engineering|cse|computer\s+science)\b", "Computer Science and Engineering"),
        (r"\b(?:information\s+technology|it\s+dept|b\.?\s*tech\s+it)\b", "Information Technology"),
        (r"\b(?:electronics\s*(?:and|&)\s*communication(?:\s*engineering)?|ece)\b", "Electronics and Communication Engineering"),
        (r"\b(?:electrical\s*(?:and|&)\s*electronics(?:\s*engineering)?|eee)\b", "Electrical and Electronics Engineering"),
        (r"\b(?:mechanical\s*engineering|mech\s*engg|mech)\b", "Mechanical Engineering"),
        (r"\b(?:civil\s*engineering|civil)\b", "Civil Engineering"),
        (r"\b(?:artificial\s*intelligence|ai\s*(?:and|&)\s*ds|data\s*science)\b", "Computer Science and Engineering"),
    ]
    for pattern, dept_name in dept_mappings:
        if re.search(pattern, raw_text, re.IGNORECASE):
            details["department"] = dept_name
            break

    # College extraction: check if any registered college is mentioned in resume
    try:
        colleges = db.query(College).all()
        for col in colleges:
            col_lower = col.name.lower()
            keywords = [col_lower]
            if "mahalingam" in col_lower:
                keywords.extend(["mahalingam", "mcet"])
            elif "psg" in col_lower:
                keywords.extend(["psg college", "psg tech", "psg"])
            elif "kumaraguru" in col_lower:
                keywords.extend(["kumaraguru", "kct"])
            elif "sri krishna" in col_lower:
                keywords.extend(["sri krishna", "skcet"])
            elif "government college of technology" in col_lower:
                keywords.extend(["government college of technology", "gct coimbatore", "gct"])

            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", raw_text, re.IGNORECASE):
                    details["college_id"] = col.id
                    break
            if "college_id" in details:
                break
    except Exception:
        pass

    # Graduation Year extraction
    year_match = re.search(r"\b(202[4-9]|203[0-2])\b", raw_text)
    if year_match:
        details["graduation_year"] = int(year_match.group(1))

    return details

async def process_and_save_resume(
    file: UploadFile,
    candidate_id: int,
    db: Session
) -> Resume:
    """
    Validates, extracts text, extracts skills/sections, and stores resume in database.
    """
    # 1. Validate file extension and MIME type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF resumes are accepted."
        )

    content = await file.read()

    # 2. Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume file exceeds the maximum size limit of 5 MB."
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # 3. Secure file storage (UUID prefixed filename, not exposed publicly)
    safe_filename = f"{uuid.uuid4().hex}_{re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename)}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 4. PDF Text Extraction
    extracted_text = extract_text_from_pdf_bytes(content)
    cleaned_full_text = clean_text(extracted_text)

    # 5. Extract Skills
    skills = extract_skills_from_text(extracted_text)

    # 6. Parse sections
    sections = parse_resume_sections(extracted_text)
    parsed_projects = parse_projects_from_text(sections["projects"])
    parsed_internships = parse_internships_from_text(sections["experience"])
    parsed_certifications = parse_certifications_from_text(sections["certifications"])

    # 7. Check if resume already exists for candidate
    existing_resume = db.query(Resume).filter(Resume.candidate_id == candidate_id).first()
    if existing_resume:
        # Delete old file safely if exists
        try:
            if os.path.exists(existing_resume.file_path):
                os.remove(existing_resume.file_path)
        except Exception:
            pass
        existing_resume.file_path = file_path
        existing_resume.original_filename = file.filename
        existing_resume.extracted_text = cleaned_full_text
        resume_record = existing_resume
    else:
        resume_record = Resume(
            candidate_id=candidate_id,
            file_path=file_path,
            original_filename=file.filename,
            extracted_text=cleaned_full_text
        )
        db.add(resume_record)

    # 8. Save extracted skills
    db.query(CandidateSkill).filter(CandidateSkill.candidate_id == candidate_id).delete()
    for skill_name in skills:
        db.add(CandidateSkill(candidate_id=candidate_id, skill_name=skill_name))

    # 9. Save projects if none exist
    curr_proj_count = db.query(Project).filter(Project.candidate_id == candidate_id).count()
    if curr_proj_count == 0 and parsed_projects:
        for p in parsed_projects:
            db.add(Project(candidate_id=candidate_id, project_name=p["project_name"], description=p["description"]))

    # 10. Save internships if none exist
    curr_exp_count = db.query(Internship).filter(Internship.candidate_id == candidate_id).count()
    if curr_exp_count == 0 and parsed_internships:
        for i in parsed_internships:
            db.add(Internship(candidate_id=candidate_id, company=i["company"], description=i["description"], duration=i.get("duration", "")))

    # 11. Save certifications if none exist
    curr_cert_count = db.query(Certification).filter(Certification.candidate_id == candidate_id).count()
    if curr_cert_count == 0 and parsed_certifications:
        for c in parsed_certifications:
            db.add(Certification(candidate_id=candidate_id, name=c["name"], issuer=c.get("issuer", "")))

    # 12. Update academic details on candidate if extracted from resume
    academic_info = extract_academic_details_from_text(extracted_text, db)
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if candidate:
        if academic_info.get("cgpa") is not None:
            candidate.cgpa = academic_info["cgpa"]
        if academic_info.get("department"):
            candidate.department = academic_info["department"]
        if academic_info.get("college_id"):
            candidate.college_id = academic_info["college_id"]
        if academic_info.get("graduation_year"):
            candidate.graduation_year = academic_info["graduation_year"]

    db.commit()
    db.refresh(resume_record)

    return resume_record
