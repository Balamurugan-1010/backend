import os
import json
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000/api"

def make_request(endpoint, method="GET", data=None, token=None, is_json=True):
    url = f"{API_URL}{endpoint}"
    headers = {}
    body = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if data is not None:
        if is_json:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
        else:
            body = data

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            status_code = resp.status
            try:
                parsed = json.loads(content.decode("utf-8"))
                return status_code, parsed
            except Exception:
                return status_code, content
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body

def test_student_submission_without_role():
    print("=" * 70)
    print("TESTING STUDENT RESUME SUBMISSION WITHOUT JOB ROLE REQUIREMENT")
    print("=" * 70)

    # 1. Manager Login
    status, data = make_request("/auth/login", method="POST", data={
        "email": "recruiter@talentmatch.ai",
        "password": "Manager@2026"
    })
    assert status == 200 and "access_token" in data, "Manager login failed"
    token = data["access_token"]
    print("[PASS] 1. Manager login successful.")

    # 2. Student Submits Profile WITHOUT any Job Role
    student_payload = {
        "name": "Karthik Subramanian",
        "email": "karthik.test@mcet.in",
        "phone": "+91 91234 56789",
        "college_name": "Dr. Mahalingam College of Engineering and Technology",
        "department": "Computer Science and Engineering",
        "graduation_year": 2026,
        "cgpa": 8.90,
        "areas_of_interest": "Full Stack, Cloud, DevOps",
        "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker"],
        "projects": [{"project_name": "Cloud Placement Portal", "description": "Microservice web app for placements"}],
        "internships": [{"company": "Tech Solutions Inc.", "description": "Backend Developer Intern", "duration": "3 Months"}],
        "certifications": [{"name": "AWS Solutions Architect Associate", "issuer": "Amazon Web Services"}]
    }

    # Verify no job_role field in student submission payload
    assert "job_role" not in student_payload and "job_role_id" not in student_payload
    status, new_student = make_request("/candidates", method="POST", data=student_payload)
    assert status == 200, f"Student submission failed: {new_student}"
    assert "candidate_code" in new_student, "No candidate_code returned"
    student_id = new_student["id"]
    print(f"[PASS] 2. Student profile submitted without Job Role: Code = {new_student['candidate_code']} (ID: {student_id})")

    # 3. Upload PDF Resume for student
    sample_pdf_path = os.path.join(os.path.dirname(__file__), "..", "uploads", "resumes")
    # Generate simple test PDF bytes
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 55 >>\nstream\nBT /F1 12 Tf 100 700 Td (Karthik Resume Python React Docker) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n00000000115 00000 n\n00000000214 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n319\n%%EOF"

    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body_parts = []
    body_parts.append(f'--{boundary}'.encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="Karthik_Resume.pdf"'.encode())
    body_parts.append(b'Content-Type: application/pdf\r\n')
    body_parts.append(pdf_content)
    body_parts.append(f'--{boundary}--'.encode())
    body_data = b'\r\n'.join(body_parts)

    req = urllib.request.Request(
        f"{API_URL}/candidates/{student_id}/resume",
        data=body_data,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode())
        assert resp.status == 200
        print(f"[PASS] 3. Resume uploaded and stored successfully: {res_data.get('message')}")

    # 4. Manager selects Job Role & Runs AI Matching
    status, roles = make_request("/job-roles", token=token)
    assert status == 200 and len(roles) > 0, "Failed to get job roles for manager"
    manager_role = roles[0]
    print(f"[PASS] 4. Manager selected Job Role: '{manager_role['role_name']}' at {manager_role['company_name']}.")

    # 5. AI Matching uses Manager's selected role
    match_req = {
        "job_role_id": manager_role["id"],
        "only_eligible": False
    }
    status, matches = make_request("/matching/run", method="POST", data=match_req, token=token)
    assert status == 200 and len(matches) > 0, "AI Matching failed"
    print(f"[PASS] 5. AI matching completed using Manager's selected role: {len(matches)} candidates ranked.")

    # 6. Verify Candidate Ranking & Student Match Result
    karthik_match = next((m for m in matches if m["candidate_id"] == student_id), None)
    assert karthik_match is not None, "Submitted student not found in AI match ranking"
    print(f"[PASS] 6. Candidate match verified: {karthik_match['candidate_name']} matched with score {karthik_match['match_score']}%")

    # 7. Manager Shortlisting
    sl_req = {
        "job_role_id": manager_role["id"],
        "candidate_ids": [student_id],
        "status": "Shortlisted"
    }
    status, shortlists = make_request("/shortlists", method="POST", data=sl_req, token=token)
    assert status == 200 and len(shortlists) > 0, "Manager shortlisting failed"
    print(f"[PASS] 7. Manager successfully shortlisted candidate for Job Role.")

    print("=" * 70)
    print("ALL VERIFICATION CHECKS FOR STUDENT ROLE REMOVAL PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_student_submission_without_role()
