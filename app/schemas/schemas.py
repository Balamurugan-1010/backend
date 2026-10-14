from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field

# ----------------- Auth Schemas -----------------
class LoginRequest(BaseModel):
    email: str
    password: str

class SendOtpRequest(BaseModel):
    email: str

class SendOtpResponse(BaseModel):
    message: str
    email: str
    expires_in_seconds: int = 300
    cooldown_seconds: int = 60

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)

class ManagerOut(BaseModel):
    id: int
    name: str
    email: str
    company_name: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    manager: ManagerOut

# ----------------- College Schemas -----------------
class CollegeOut(BaseModel):
    id: int
    name: str
    location: str
    total_candidates: int = 0
    eligible_candidates: int = 0
    departments: List[str] = []
    average_cgpa: float = 0.0

    class Config:
        from_attributes = True

class CollegeCreate(BaseModel):
    name: str
    location: Optional[str] = "Tamil Nadu, India"

# ----------------- Candidate Schemas -----------------
class SkillItem(BaseModel):
    skill_name: str

class ProjectItem(BaseModel):
    project_name: str
    description: Optional[str] = ""

class InternshipItem(BaseModel):
    company: str
    description: Optional[str] = ""
    duration: Optional[str] = ""

class CertificationItem(BaseModel):
    name: str
    issuer: Optional[str] = ""

class CandidateCreate(BaseModel):
    name: str
    email: str
    phone: str
    college_name: Optional[str] = None
    department: Optional[str] = None
    graduation_year: Optional[int] = 2026
    cgpa: Optional[float] = None
    areas_of_interest: Optional[str] = ""
    job_role_id: Optional[int] = None
    skills: Optional[List[str]] = []
    projects: Optional[List[ProjectItem]] = []
    internships: Optional[List[InternshipItem]] = []
    certifications: Optional[List[CertificationItem]] = []

class CandidateOut(BaseModel):
    id: int
    candidate_code: str
    name: str
    email: str
    phone: str
    college_id: int
    college_name: Optional[str] = ""
    department: str
    graduation_year: int
    cgpa: float
    areas_of_interest: Optional[str] = ""
    created_at: Optional[datetime] = None
    skills: List[str] = []
    projects: List[ProjectItem] = []
    internships: List[InternshipItem] = []
    certifications: List[CertificationItem] = []
    has_resume: bool = False

    class Config:
        from_attributes = True

# ----------------- Job Role Schemas -----------------
class JobSkillInput(BaseModel):
    skill_name: str
    required: bool = True

class JobRoleCreate(BaseModel):
    company_name: str
    role_name: str
    job_description: str
    minimum_cgpa: float = 7.0
    eligible_departments: str = "Computer Science and Engineering,Information Technology"
    experience_requirement: Optional[str] = "Freshers / 0-1 Years"
    college_id: Optional[int] = None
    required_skills: List[JobSkillInput] = []

class JobRoleOut(BaseModel):
    id: int
    manager_id: Optional[int] = None
    college_id: Optional[int] = None
    company_name: str
    role_name: str
    job_description: str
    minimum_cgpa: float
    eligible_departments: str
    experience_requirement: Optional[str] = ""
    created_at: Optional[datetime] = None
    required_skills: List[JobSkillInput] = []

    class Config:
        from_attributes = True

# ----------------- AI Matching Schemas -----------------
class MatchingRunRequest(BaseModel):
    job_role_id: int
    college_id: Optional[int] = None
    only_eligible: bool = False

class CandidateMatchOut(BaseModel):
    id: Optional[int] = None
    candidate_id: int
    candidate_code: str
    candidate_name: str
    email: str
    phone: str
    college_id: int
    college_name: str
    department: str
    cgpa: float
    graduation_year: int
    match_score: float
    skill_score: float
    similarity_score: float
    project_score: float
    experience_score: float
    education_score: float
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    ai_explanation: str
    is_eligible: bool = True
    status: Optional[str] = "Not Shortlisted"
    shortlist_id: Optional[int] = None

class CompareRequest(BaseModel):
    job_role_id: int
    candidate_ids: List[int]

class CompareCandidateOut(BaseModel):
    candidate: CandidateOut
    match: Optional[CandidateMatchOut] = None

# ----------------- Shortlist Schemas -----------------
class ShortlistCreate(BaseModel):
    job_role_id: int
    candidate_ids: List[int]
    status: Optional[str] = "Shortlisted"

class ShortlistStatusUpdate(BaseModel):
    status: str  # Shortlisted, Assessment, Interview, Selected, Rejected

class ShortlistOut(BaseModel):
    id: int
    candidate_id: int
    candidate_code: str
    candidate_name: str
    email: str
    phone: str
    college_name: str
    department: str
    cgpa: float
    job_role_id: int
    role_name: str
    company_name: str
    status: str
    match_score: float = 0.0
    shortlisted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ----------------- Document Generation Schemas -----------------
class GenerateDocxRequest(BaseModel):
    job_role_id: int
    candidate_ids: List[int]
    include_full_details: bool = True

class GenerateDocxResponse(BaseModel):
    message: str
    filename: str
    download_url: str
    candidate_count: int

class GeneratePdfRequest(BaseModel):
    candidate_ids: List[int]
    job_role_id: Optional[int] = None

# ----------------- Dashboard Stats Schemas -----------------
class DashboardStatsOut(BaseModel):
    total_candidates: int
    total_colleges: int
    active_job_roles: int
    shortlisted_candidates: int
    recent_submissions: List[CandidateOut] = []
    top_colleges: List[dict] = []
