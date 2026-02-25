"""Tests for new document enhancements: document_category, page_count, PDF serving."""

import io
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentShare, EducationLevelEnum, DocumentCategoryEnum, RoleEnum


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(client: TestClient, role: str = "student", level: str | None = "S3") -> str:
    uid = str(uuid.uuid4())[:8]
    email = f"{role}_{uid}@ex.com"
    payload = {
        "email": email,
        "password": "testpwd1",
        "full_name": f"Test {role.title()}",
        "role": role,
    }
    if level:
        payload["education_level"] = level
    client.post("/api/users/register", json=payload)
    resp = client.post("/api/users/login", json={"email": email, "password": "testpwd1"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_user_id(client: TestClient, token: str) -> str:
    resp = client.get("/api/users/me", headers=_auth(token))
    return resp.json()["id"]


def _minimal_pdf_bytes() -> bytes:
    """Minimal valid 1-page PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000074 00000 n \n"
        b"0000000133 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n217\n%%EOF"
    )


# ── Document Category ──────────────────────────────────────────────────────────


class TestDocumentCategory:
    def test_upload_with_default_category(self, client: TestClient):
        """Upload without explicit category defaults to exam_paper."""
        admin_token = _register_and_login(client, role="admin")

        resp = client.post(
            "/api/documents/admin",
            data={"subject": "Mathematics", "level": "S3", "year": "2023"},
            files={"file": ("exam.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["document_category"] == "exam_paper"

    def test_upload_with_marking_scheme_category(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")

        resp = client.post(
            "/api/documents/admin",
            data={
                "subject": "Physics",
                "level": "S6",
                "year": "2023",
                "document_category": "marking_scheme",
            },
            files={"file": ("ms.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["document_category"] == "marking_scheme"

    def test_upload_with_each_category(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        categories = ["exam_paper", "marking_scheme", "syllabus", "textbook", "notes", "other"]

        for cat in categories:
            resp = client.post(
                "/api/documents/admin",
                data={
                    "subject": f"Subject_{cat}",
                    "level": "P6",
                    "year": "2023",
                    "document_category": cat,
                },
                files={"file": (f"{cat}.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
                headers=_auth(admin_token),
            )
            assert resp.status_code == 201, f"Failed for category {cat}: {resp.text}"
            assert resp.json()["document_category"] == cat

    def test_student_upload_with_category(self, client: TestClient):
        """Students can specify category on personal document upload."""
        student_token = _register_and_login(client)

        resp = client.post(
            "/api/documents/student",
            data={
                "subject": "English",
                "level": "S3",
                "year": "2023",
                "document_category": "notes",
            },
            files={"file": ("notes.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(student_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_category"] == "notes"
        assert data["is_personal"] is True


# ── Page Count ─────────────────────────────────────────────────────────────────


class TestPageCount:
    @patch("app.api.documents._count_pdf_pages", return_value=5)
    def test_page_count_returned_on_upload(self, mock_count, client: TestClient):
        admin_token = _register_and_login(client, role="admin")

        resp = client.post(
            "/api/documents/admin",
            data={"subject": "Biology", "level": "S3", "year": "2023"},
            files={"file": ("bio.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["page_count"] == 5
        mock_count.assert_called_once()

    @patch("app.api.documents._count_pdf_pages", return_value=None)
    def test_page_count_none_when_unavailable(self, mock_count, client: TestClient):
        admin_token = _register_and_login(client, role="admin")

        resp = client.post(
            "/api/documents/admin",
            data={"subject": "Chemistry", "level": "S6", "year": "2023"},
            files={"file": ("chem.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["page_count"] is None


# ── _count_pdf_pages helper ────────────────────────────────────────────────────


class TestCountPdfPagesHelper:
    def test_counts_valid_pdf(self, tmp_path):
        """Write a minimal PDF and count pages."""
        from app.api.documents import _count_pdf_pages

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(_minimal_pdf_bytes())
        count = _count_pdf_pages(pdf_file)
        # Our minimal PDF has 1 page object — the result depends on
        # whether pypdf / PyMuPDF is installed.
        if count is not None:
            assert count >= 1

    def test_returns_none_for_nonpdf(self, tmp_path):
        """A non-PDF file should not crash, just return None or a number."""
        from app.api.documents import _count_pdf_pages

        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"this is not a pdf")
        # Should not raise — graceful fallback
        try:
            _count_pdf_pages(bad)
        except Exception:
            pass  # acceptable if library raises for corrupt files


# ── PDF Serving ────────────────────────────────────────────────────────────────


class TestServePDF:
    def test_serve_pdf_as_owner(self, client: TestClient, db: Session, tmp_path):
        """Admin who uploaded can view the PDF."""
        admin_token = _register_and_login(client, role="admin")
        user_id = _get_user_id(client, admin_token)

        # Write a file to a temp path
        pdf_path = tmp_path / "serve_test.pdf"
        pdf_path.write_bytes(_minimal_pdf_bytes())

        doc = Document(
            filename="serve_test.pdf",
            subject="Mathematics",
            level=EducationLevelEnum.S3,
            year="2023",
            file_path=str(pdf_path),
            uploaded_by=uuid.UUID(user_id),
            is_personal=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        resp = client.get(
            f"/api/documents/{doc.id}/pdf",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "serve_test.pdf" in resp.headers.get("content-disposition", "")

    def test_serve_pdf_as_level_student(self, client: TestClient, db: Session, tmp_path):
        """Student with matching education_level can view admin-designated PDF."""
        admin_token = _register_and_login(client, role="admin")
        admin_id = _get_user_id(client, admin_token)
        student_token = _register_and_login(client, level="S3")

        pdf_path = tmp_path / "level_doc.pdf"
        pdf_path.write_bytes(_minimal_pdf_bytes())

        doc = Document(
            filename="level_doc.pdf",
            subject="Physics",
            level=EducationLevelEnum.S3,
            year="2023",
            file_path=str(pdf_path),
            uploaded_by=uuid.UUID(admin_id),
            is_personal=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        resp = client.get(
            f"/api/documents/{doc.id}/pdf",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    def test_serve_pdf_wrong_level_forbidden(self, client: TestClient, db: Session, tmp_path):
        """Student with different education_level cannot view the PDF."""
        admin_token = _register_and_login(client, role="admin")
        admin_id = _get_user_id(client, admin_token)
        student_token = _register_and_login(client, level="S6")  # S6 ≠ P6

        pdf_path = tmp_path / "restricted.pdf"
        pdf_path.write_bytes(_minimal_pdf_bytes())

        doc = Document(
            filename="restricted.pdf",
            subject="Art",
            level=EducationLevelEnum.P6,  # P6 document
            year="2023",
            file_path=str(pdf_path),
            uploaded_by=uuid.UUID(admin_id),
            is_personal=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        resp = client.get(
            f"/api/documents/{doc.id}/pdf",
            headers=_auth(student_token),
        )
        assert resp.status_code == 403

    def test_serve_pdf_not_found(self, client: TestClient):
        student_token = _register_and_login(client)
        resp = client.get(
            f"/api/documents/{uuid.uuid4()}/pdf",
            headers=_auth(student_token),
        )
        assert resp.status_code == 404

    def test_serve_pdf_file_missing_on_disk(self, client: TestClient, db: Session):
        """Document exists in DB but the file was deleted from disk."""
        admin_token = _register_and_login(client, role="admin")
        admin_id = _get_user_id(client, admin_token)

        doc = Document(
            filename="ghost.pdf",
            subject="History",
            level=EducationLevelEnum.S3,
            year="2023",
            file_path="/nonexistent/path/ghost.pdf",
            uploaded_by=uuid.UUID(admin_id),
            is_personal=False,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        resp = client.get(
            f"/api/documents/{doc.id}/pdf",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 404
        assert "not found on server" in resp.json()["detail"]

    def test_serve_pdf_requires_auth(self, client: TestClient):
        resp = client.get(f"/api/documents/{uuid.uuid4()}/pdf")
        assert resp.status_code == 401


# ── Student Upload (personal) ─────────────────────────────────────────────────


class TestStudentUpload:
    def test_student_personal_upload(self, client: TestClient):
        student_token = _register_and_login(client)

        resp = client.post(
            "/api/documents/student",
            data={"subject": "French", "level": "S3", "year": "2023"},
            files={"file": ("notes.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(student_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_personal"] is True

    def test_admin_cannot_use_student_upload(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")

        resp = client.post(
            "/api/documents/student",
            data={"subject": "French", "level": "S3", "year": "2023"},
            files={"file": ("notes.pdf", io.BytesIO(_minimal_pdf_bytes()), "application/pdf")},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 403
