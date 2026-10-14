import os
import sys
import json
import urllib.request
import urllib.error
import pymupdf  # to inspect generated PDF content

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
            content_type = resp.headers.get("Content-Type", "")
            content_disposition = resp.headers.get("Content-Disposition", "")
            try:
                parsed = json.loads(content.decode("utf-8"))
                return status_code, parsed, resp.headers
            except Exception:
                return status_code, content, resp.headers
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body), e.headers
        except Exception:
            return e.code, err_body, e.headers


def test_pdf_generation_suite():
    print("=" * 70)
    print("TALENTMATCH PDF GENERATION VERIFICATION SUITE")
    print("=" * 70)

    # 1. Manager Login
    login_status, login_data, _ = make_request("/auth/login", method="POST", data={
        "email": "recruiter@talentmatch.ai",
        "password": "Manager@2026"
    })
    assert login_status == 200 and "access_token" in login_data, f"Manager login failed: {login_data}"
    token = login_data["access_token"]
    print(f"[PASS] 1. Manager Login Successful: {login_data['manager']['name']}")

    # 2. Get Job Roles and Candidates
    _, job_roles, _ = make_request("/job-roles", token=token)
    assert len(job_roles) > 0, "No job roles found"
    target_role = job_roles[0]

    _, candidates, _ = make_request("/candidates", token=token)
    assert len(candidates) >= 3, f"Expected at least 3 candidates, found {len(candidates)}"
    print(f"[PASS] 2. Fetched Test Data: Job Role = '{target_role['role_name']}' ({target_role['company_name']}), Total Candidates = {len(candidates)}")

    selected_cands = candidates[:2]
    selected_ids = [c["id"] for c in selected_cands]
    unselected_cands = candidates[2:]

    # 3. Test PDF Generation with 2 Selected Candidates
    print(f"Testing PDF generation for candidate IDs: {selected_ids}...")
    pdf_payload = {
        "candidate_ids": selected_ids,
        "job_role_id": target_role["id"]
    }
    status, pdf_bytes, headers = make_request("/documents/generate-pdf", method="POST", data=pdf_payload, token=token, is_json=True)
    assert status == 200, f"PDF generation failed with status {status}: {pdf_bytes}"
    assert isinstance(pdf_bytes, bytes), "Expected raw PDF bytes in response"
    assert pdf_bytes.startswith(b"%PDF-"), "Response does not start with %PDF- header"
    content_disp = headers.get("Content-Disposition", "")
    assert "attachment" in content_disp and "TalentMatch_Shortlisted_Candidates.pdf" in content_disp, f"Invalid Content-Disposition: {content_disp}"
    print(f"[PASS] 3. PDF Generated Successfully! Byte size: {len(pdf_bytes)} bytes, Content-Disposition: {content_disp}")

    # Inspect PDF text using PyMuPDF
    pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    full_pdf_text = ""
    for page in pdf_doc:
        full_pdf_text += page.get_text() + " "
    pdf_doc.close()
    normalized_pdf_text = " ".join(full_pdf_text.split())

    # Verify Required Content Fields
    assert "TalentMatch - Shortlisted Candidates" in normalized_pdf_text, "PDF missing Title"
    assert target_role["company_name"] in normalized_pdf_text, f"PDF missing Company Name: {target_role['company_name']}"
    assert target_role["role_name"] in normalized_pdf_text, f"PDF missing Job Role: {target_role['role_name']}"
    assert "Generation Date:" in normalized_pdf_text, "PDF missing Generation Date label"

    # Verify Selected Candidates are Present
    for cand in selected_cands:
        assert cand["name"] in normalized_pdf_text, f"Selected candidate '{cand['name']}' not found in generated PDF"
        assert cand["email"] in normalized_pdf_text, f"Selected candidate email '{cand['email']}' not found in PDF"
        print(f"  [OK] Verified selected candidate in PDF: {cand['name']} ({cand['email']}, {cand['department']}, CGPA {cand['cgpa']})")

    # Verify Unselected Candidates are NOT Present
    selected_names = {c["name"] for c in selected_cands}
    for cand in unselected_cands:
        if cand["name"] not in selected_names:
            assert cand["name"] not in normalized_pdf_text, f"Unselected candidate '{cand['name']}' WAS FOUND in PDF when they should not be included!"
    print(f"[PASS] 4. Content Verification: Only selected candidates are present; unselected candidates excluded.")

    # 4. Test Single Candidate PDF Generation
    single_cand = candidates[0]
    single_status, single_bytes, _ = make_request("/documents/generate-pdf", method="POST", data={
        "candidate_ids": [single_cand["id"]],
        "job_role_id": target_role["id"]
    }, token=token)
    assert single_status == 200 and single_bytes.startswith(b"%PDF-"), f"Single candidate PDF failed: {single_status}"
    print(f"[PASS] 5. Single Candidate PDF Generation Succeeded ({len(single_bytes)} bytes)")

    # 5. Test Multiple Candidates PDF Generation
    all_three_ids = [c["id"] for c in candidates[:3]]
    multi_status, multi_bytes, _ = make_request("/documents/generate-pdf", method="POST", data={
        "candidate_ids": all_three_ids,
        "job_role_id": target_role["id"]
    }, token=token)
    assert multi_status == 200 and multi_bytes.startswith(b"%PDF-"), f"Multi-candidate PDF failed: {multi_status}"
    print(f"[PASS] 6. Multiple Candidates (3 candidates) PDF Generation Succeeded ({len(multi_bytes)} bytes)")

    # 6. Test Validation: Empty candidate_ids
    empty_status, empty_res, _ = make_request("/documents/generate-pdf", method="POST", data={
        "candidate_ids": [],
        "job_role_id": target_role["id"]
    }, token=token)
    assert empty_status == 400, f"Expected 400 Bad Request for empty list, got {empty_status}"
    assert "Please select at least one candidate" in str(empty_res), f"Unexpected message: {empty_res}"
    print(f"[PASS] 7. Empty Selection Validation Correctly Returns 400: '{empty_res.get('detail')}'")

    # 7. Test Validation: Invalid Candidate IDs
    invalid_status, invalid_res, _ = make_request("/documents/generate-pdf", method="POST", data={
        "candidate_ids": [999999, 888888],
        "job_role_id": target_role["id"]
    }, token=token)
    assert invalid_status in (404, 400), f"Expected 404/400 for non-existent IDs, got {invalid_status}"
    print(f"[PASS] 8. Invalid Candidate ID Validation Correctly Returns Error: '{invalid_res.get('detail')}'")

    # 8. Test Unauthenticated Request
    unauth_status, unauth_res, _ = make_request("/documents/generate-pdf", method="POST", data={
        "candidate_ids": selected_ids,
        "job_role_id": target_role["id"]
    }, token=None)
    assert unauth_status == 401, f"Expected 401 Unauthorized for missing token, got {unauth_status}"
    print(f"[PASS] 9. Unauthenticated Access Blocked Correctly (401)")

    print("=" * 70)
    print("ALL 9 PDF GENERATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    test_pdf_generation_suite()
