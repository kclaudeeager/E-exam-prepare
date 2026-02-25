"""Integration tests for document endpoints."""

import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Document, EducationLevelEnum


# ── Test Fixtures ─────────────────────────────────────────────────────────


def _create_admin_token(client: TestClient) -> str:
    """Helper: Create admin user and return JWT token."""
    unique_id = str(uuid.uuid4())[:8]
    email = f"admin_{unique_id}@ex.com"
    password = "pwd1"
    
    # Register
    client.post(
        "/api/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Admin User",
            "role": "admin",
        },
    )
    
    # Login to get token
    response = client.post(
        "/api/users/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_student_token(client: TestClient, level: str = "S3") -> str:
    """Helper: Create student user and return JWT token."""
    unique_id = str(uuid.uuid4())[:8]
    email = f"student_{unique_id}@ex.com"
    password = "pwd1"
    
    # Register
    client.post(
        "/api/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Student User",
            "role": "student",
            "education_level": level,
        },
    )
    
    # Login to get token
    response = client.post(
        "/api/users/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_pdf_file():
    """Helper: Create a minimal PDF file for testing."""
    # Minimal PDF header (won't be parsed, just tests file handling)
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000074 00000 n
0000000133 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
217
%%EOF"""
    return io.BytesIO(pdf_content)


# ── Tests ─────────────────────────────────────────────────────────────────


def test_upload_document_as_admin(client: TestClient, db: Session):
    """Test uploading a document as admin."""
    admin_token = _create_admin_token(client)

    pdf = _create_pdf_file()

    response = client.post(
        "/api/documents/admin",
        data={
            "subject": "Mathematics",
            "level": "S3",
            "year": "2023",
            "official_duration_minutes": "120",
            "instructions": "Answer all questions",
        },
        files={"file": ("exam.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == "Mathematics"
    assert data["level"] == "S3"
    assert data["year"] == "2023"
    assert data["official_duration_minutes"] == 120
    assert "id" in data
    assert data["ingestion_status"].upper() == "PENDING"


def test_upload_document_as_student_fails(client: TestClient):
    """Test that students cannot upload documents."""
    student_token = _create_student_token(client)
    pdf = _create_pdf_file()

    response = client.post(
        "/api/documents/admin",
        data={
            "subject": "Mathematics",
            "level": "S3",
            "year": "2023",
        },
        files={"file": ("exam.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {student_token}"},
    )

    # Should be forbidden or unauthorized
    assert response.status_code in [403, 401]


def test_upload_document_without_auth_fails(client: TestClient):
    """Test that unauthenticated users cannot upload."""
    pdf = _create_pdf_file()

    response = client.post(
        "/api/documents/admin",
        data={
            "subject": "Mathematics",
            "level": "S3",
            "year": "2023",
        },
        files={"file": ("exam.pdf", pdf, "application/pdf")},
    )

    assert response.status_code == 401


def test_list_documents(client: TestClient, db: Session):
    """Test listing documents."""
    admin_token = _create_admin_token(client)
    student_token = _create_student_token(client)

    # Upload a document
    pdf = _create_pdf_file()
    upload_response = client.post(
        "/api/documents/admin",
        data={
            "subject": "Mathematics",
            "level": "S3",
            "year": "2023",
        },
        files={"file": ("exam.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert upload_response.status_code == 201

    # List as student
    response = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["subject"] == "Mathematics"
    assert data[0]["level"] == "S3"


def test_list_documents_with_filters(client: TestClient, db: Session):
    """Test listing documents with subject/level filters."""
    admin_token = _create_admin_token(client)
    student_token = _create_student_token(client)

    # Upload multiple documents
    for subject, level in [("Mathematics", "S3"), ("Physics", "S3"), ("Biology", "S6")]:
        pdf = _create_pdf_file()
        client.post(
            "/api/documents/admin",
            data={
                "subject": subject,
                "level": level,
                "year": "2023",
            },
            files={"file": (f"{subject}.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    # Filter by subject
    response = client.get(
        "/api/documents?subject=Mathematics",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert all(doc["subject"] == "Mathematics" for doc in data)

    # Filter by level
    response = client.get(
        "/api/documents?level=S6",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert all(doc["level"] == "S6" for doc in data)


def test_list_documents_without_auth_fails(client: TestClient):
    """Test that unauthenticated users cannot list documents."""
    response = client.get("/api/documents")
    assert response.status_code == 401


def test_get_document_by_id(client: TestClient, db: Session):
    """Test retrieving a specific document by ID."""
    admin_token = _create_admin_token(client)
    student_token = _create_student_token(client)

    # Upload a document
    pdf = _create_pdf_file()
    upload_response = client.post(
        "/api/documents/admin",
        data={
            "subject": "Mathematics",
            "level": "S3",
            "year": "2023",
            "official_duration_minutes": "150",
        },
        files={"file": ("exam.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert upload_response.status_code == 201

    doc_id = upload_response.json()["id"]

    # Retrieve by ID as student
    response = client.get(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["subject"] == "Mathematics"
    assert data["level"] == "S3"
    assert data["official_duration_minutes"] == 150


def test_get_document_not_found(client: TestClient):
    """Test retrieving a non-existent document."""
    student_token = _create_student_token(client)
    fake_id = str(uuid.uuid4())

    response = client.get(
        f"/api/documents/{fake_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 404


def test_get_document_without_auth_fails(client: TestClient):
    """Test that unauthenticated users cannot retrieve documents."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/documents/{fake_id}")
    assert response.status_code == 401


def test_upload_document_with_optional_fields(client: TestClient):
    """Test uploading with all optional fields."""
    admin_token = _create_admin_token(client)
    pdf = _create_pdf_file()

    response = client.post(
        "/api/documents/admin",
        data={
            "subject": "English",
            "level": "S3",
            "year": "2022",
            "official_duration_minutes": "180",
            "instructions": "Section A: 30 marks, Section B: 40 marks",
        },
        files={"file": ("english.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["official_duration_minutes"] == 180


def test_upload_document_minimal_fields(client: TestClient):
    """Test uploading with minimal required fields only."""
    admin_token = _create_admin_token(client)
    pdf = _create_pdf_file()

    response = client.post(
        "/api/documents/admin",
        data={
            "subject": "History",
            "level": "S3",
            "year": "2021",
        },
        files={"file": ("history.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == "History"
    assert data["official_duration_minutes"] is None


def test_pagination_list_documents(client: TestClient):
    """Test pagination when listing documents."""
    admin_token = _create_admin_token(client)
    student_token = _create_student_token(client)

    # Upload 5 documents
    for i in range(5):
        pdf = _create_pdf_file()
        client.post(
            "/api/documents/admin",
            data={
                "subject": "Mathematics",
                "level": "S3",
                "year": "2023",
            },
            files={"file": (f"exam_{i}.pdf", pdf, "application/pdf")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    # Get first page (limit=2)
    response = client.get(
        "/api/documents?limit=2&skip=0",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    assert len(response.json()) <= 2

    # Get second page (limit=2)
    response = client.get(
        "/api/documents?limit=2&skip=2",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 200
    # Should have up to 2 more documents
    data = response.json()
    assert len(data) <= 2
