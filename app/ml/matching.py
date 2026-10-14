from typing import List, Dict, Any, Tuple
import json
import numpy as np
from backend.app.ml.skill_extraction import normalize_skill
from backend.app.ml.preprocessing import preprocess_for_tfidf, clean_text
from backend.app.ml.vectorizer import get_tfidf_vectorizer, compute_cosine_similarity

class CandidateMatchingEngine:
    """
    Core AI Resume Matching Engine utilizing TF-IDF vectorization,
    cosine similarity, normalized skill overlap, and multi-factor weighted scoring.
    """

    def __init__(
        self,
        weight_skill: float = 0.40,
        weight_similarity: float = 0.25,
        weight_projects: float = 0.15,
        weight_experience: float = 0.10,
        weight_education: float = 0.10,
    ):
        self.w_skill = weight_skill
        self.w_sim = weight_similarity
        self.w_proj = weight_projects
        self.w_exp = weight_experience
        self.w_edu = weight_education
        self.vectorizer = get_tfidf_vectorizer(max_features=5000)

    def compute_skill_overlap(
        self,
        candidate_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str] = None
    ) -> Tuple[float, List[str], List[str]]:
        """
        Calculates skill match percentage, matched skills list, and missing skills gap.
        """
        preferred_skills = preferred_skills or []
        norm_candidate = {normalize_skill(s).lower(): normalize_skill(s) for s in candidate_skills if s}
        norm_required = [normalize_skill(s) for s in required_skills if s]
        norm_preferred = [normalize_skill(s) for s in preferred_skills if s]

        if not norm_required and not norm_preferred:
            # If no skills specified, give baseline
            return 80.0, list(norm_candidate.values()), []

        matched_req: List[str] = []
        missing_req: List[str] = []

        for req in norm_required:
            if req.lower() in norm_candidate:
                matched_req.append(req)
            else:
                missing_req.append(req)

        matched_pref: List[str] = []
        for pref in norm_preferred:
            if pref.lower() in norm_candidate:
                matched_pref.append(pref)

        # Calculation
        total_req_count = len(norm_required) if norm_required else 1
        req_ratio = len(matched_req) / total_req_count

        pref_bonus = 0.0
        if norm_preferred:
            pref_bonus = min(15.0, (len(matched_pref) / len(norm_preferred)) * 15.0)

        # Scale to 0 - 100
        raw_skill_score = min(100.0, (req_ratio * 85.0) + pref_bonus)
        if len(missing_req) == 0 and len(norm_required) > 0:
            raw_skill_score = max(raw_skill_score, 95.0)

        return round(raw_skill_score, 1), matched_req + matched_pref, missing_req

    def compute_jd_similarity(self, jd_text: str, resume_text: str) -> float:
        """
        Calculates cosine similarity between TF-IDF representations of the JD and the resume.
        """
        clean_jd = preprocess_for_tfidf(jd_text)
        clean_res = preprocess_for_tfidf(resume_text)

        if not clean_jd or not clean_res:
            return 40.0

        try:
            corpus = [clean_jd, clean_res]
            tfidf_matrix = self.vectorizer.fit_transform(corpus)
            sim = compute_cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Scale cosine similarity from [0, 1] to [0, 100] with standard curve
            score = float(sim * 100.0)
            # Add reasonable scaling so good text similarity reaches 70-95
            scaled = min(100.0, max(0.0, score * 1.5))
            return round(scaled, 1)
        except Exception:
            return 50.0

    def compute_project_score(self, projects: List[Dict[str, Any]], required_skills: List[str], jd_text: str) -> float:
        """
        Evaluates relevance of candidate projects against job requirements.
        """
        if not projects:
            return 30.0

        score = 50.0 + min(30.0, len(projects) * 15.0)
        proj_text = " ".join([f"{p.get('project_name', '')} {p.get('description', '')}" for p in projects]).lower()

        matched_in_proj = 0
        for skill in required_skills:
            if skill.lower() in proj_text:
                matched_in_proj += 1

        if required_skills:
            score += min(20.0, (matched_in_proj / len(required_skills)) * 20.0)

        return min(100.0, round(score, 1))

    def compute_experience_score(self, internships: List[Dict[str, Any]]) -> float:
        """
        Evaluates internship and hands-on experience presence.
        """
        if not internships:
            return 45.0  # College freshers baseline

        return min(100.0, 70.0 + (len(internships) * 15.0))

    def compute_education_score(self, cgpa: float, department: str, eligible_depts: str, min_cgpa: float) -> float:
        """
        Evaluates education criteria: CGPA performance and department eligibility.
        """
        dept_eligible = True
        if eligible_depts:
            dept_list = [d.strip().lower() for d in eligible_depts.split(",")]
            dept_eligible = department.strip().lower() in dept_list or "all" in dept_list

        dept_points = 50.0 if dept_eligible else 20.0

        # CGPA points (scaled from min_cgpa up to 10.0)
        if cgpa >= min_cgpa:
            cgpa_points = 35.0 + min(15.0, ((cgpa - min_cgpa) / max(0.1, 10.0 - min_cgpa)) * 15.0)
        else:
            cgpa_points = max(10.0, (cgpa / min_cgpa) * 30.0)

        return min(100.0, round(dept_points + cgpa_points, 1))

    def generate_ai_explanation(
        self,
        candidate_name: str,
        match_score: float,
        matched_skills: List[str],
        missing_skills: List[str],
        cgpa: float,
        has_internship: bool,
        project_count: int
    ) -> str:
        """
        Produces human-readable, explainable AI reasoning for recruiter transparency.
        """
        matched_count = len(matched_skills)
        missing_count = len(missing_skills)

        strength_desc = "Strong" if match_score >= 80 else "Moderate" if match_score >= 60 else "Partial"
        matched_sample = ", ".join(matched_skills[:4]) if matched_skills else "General technical foundational skills"

        parts = [
            f"{strength_desc} match ({int(round(match_score))}%) for {candidate_name}."
        ]

        if matched_skills:
            parts.append(f"Demonstrates proficiency in {matched_count} relevant skill(s): {matched_sample}.")

        if missing_skills:
            parts.append(f"Identified skill gap in: {', '.join(missing_skills[:3])}.")
        else:
            parts.append("Fulfills all specified mandatory skill requirements.")

        if project_count > 0:
            parts.append(f"Possesses {project_count} relevant hands-on project portfolio item(s).")
        
        if has_internship:
            parts.append("Includes verified practical internship experience.")

        parts.append(f"Academic standing: CGPA {cgpa:.2f}.")

        explanation = " ".join(parts)
        return explanation

    def evaluate_candidate(
        self,
        candidate_data: Dict[str, Any],
        job_role_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Full evaluation pipeline combining all scoring components.
        """
        candidate_skills = candidate_data.get("skills", [])
        required_skills = job_role_data.get("required_skills", [])
        preferred_skills = job_role_data.get("preferred_skills", [])
        jd_text = job_role_data.get("job_description", "")
        resume_text = candidate_data.get("resume_text", "")
        projects = candidate_data.get("projects", [])
        internships = candidate_data.get("internships", [])
        cgpa = float(candidate_data.get("cgpa", 0.0))
        department = candidate_data.get("department", "")
        eligible_depts = job_role_data.get("eligible_departments", "")
        min_cgpa = float(job_role_data.get("minimum_cgpa", 7.0))

        # Check strict eligibility
        dept_list = [d.strip().lower() for d in eligible_depts.split(",")] if eligible_depts else []
        is_dept_ok = (not dept_list) or (department.strip().lower() in dept_list) or ("all" in dept_list)
        is_cgpa_ok = cgpa >= min_cgpa
        is_eligible = is_dept_ok and is_cgpa_ok

        # 1. Skill Match (40%)
        skill_score, matched_skills, missing_skills = self.compute_skill_overlap(
            candidate_skills, required_skills, preferred_skills
        )

        # 2. JD Similarity (25%)
        similarity_score = self.compute_jd_similarity(jd_text, resume_text)

        # 3. Project Relevance (15%)
        project_score = self.compute_project_score(projects, required_skills, jd_text)

        # 4. Experience (10%)
        experience_score = self.compute_experience_score(internships)

        # 5. Education / Eligibility (10%)
        education_score = self.compute_education_score(cgpa, department, eligible_depts, min_cgpa)

        # Final Weighted Score: 0 - 100
        final_match_score = (
            (skill_score * self.w_skill) +
            (similarity_score * self.w_sim) +
            (project_score * self.w_proj) +
            (experience_score * self.w_exp) +
            (education_score * self.w_edu)
        )
        final_match_score = round(max(0.0, min(100.0, final_match_score)), 1)

        ai_explanation = self.generate_ai_explanation(
            candidate_name=candidate_data.get("name", "Candidate"),
            match_score=final_match_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            cgpa=cgpa,
            has_internship=len(internships) > 0,
            project_count=len(projects)
        )

        return {
            "match_score": final_match_score,
            "skill_score": skill_score,
            "similarity_score": similarity_score,
            "project_score": project_score,
            "experience_score": experience_score,
            "education_score": education_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "ai_explanation": ai_explanation,
            "is_eligible": is_eligible
        }

# Global Matching Engine instance
matching_engine = CandidateMatchingEngine()
