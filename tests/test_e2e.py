import os
import sys
import io
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

def run_e2e_verification():
    print("=" * 60)
    print("TALENTMATCH E2E VERIFICATION SUITE")
    print("=" * 60)

    # 1. Health check
    status, data = make_request("/health")
    assert status == 200, f"Health check failed: {status}"
    print(f"[PASS] Health Check Passed: {data}")

    # 2. Test Invalid Manager Login
    status, data = make_request("/auth/login", method="POST", data={
        "email": "recruiter@talentmatch.ai",
        "password": "WrongPassword123"
    })
    assert status == 401, f"Expected 401 for wrong credentials, got {status}"
    print(f"[PASS] Invalid Manager Login Rejected Correctly (401): {data.get('detail')}")

    # 3. Test Valid Manager Login
    status, data = make_request("/auth/login", method="POST", data={
        "email": "recruiter@talentmatch.ai",
        "password": "Manager@2026"
    })
    assert status == 200 and "access_token" in data, f"Login failed: {data}"
    token = data["access_token"]
    print(f"[PASS] Valid Manager Login Succeeded: Token acquired, Manager = {data['manager']['name']}")

    # 4. Test Colleges endpoint
    status, colleges = make_request("/colleges", token=token)
    assert status == 200 and len(colleges) > 0, "Failed to get colleges"
    print(f"[PASS] Colleges List Verified: {len(colleges)} colleges found (Top: {colleges[0]['name']})")
    target_college_id = colleges[0]["id"]

    # 5. Test Job Roles endpoint
    status, job_roles = make_request("/job-roles", token=token)
    assert status == 200 and len(job_roles) > 0, "Failed to get job roles"
    target_role = job_roles[0]
    print(f"[PASS] Job Roles Verified: {len(job_roles)} active roles (First: {target_role['role_name']})")

    # 6. Test Public Student Submission
    cand_payload = {
        "name": "Vignesh Sundaram",
        "email": "vignesh.test@mcet.in",
        "phone": "+91 98989 12345",
        "college_name": colleges[0]["name"],
        "department": "Computer Science and Engineering",
        "graduation_year": 2026,
        "cgpa": 8.75,
        "areas_of_interest": "Web Development, React, Cloud"
    }
    status, new_cand = make_request("/candidates", method="POST", data=cand_payload)
    assert status == 200 and "candidate_code" in new_cand, f"Student submission failed: {new_cand}"
    cand_id = new_cand["id"]
    print(f"[PASS] Public Student Submission Succeeded: Candidate ID = {new_cand['candidate_code']} (DB ID: {cand_id})")

    # 7. Test AI Matching & Candidate Ranking
    match_payload = {
        "job_role_id": target_role["id"],
        "college_id": target_college_id,
        "only_eligible": False
    }
    status, ranked_candidates = make_request("/matching/run", method="POST", data=match_payload, token=token)
    assert status == 200 and len(ranked_candidates) > 0, f"Matching failed: {ranked_candidates}"
    print(f"[PASS] AI Matching Succeeded: {len(ranked_candidates)} candidates ranked!")
    top_candidate = ranked_candidates[0]
    print(f"  Rank #1 Candidate: {top_candidate['candidate_name']} • Score: {top_candidate['match_score']}%")
    print(f"  Matched Skills: {top_candidate['matched_skills']}")
    print(f"  Skill Gap: {top_candidate['missing_skills']}")
    print(f"  AI Explanation: {top_candidate['ai_explanation'][:80]}...")

    # 8. Test Shortlisting
    cand_ids_to_shortlist = [c["candidate_id"] for c in ranked_candidates[:2]]
    sl_payload = {
        "job_role_id": target_role["id"],
        "candidate_ids": cand_ids_to_shortlist,
        "status": "Shortlisted"
    }
    status, sl_result = make_request("/shortlists", method="POST", data=sl_payload, token=token)
    assert status == 200 and len(sl_result) > 0, "Shortlisting failed"
    print(f"[PASS] Shortlisting Succeeded: {len(sl_result)} candidates shortlisted")

    # 9. Test DOCX Document Generation
    doc_payload = {
        "job_role_id": target_role["id"],
        "candidate_ids": cand_ids_to_shortlist,
        "include_full_details": True
    }
    status, doc_res = make_request("/documents/shortlist", method="POST", data=doc_payload, token=token)
    assert status == 200 and "download_url" in doc_res, f"DOCX generation failed: {doc_res}"
    print(f"[PASS] Word Document (.docx) Generated Successfully: {doc_res['filename']}")

    # 10. Test Downloading Generated DOCX
    dl_status, dl_data = make_request(f"/documents/shortlist/{doc_res['filename']}/download", token=token, is_json=False)
    assert dl_status == 200 and len(dl_data) > 1000, "DOCX download failed"
    print(f"[PASS] Download DOCX Verified: Received {len(dl_data)} bytes of valid Word document!")

    # 11. Test Dashboard Statistics
    status, stats = make_request("/stats/dashboard", token=token)
    assert status == 200 and "total_candidates" in stats, "Dashboard stats failed"
    print(f"[PASS] Dashboard Stats Verified: {stats['total_candidates']} Candidates, {stats['total_colleges']} Colleges, {stats['shortlisted_candidates']} Shortlisted")

    print("=" * 60)
    print("ALL 11 BACKEND VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_e2e_verification()
