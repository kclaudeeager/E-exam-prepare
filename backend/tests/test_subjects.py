"""Integration tests for subject management and enrollment endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Subject, EducationLevelEnum, Document


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(client: TestClient, role: str = "student", level: str | None = "S6") -> str:
    """Create a user and return their JWT token."""
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


def _seed_subject(db: Session, name: str = "Mathematics", level: str = "S6") -> Subject:
    """Directly insert a subject for tests that need it."""
    s = Subject(name=name, level=EducationLevelEnum(level), icon="🔢")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ── Seed Defaults ──────────────────────────────────────────────────────────────


class TestSeedDefaults:
    def test_seed_defaults_as_admin(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        resp = client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] > 0
        assert "Seeded" in data["message"]

    def test_seed_defaults_idempotent(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        resp1 = client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))
        count1 = resp1.json()["created"]
        resp2 = client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))
        assert resp2.json()["created"] == 0  # No new subjects
        assert resp2.status_code == 201

    def test_seed_defaults_requires_admin(self, client: TestClient):
        student_token = _register_and_login(client, role="student")
        resp = client.post("/api/subjects/seed-defaults", headers=_auth(student_token))
        assert resp.status_code == 403

    def test_seed_defaults_requires_auth(self, client: TestClient):
        resp = client.post("/api/subjects/seed-defaults")
        assert resp.status_code == 401


# ── Create Subject ─────────────────────────────────────────────────────────────


class TestCreateSubject:
    def test_create_subject_as_admin(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        name = f"Astrology_{uid}"
        resp = client.post(
            "/api/subjects",
            json={"name": name, "level": "S6", "description": "Star gazing", "icon": "⚡"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["level"] == "S6"
        assert data["description"] == "Star gazing"
        assert data["icon"] == "⚡"
        assert data["document_count"] == 0
        assert "id" in data

    def test_create_duplicate_subject_fails(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        payload = {"name": f"Dup_{uid}", "level": "S3"}
        client.post("/api/subjects", json=payload, headers=_auth(admin_token))
        resp = client.post("/api/subjects", json=payload, headers=_auth(admin_token))
        assert resp.status_code == 409

    def test_create_same_name_different_level_ok(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        name = f"Botany_{uid}"
        resp1 = client.post(
            "/api/subjects",
            json={"name": name, "level": "S3"},
            headers=_auth(admin_token),
        )
        resp2 = client.post(
            "/api/subjects",
            json={"name": name, "level": "S6"},
            headers=_auth(admin_token),
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_create_subject_requires_admin(self, client: TestClient):
        student_token = _register_and_login(client, role="student")
        resp = client.post(
            "/api/subjects",
            json={"name": "Art", "level": "P6"},
            headers=_auth(student_token),
        )
        assert resp.status_code == 403


# ── List Subjects ──────────────────────────────────────────────────────────────


class TestListSubjects:
    def test_list_subjects(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        # Seed to ensure we have data
        client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))

        student_token = _register_and_login(client, role="student", level="S6")
        resp = client.get("/api/subjects", headers=_auth(student_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # S6 student should see S6 subjects
        for s in data:
            assert s["level"] == "S6"

    def test_list_subjects_filter_by_level(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))

        resp = client.get("/api/subjects?level=P6", headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["level"] == "P6" for s in data)
        assert len(data) > 0

    def test_list_subjects_admin_sees_all(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))

        resp = client.get("/api/subjects", headers=_auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        levels = set(s["level"] for s in data)
        # Admin should see subjects across multiple levels
        assert len(levels) > 1

    def test_list_subjects_shows_enrollment_status(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        client.post("/api/subjects/seed-defaults", headers=_auth(admin_token))

        student_token = _register_and_login(client, role="student", level="S6")
        resp = client.get("/api/subjects", headers=_auth(student_token))
        data = resp.json()
        assert all("enrolled" in s for s in data)
        # Initially all should be unenrolled
        assert all(s["enrolled"] is False for s in data)

    def test_list_subjects_requires_auth(self, client: TestClient):
        resp = client.get("/api/subjects")
        assert resp.status_code == 401


# ── Get Subject ────────────────────────────────────────────────────────────────


class TestGetSubject:
    def test_get_subject_detail(self, client: TestClient, db: Session):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        name = f"Geology_{uid}"
        create_resp = client.post(
            "/api/subjects",
            json={"name": name, "level": "S3", "icon": "🌍"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        student_token = _register_and_login(client, role="student", level="S3")
        resp = client.get(f"/api/subjects/{subject_id}", headers=_auth(student_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == subject_id
        assert data["name"] == name
        assert data["collection_name"] == f"S3_{name}"

    def test_get_subject_not_found(self, client: TestClient):
        student_token = _register_and_login(client, role="student")
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/subjects/{fake_id}", headers=_auth(student_token))
        assert resp.status_code == 404

    def test_get_subject_collection_name_format(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        name = f"Civic Studies {uid}"
        create_resp = client.post(
            "/api/subjects",
            json={"name": name, "level": "P6"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]
        resp = client.get(f"/api/subjects/{subject_id}", headers=_auth(admin_token))
        # Spaces replaced with underscores
        assert resp.json()["collection_name"] == f"P6_{name}".replace(" ", "_")


# ── Enrollment ─────────────────────────────────────────────────────────────────


class TestEnrollment:
    def test_enroll_in_subject(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        create_resp = client.post(
            "/api/subjects",
            json={"name": f"Lang_{uid}", "level": "S6"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        student_token = _register_and_login(client, role="student", level="S6")
        resp = client.post(
            "/api/subjects/enroll",
            json={"subject_ids": [subject_id]},
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enrolled_count"] == 1

        # Verify enrollment is reflected in list
        list_resp = client.get("/api/subjects?level=S6", headers=_auth(student_token))
        subjects = list_resp.json()
        enrolled = [s for s in subjects if s["id"] == subject_id]
        assert len(enrolled) == 1
        assert enrolled[0]["enrolled"] is True

    def test_enroll_idempotent(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        create_resp = client.post(
            "/api/subjects",
            json={"name": f"Hist_{uid}", "level": "S6"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        student_token = _register_and_login(client, role="student", level="S6")
        client.post(
            "/api/subjects/enroll",
            json={"subject_ids": [subject_id]},
            headers=_auth(student_token),
        )
        # Second enrollment should succeed with 0 new enrollments
        resp = client.post(
            "/api/subjects/enroll",
            json={"subject_ids": [subject_id]},
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        assert resp.json()["enrolled_count"] == 0

    def test_enroll_multiple_subjects(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        ids = []
        for name in ["Math", "Science"]:
            r = client.post(
                "/api/subjects",
                json={"name": name, "level": "P6"},
                headers=_auth(admin_token),
            )
            ids.append(r.json()["id"])

        student_token = _register_and_login(client, role="student", level="P6")
        resp = client.post(
            "/api/subjects/enroll",
            json={"subject_ids": ids},
            headers=_auth(student_token),
        )
        assert resp.json()["enrolled_count"] == 2

    def test_enroll_admin_forbidden(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        create_resp = client.post(
            "/api/subjects",
            json={"name": f"Econ_{uid}", "level": "S6"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]
        resp = client.post(
            "/api/subjects/enroll",
            json={"subject_ids": [subject_id]},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 403

    def test_unenroll_from_subject(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        create_resp = client.post(
            "/api/subjects",
            json={"name": f"Lit_{uid}", "level": "S6"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        student_token = _register_and_login(client, role="student", level="S6")
        # Enroll
        client.post(
            "/api/subjects/enroll",
            json={"subject_ids": [subject_id]},
            headers=_auth(student_token),
        )
        # Unenroll
        resp = client.delete(
            f"/api/subjects/enroll/{subject_id}",
            headers=_auth(student_token),
        )
        assert resp.status_code == 204

        # Verify unenrolled
        list_resp = client.get("/api/subjects?level=S6", headers=_auth(student_token))
        subjects = list_resp.json()
        enrolled = [s for s in subjects if s["id"] == subject_id]
        if enrolled:
            assert enrolled[0]["enrolled"] is False

    def test_unenroll_nonexistent_is_safe(self, client: TestClient):
        student_token = _register_and_login(client, role="student")
        fake_id = str(uuid.uuid4())
        resp = client.delete(
            f"/api/subjects/enroll/{fake_id}",
            headers=_auth(student_token),
        )
        # Should not error — just a no-op
        assert resp.status_code == 204


# ── Subject Documents ──────────────────────────────────────────────────────────


class TestSubjectDocuments:
    def test_get_subject_documents_empty(self, client: TestClient):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        create_resp = client.post(
            "/api/subjects",
            json={"name": f"Fren_{uid}", "level": "S3"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        student_token = _register_and_login(client, role="student", level="S3")
        resp = client.get(
            f"/api/subjects/{subject_id}/documents",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_subject_documents_returns_matching_docs(self, client: TestClient, db: Session):
        admin_token = _register_and_login(client, role="admin")
        uid = str(uuid.uuid4())[:6]
        subject_name = f"MathDocs_{uid}"
        create_resp = client.post(
            "/api/subjects",
            json={"name": subject_name, "level": "S3"},
            headers=_auth(admin_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        subject_id = create_resp.json()["id"]

        # Upload a document matching the subject
        import io
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
        pdf = io.BytesIO(pdf_content)
        upload_resp = client.post(
            "/api/documents/admin",
            data={"subject": subject_name, "level": "S3", "year": "2023"},
            files={"file": ("math.pdf", pdf, "application/pdf")},
            headers=_auth(admin_token),
        )
        assert upload_resp.status_code == 201

        # Now the subject documents endpoint should return it
        student_token = _register_and_login(client, role="student", level="S3")
        resp = client.get(
            f"/api/subjects/{subject_id}/documents",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1
        assert docs[0]["subject"] == subject_name

    def test_get_subject_documents_not_found(self, client: TestClient):
        student_token = _register_and_login(client, role="student")
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/subjects/{fake_id}/documents",
            headers=_auth(student_token),
        )
        assert resp.status_code == 404
