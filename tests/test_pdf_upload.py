import fitz
import io
import urllib.request
import json

def test_upload():
    # 1. Create a real in-memory PDF resume
    doc = fitz.open()
    page = doc.new_page()
    text = """
    Vignesh Sundaram
    Email: vignesh@mcet.in | Phone: +91 98989 12345
    Education: B.E. Computer Science and Engineering, MCET | CGPA: 8.75
    
    Technical Skills:
    React, JavaScript, TypeScript, Node.js, Express.js, MongoDB, HTML, CSS, Git
    
    Academic Projects:
    - Campus Placement SaaS Platform: Built using React, Node.js, and MongoDB with JWT auth.
    - Cloud Task Scheduler: React web application with responsive UI.
    
    Internship Experience:
    - Cognizant Technology Solutions: Full Stack Web Developer Intern for 3 months.
    
    Certifications:
    - Meta Front-End Developer Professional Certificate
    """
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode("utf-8"))
    body.write(b'Content-Disposition: form-data; name="file"; filename="vignesh_resume.pdf"\r\n')
    body.write(b"Content-Type: application/pdf\r\n\r\n")
    body.write(pdf_bytes)
    body.write(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/candidates/9/resume",
        data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print("[PASS] PDF Resume Uploaded and Parsed Successfully!")
        print("Response:", json.dumps(result, indent=2))

if __name__ == "__main__":
    test_upload()
