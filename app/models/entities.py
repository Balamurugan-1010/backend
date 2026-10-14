from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False, default="TalentMatch Partner")
    created_at = Column(DateTime, default=datetime.utcnow)

    job_roles = relationship("JobRole", back_populates="manager", cascade="all, delete-orphan")
    shortlists = relationship("Shortlist", back_populates="manager", cascade="all, delete-orphan")


class ManagerOTP(Base):
    __tablename__ = "manager_otps"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)

    manager = relationship("Manager")


class College(Base):
    __tablename__ = "colleges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    location = Column(String(255), default="Tamil Nadu, India")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidates = relationship("Candidate", back_populates="college", cascade="all, delete-orphan")
    job_roles = relationship("JobRole", back_populates="college")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), index=True, nullable=False)
    phone = Column(String(64), nullable=False)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=False)
    department = Column(String(255), nullable=False)
    graduation_year = Column(Integer, nullable=False, default=2026)
    cgpa = Column(Float, nullable=False, default=0.0)
    areas_of_interest = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    college = relationship("College", back_populates="candidates")
    resume = relationship("Resume", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="candidate", cascade="all, delete-orphan")
    internships = relationship("Internship", back_populates="candidate", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="candidate", cascade="all, delete-orphan")
    matches = relationship("CandidateMatch", back_populates="candidate", cascade="all, delete-orphan")
    shortlists = relationship("Shortlist", back_populates="candidate", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), unique=True, nullable=False)
    file_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)
    extracted_text = Column(Text, nullable=False, default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="resume")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    skill_name = Column(String(128), nullable=False, index=True)

    candidate = relationship("Candidate", back_populates="skills")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    project_name = Column(String(255), nullable=False)
    description = Column(Text, default="")

    candidate = relationship("Candidate", back_populates="projects")


class Internship(Base):
    __tablename__ = "internships"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    company = Column(String(255), nullable=False)
    description = Column(Text, default="")
    duration = Column(String(128), default="")

    candidate = relationship("Candidate", back_populates="internships")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    name = Column(String(255), nullable=False)
    issuer = Column(String(255), default="")

    candidate = relationship("Candidate", back_populates="certifications")


class JobRole(Base):
    __tablename__ = "job_roles"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=True)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    company_name = Column(String(255), nullable=False)
    role_name = Column(String(255), nullable=False)
    job_description = Column(Text, nullable=False)
    minimum_cgpa = Column(Float, nullable=False, default=7.0)
    eligible_departments = Column(Text, default="Computer Science and Engineering,Information Technology")
    experience_requirement = Column(String(128), default="Freshers / 0-1 Years")
    created_at = Column(DateTime, default=datetime.utcnow)

    manager = relationship("Manager", back_populates="job_roles")
    college = relationship("College", back_populates="job_roles")
    required_skills = relationship("JobRequiredSkill", back_populates="job_role", cascade="all, delete-orphan")
    matches = relationship("CandidateMatch", back_populates="job_role", cascade="all, delete-orphan")
    shortlists = relationship("Shortlist", back_populates="job_role", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="job_role", cascade="all, delete-orphan")


class JobRequiredSkill(Base):
    __tablename__ = "job_required_skills"

    id = Column(Integer, primary_key=True, index=True)
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False)
    skill_name = Column(String(128), nullable=False, index=True)
    required = Column(Boolean, default=True)  # True = Required, False = Preferred

    job_role = relationship("JobRole", back_populates="required_skills")


class CandidateMatch(Base):
    __tablename__ = "candidate_matches"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False)
    match_score = Column(Float, nullable=False, default=0.0)
    skill_score = Column(Float, default=0.0)
    similarity_score = Column(Float, default=0.0)
    project_score = Column(Float, default=0.0)
    experience_score = Column(Float, default=0.0)
    education_score = Column(Float, default=0.0)
    matched_skills = Column(Text, default="[]")  # JSON encoded list
    missing_skills = Column(Text, default="[]")  # JSON encoded list
    ai_explanation = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="matches")
    job_role = relationship("JobRole", back_populates="matches")


class Shortlist(Base):
    __tablename__ = "shortlists"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("managers.id"), nullable=True)
    status = Column(String(64), default="Shortlisted")  # Shortlisted, Assessment, Interview, Selected, Rejected
    shortlisted_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="shortlists")
    job_role = relationship("JobRole", back_populates="shortlists")
    manager = relationship("Manager", back_populates="shortlists")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_role_id = Column(Integer, ForeignKey("job_roles.id"), nullable=False)
    assessment_type = Column(String(128), default="Technical Assessment")
    score = Column(Float, default=0.0)
    status = Column(String(64), default="Pending")  # Pending, Completed, Passed, Failed
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="assessments")
    job_role = relationship("JobRole", back_populates="assessments")
