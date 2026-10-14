import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("talentmatch.seed")

from backend.app.database import engine, SessionLocal, Base
from backend.app.models.entities import (
    Manager, College, Candidate, Resume, CandidateSkill,
    Project, Internship, Certification, JobRole, JobRequiredSkill,
    CandidateMatch, Shortlist
)
from backend.app.auth.security import get_password_hash
from backend.app.ml.matching import matching_engine

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("[SEED] Seeding TalentMatch database...")

        # 1. Seed Manager
        manager_email = os.getenv("SEED_MANAGER_EMAIL", "balamurugant1010@gmail.com")
        manager_password = os.getenv("SEED_MANAGER_PASSWORD", "Bala@123")
        manager_name = os.getenv("SEED_MANAGER_NAME", "Balamurugan")
        manager_company = os.getenv("SEED_MANAGER_COMPANY", "NEXGEN SOLUTIONS")

        existing_manager = db.query(Manager).filter(Manager.email == manager_email).first()
        if not existing_manager:
            manager = Manager(
                name=manager_name,
                email=manager_email,
                password_hash=get_password_hash(manager_password),
                company_name=manager_company
            )
            db.add(manager)
            db.commit()
            db.refresh(manager)
            print(f"Created default Manager: {manager.email} (Password: {manager_password})")
        else:
            manager = existing_manager

        # 2. Seed Colleges
        colleges_data = [
            {"name": "Dr. Mahalingam College of Engineering and Technology", "location": "Pollachi, Coimbatore"},
            {"name": "PSG College of Technology", "location": "Peelamedu, Coimbatore"},
            {"name": "Kumaraguru College of Technology", "location": "Saravanampatti, Coimbatore"},
            {"name": "Sri Krishna College of Engineering and Technology", "location": "Kuniamuthur, Coimbatore"},
            {"name": "Government College of Technology", "location": "Thadagam Road, Coimbatore"},
            {"name": "Kongu Engineering College", "location": "Perundurai, Erode"},
            {"name": "Bannari Amman Institute of Technology", "location": "Sathyamangalam, Erode"},
            {"name": "Coimbatore Institute of Technology", "location": "Civil Aerodrome Post, Coimbatore"},
            {"name": "Thiagarajar College of Engineering", "location": "Madurai, Tamil Nadu"}
        ]

        college_map = {}
        for c_data in colleges_data:
            c = db.query(College).filter(College.name == c_data["name"]).first()
            if not c:
                c = College(name=c_data["name"], location=c_data["location"])
                db.add(c)
                db.commit()
                db.refresh(c)
            college_map[c.name] = c

        # 3. Seed Job Roles
        mcet = college_map["Dr. Mahalingam College of Engineering and Technology"]
        psg = college_map["PSG College of Technology"]

        roles_data = [
            {
                "role_name": "Full Stack Web Developer",
                "company_name": "HexaTech Solutions",
                "college_id": mcet.id,
                "job_description": "We are seeking a talented Full Stack Web Developer proficient in HTML5, CSS3, JavaScript, React, and Node.js. The candidate will build scalable client portals, integrate RESTful APIs, and collaborate on modern microservices architectures. Prior experience with MongoDB or SQL is highly preferred.",
                "minimum_cgpa": 7.5,
                "eligible_departments": "Computer Science and Engineering,Information Technology",
                "experience_requirement": "Freshers / 0-1 Years",
                "required_skills": [
                    {"skill_name": "JavaScript", "required": True},
                    {"skill_name": "React", "required": True},
                    {"skill_name": "Node.js", "required": True},
                    {"skill_name": "HTML", "required": True},
                    {"skill_name": "CSS", "required": True},
                    {"skill_name": "MongoDB", "required": False},
                    {"skill_name": "Git", "required": False}
                ]
            },
            {
                "role_name": "AI / Machine Learning Engineer",
                "company_name": "Cognitive Scale AI",
                "college_id": psg.id,
                "job_description": "Looking for a Machine Learning Engineer to design and deploy deep learning models. Candidate must have strong programming capability in Python, machine learning algorithms with Scikit-Learn, neural networks with PyTorch or TensorFlow, and experience handling data pipelines using Pandas and NumPy.",
                "minimum_cgpa": 8.0,
                "eligible_departments": "Computer Science and Engineering,Information Technology,Electronics and Communication Engineering",
                "experience_requirement": "Freshers / 2026 Batch",
                "required_skills": [
                    {"skill_name": "Python", "required": True},
                    {"skill_name": "Machine Learning", "required": True},
                    {"skill_name": "Deep Learning", "required": True},
                    {"skill_name": "TensorFlow", "required": True},
                    {"skill_name": "PyTorch", "required": False},
                    {"skill_name": "Pandas", "required": False}
                ]
            },
            {
                "role_name": "Java Backend Engineer",
                "company_name": "Apex Enterprise Systems",
                "college_id": mcet.id,
                "job_description": "Seeking an enthusiastic Java Backend Engineer to build robust RESTful APIs and enterprise microservices. Solid foundations in Java 17+, Spring Boot, Hibernate ORM, and relational databases like MySQL or PostgreSQL are required.",
                "minimum_cgpa": 7.0,
                "eligible_departments": "Computer Science and Engineering,Information Technology",
                "experience_requirement": "Freshers / 0-1 Years",
                "required_skills": [
                    {"skill_name": "Java", "required": True},
                    {"skill_name": "Spring Boot", "required": True},
                    {"skill_name": "MySQL", "required": True},
                    {"skill_name": "REST API", "required": True},
                    {"skill_name": "Docker", "required": False}
                ]
            }
        ]

        created_job_roles = []
        for r_data in roles_data:
            existing_role = db.query(JobRole).filter(
                JobRole.role_name == r_data["role_name"],
                JobRole.company_name == r_data["company_name"]
            ).first()

            if not existing_role:
                j = JobRole(
                    manager_id=manager.id,
                    college_id=r_data["college_id"],
                    company_name=r_data["company_name"],
                    role_name=r_data["role_name"],
                    job_description=r_data["job_description"],
                    minimum_cgpa=r_data["minimum_cgpa"],
                    eligible_departments=r_data["eligible_departments"],
                    experience_requirement=r_data["experience_requirement"]
                )
                db.add(j)
                db.commit()
                db.refresh(j)

                for sk in r_data["required_skills"]:
                    db.add(JobRequiredSkill(
                        job_role_id=j.id,
                        skill_name=sk["skill_name"],
                        required=sk["required"]
                    ))
                db.commit()
                created_job_roles.append(j)
            else:
                created_job_roles.append(existing_role)

        # 4. Seed Candidates with Rich Resumes
        candidates_seed = [
            {
                "code": "TM-2026-00101",
                "name": "Kavitha Ramanathan",
                "email": "kavitha.r@mcet.in",
                "phone": "+91 98421 11021",
                "college": "Dr. Mahalingam College of Engineering and Technology",
                "department": "Computer Science and Engineering",
                "cgpa": 8.85,
                "year": 2026,
                "interest": "Full Stack Web Development, Cloud Computing",
                "skills": ["JavaScript", "React", "Node.js", "Express.js", "HTML", "CSS", "Tailwind CSS", "MongoDB", "Git"],
                "projects": [
                    {"name": "Campus Event & Placement Portal", "desc": "MERN stack responsive portal with candidate registration, filter views, and analytics dashboards."},
                    {"name": "Cloud Task Management System", "desc": "Kanban workspace developed in React and Node.js with role-based access control."}
                ],
                "internships": [
                    {"company": "Cognizant Technology Solutions", "desc": "Web application developer intern building interactive React modules.", "dur": "3 Months"}
                ],
                "certifications": [
                    {"name": "Meta Front-End Developer Professional Certificate", "issuer": "Coursera"}
                ],
                "resume_text": "Kavitha Ramanathan. B.E. Computer Science, Dr. Mahalingam College of Engineering and Technology. CGPA: 8.85. Core competencies: HTML5, CSS3, JavaScript (ES6+), React, Node.js, Express.js, MongoDB, Tailwind CSS, Git. Built full-stack Campus Placement Portal and Cloud Task Manager. Interned at Cognizant building enterprise web applications."
            },
            {
                "code": "TM-2026-00102",
                "name": "Dinesh Kumar V",
                "email": "dinesh.k@mcet.in",
                "phone": "+91 94432 87612",
                "college": "Dr. Mahalingam College of Engineering and Technology",
                "department": "Information Technology",
                "cgpa": 8.40,
                "year": 2026,
                "interest": "Frontend Engineering, Web UI/UX",
                "skills": ["JavaScript", "React", "HTML", "CSS", "Tailwind CSS", "TypeScript", "MySQL", "Git"],
                "projects": [
                    {"name": "E-Commerce Storefront UI", "desc": "Modern responsive shopping application built with React, TypeScript, and Tailwind CSS."},
                    {"name": "Student Assessment Quiz App", "desc": "Interactive assessment app with timed quizzes and real-time score computation."}
                ],
                "internships": [
                    {"company": "Zoho Creator Incubator", "desc": "UI Developer trainee building reusable component libraries.", "dur": "2 Months"}
                ],
                "certifications": [
                    {"name": "React Developer Nanodegree", "issuer": "Udacity"}
                ],
                "resume_text": "Dinesh Kumar V. B.Tech IT, Dr. Mahalingam College of Engineering and Technology. CGPA: 8.40. Frontend engineer proficient in HTML, CSS, JavaScript, TypeScript, React, Tailwind CSS, MySQL, Git. Developed responsive E-commerce storefront and assessment app. 2-month summer internship at Zoho."
            },
            {
                "code": "TM-2026-00103",
                "name": "Preethi Sundaram",
                "email": "preethi.s@mcet.in",
                "phone": "+91 97890 33411",
                "college": "Dr. Mahalingam College of Engineering and Technology",
                "department": "Computer Science and Engineering",
                "cgpa": 7.90,
                "year": 2026,
                "interest": "Web & Backend Systems",
                "skills": ["HTML", "CSS", "JavaScript", "React", "Node.js", "Express.js", "MySQL"],
                "projects": [
                    {"name": "Hospital Bed Reservation System", "desc": "Web booking platform using Node.js, Express, and MySQL database."}
                ],
                "internships": [
                    {"company": "Vuram Technologies", "desc": "Associate software trainee for enterprise workflow automation.", "dur": "2 Months"}
                ],
                "certifications": [
                    {"name": "NodeJS Tutorial Series", "issuer": "freeCodeCamp"}
                ],
                "resume_text": "Preethi Sundaram. Computer Science student at MCET. CGPA: 7.90. Proficient in HTML, CSS, JavaScript, React, Node.js, Express, MySQL. Built hospital management system and worked as trainee at Vuram Technologies."
            },
            {
                "code": "TM-2026-00104",
                "name": "Surya Narayanan",
                "email": "surya.n@mcet.in",
                "phone": "+91 99401 54321",
                "college": "Dr. Mahalingam College of Engineering and Technology",
                "department": "Computer Science and Engineering",
                "cgpa": 7.15,
                "year": 2026,
                "interest": "Web Design, Basic Programming",
                "skills": ["HTML", "CSS", "JavaScript", "PHP", "Bootstrap", "MySQL"],
                "projects": [
                    {"name": "Alumni Association Website", "desc": "PHP and MySQL web portal with alumni directory and event gallery."}
                ],
                "internships": [],
                "certifications": [
                    {"name": "Responsive Web Design", "issuer": "freeCodeCamp"}
                ],
                "resume_text": "Surya Narayanan. CSE, MCET. CGPA: 7.15. Knowledge of HTML, CSS, JavaScript, PHP, MySQL, Bootstrap. Created college alumni directory website."
            },
            {
                "code": "TM-2026-00105",
                "name": "Naveen Prakash",
                "email": "naveen.p@mcet.in",
                "phone": "+91 98845 22910",
                "college": "Dr. Mahalingam College of Engineering and Technology",
                "department": "Mechanical Engineering",
                "cgpa": 6.80,
                "year": 2026,
                "interest": "Design, CAD, Basics of Web",
                "skills": ["HTML", "CSS", "AutoCAD", "SolidWorks"],
                "projects": [
                    {"name": "Solar Powered EV Chassis", "desc": "CAD modeling and structural analysis."}
                ],
                "internships": [],
                "certifications": [],
                "resume_text": "Naveen Prakash. Mechanical Engineering, MCET. CGPA: 6.80. Basic knowledge of HTML and CSS. Expertise in AutoCAD and SolidWorks."
            },
            {
                "code": "TM-2026-00201",
                "name": "Harish Ragavendra",
                "email": "harish.r@psgtech.ac.in",
                "phone": "+91 98409 88123",
                "college": "PSG College of Technology",
                "department": "Computer Science and Engineering",
                "cgpa": 9.15,
                "year": 2026,
                "interest": "Artificial Intelligence, Deep Learning",
                "skills": ["Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-Learn", "Pandas", "NumPy", "OpenCV"],
                "projects": [
                    {"name": "Medical Imaging Cancer Detector", "desc": "PyTorch CNN model for automated histopathology tumor detection with 95.2% accuracy."},
                    {"name": "Stock Trend Multi-Agent Predictor", "desc": "LSTM neural networks and reinforcement learning portfolio balancing agent."}
                ],
                "internships": [
                    {"company": "Bosch Global Software", "desc": "Deep learning research intern optimizing autonomous vision models.", "dur": "4 Months"}
                ],
                "certifications": [
                    {"name": "Deep Learning Specialization", "issuer": "DeepLearning.AI"},
                    {"name": "TensorFlow Developer Certificate", "issuer": "Google"}
                ],
                "resume_text": "Harish Ragavendra. CSE at PSG College of Technology. CGPA: 9.15. Specialist in Python, Machine Learning, Deep Learning, TensorFlow, PyTorch, Scikit-Learn, Pandas, NumPy, OpenCV, Computer Vision. Published cancer detector project. 4-month research internship at Bosch."
            },
            {
                "code": "TM-2026-00202",
                "name": "Ananya Sridhar",
                "email": "ananya.s@psgtech.ac.in",
                "phone": "+91 97911 55678",
                "college": "PSG College of Technology",
                "department": "Information Technology",
                "cgpa": 8.70,
                "year": 2026,
                "interest": "Data Science, NLP",
                "skills": ["Python", "Machine Learning", "Natural Language Processing", "Pandas", "NumPy", "Scikit-Learn", "FastAPI"],
                "projects": [
                    {"name": "Customer Sentiment Engine", "desc": "NLP sentiment pipeline using Transformers and Scikit-Learn deployed as a FastAPI microservice."}
                ],
                "internships": [
                    {"company": "Mu Sigma", "desc": "Decision sciences intern developing predictive customer analytics models.", "dur": "3 Months"}
                ],
                "certifications": [
                    {"name": "Applied Data Science with Python", "issuer": "University of Michigan"}
                ],
                "resume_text": "Ananya Sridhar. IT at PSG College of Technology. CGPA: 8.70. Proficient in Python, Machine Learning, Natural Language Processing, Pandas, NumPy, Scikit-Learn, FastAPI, SQL. Developed Sentiment Engine and interned at Mu Sigma."
            },
            {
                "code": "TM-2026-00301",
                "name": "Manojkumar B",
                "email": "manoj.b@kct.ac.in",
                "phone": "+91 94876 11234",
                "college": "Kumaraguru College of Technology",
                "department": "Computer Science and Engineering",
                "cgpa": 8.65,
                "year": 2026,
                "interest": "Enterprise Java, Cloud Backend",
                "skills": ["Java", "Spring Boot", "MySQL", "PostgreSQL", "REST API", "Hibernate", "Microservices", "Docker", "Git"],
                "projects": [
                    {"name": "Banking Microservices Platform", "desc": "Decoupled transaction backend with Spring Boot, Spring Security, Hibernate, and MySQL."},
                    {"name": "Inventory Distributed System", "desc": "Java microservices communicating via Apache Kafka and Dockerized with PostgreSQL."}
                ],
                "internships": [
                    {"company": "TCS Digital", "desc": "Backend engineering intern maintaining enterprise Spring Boot services.", "dur": "3 Months"}
                ],
                "certifications": [
                    {"name": "Oracle Certified Professional: Java SE 17", "issuer": "Oracle"}
                ],
                "resume_text": "Manojkumar B. Computer Science at Kumaraguru College of Technology. CGPA: 8.65. Experienced in Java, Spring Boot, MySQL, PostgreSQL, REST API, Hibernate, Microservices, Docker, Git. Built banking microservices platform and interned at TCS Digital."
            }
        ]

        dummy_uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "resumes"))
        os.makedirs(dummy_uploads_dir, exist_ok=True)

        for c_seed in candidates_seed:
            col = college_map.get(c_seed["college"])
            if not col:
                continue

            existing_cand = db.query(Candidate).filter(Candidate.candidate_code == c_seed["code"]).first()
            if not existing_cand:
                cand = Candidate(
                    candidate_code=c_seed["code"],
                    name=c_seed["name"],
                    email=c_seed["email"],
                    phone=c_seed["phone"],
                    college_id=col.id,
                    department=c_seed["department"],
                    graduation_year=c_seed["year"],
                    cgpa=c_seed["cgpa"],
                    areas_of_interest=c_seed["interest"]
                )
                db.add(cand)
                db.commit()
                db.refresh(cand)

                # Add dummy resume file & record
                res_filename = f"{cand.candidate_code}_resume.pdf"
                res_path = os.path.join(dummy_uploads_dir, res_filename)
                with open(res_path, "w", encoding="utf-8") as f:
                    f.write(c_seed["resume_text"])

                db.add(Resume(
                    candidate_id=cand.id,
                    file_path=res_path,
                    original_filename=f"{cand.name.replace(' ', '_')}_Resume.pdf",
                    extracted_text=c_seed["resume_text"]
                ))

                # Skills
                for sk in c_seed["skills"]:
                    db.add(CandidateSkill(candidate_id=cand.id, skill_name=sk))

                # Projects
                for pj in c_seed["projects"]:
                    db.add(Project(candidate_id=cand.id, project_name=pj["name"], description=pj["desc"]))

                # Internships
                for it in c_seed["internships"]:
                    db.add(Internship(candidate_id=cand.id, company=it["company"], description=it["desc"], duration=it.get("dur", "")))

                # Certifications
                for ct in c_seed["certifications"]:
                    db.add(Certification(candidate_id=cand.id, name=ct["name"], issuer=ct.get("issuer", "")))

                db.commit()

        # 5. Pre-run matches for the Web Developer job role on MCET candidates
        web_role = created_job_roles[0]
        mcet_candidates = db.query(Candidate).filter(Candidate.college_id == mcet.id).all()

        job_data = {
            "role_name": web_role.role_name,
            "company_name": web_role.company_name,
            "job_description": web_role.job_description,
            "required_skills": [s.skill_name for s in web_role.required_skills if s.required],
            "preferred_skills": [s.skill_name for s in web_role.required_skills if not s.required],
            "minimum_cgpa": web_role.minimum_cgpa,
            "eligible_departments": web_role.eligible_departments
        }

        shortlisted_top = []
        for cand in mcet_candidates:
            cand_skills = [s.skill_name for s in cand.skills]
            cand_projects = [{"project_name": p.project_name, "description": p.description} for p in cand.projects]
            cand_internships = [{"company": i.company, "description": i.description, "duration": i.duration} for i in cand.internships]

            cand_data = {
                "name": cand.name,
                "skills": cand_skills,
                "resume_text": cand.resume.extracted_text if cand.resume else "",
                "projects": cand_projects,
                "internships": cand_internships,
                "cgpa": cand.cgpa,
                "department": cand.department
            }

            eval_res = matching_engine.evaluate_candidate(cand_data, job_data)

            m_rec = db.query(CandidateMatch).filter(
                CandidateMatch.candidate_id == cand.id,
                CandidateMatch.job_role_id == web_role.id
            ).first()

            if not m_rec:
                m_rec = CandidateMatch(
                    candidate_id=cand.id,
                    job_role_id=web_role.id,
                    match_score=eval_res["match_score"],
                    skill_score=eval_res["skill_score"],
                    similarity_score=eval_res["similarity_score"],
                    project_score=eval_res["project_score"],
                    experience_score=eval_res["experience_score"],
                    education_score=eval_res["education_score"],
                    matched_skills=json.dumps(eval_res["matched_skills"]),
                    missing_skills=json.dumps(eval_res["missing_skills"]),
                    ai_explanation=eval_res["ai_explanation"]
                )
                db.add(m_rec)
            db.commit()

            if eval_res["match_score"] >= 75:
                shortlisted_top.append(cand)

        # Pre-shortlist top candidates
        for cand in shortlisted_top:
            existing_sl = db.query(Shortlist).filter(
                Shortlist.candidate_id == cand.id,
                Shortlist.job_role_id == web_role.id
            ).first()
            if not existing_sl:
                db.add(Shortlist(
                    candidate_id=cand.id,
                    job_role_id=web_role.id,
                    manager_id=manager.id,
                    status="Shortlisted"
                ))
        db.commit()

        print("Database seeded successfully with colleges, manager, job roles, candidates, and AI matches!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
