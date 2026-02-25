"""Integration tests for the practice session endpoints.

Covers:
  POST /api/practice/start
  GET  /api/practice/{id}/next
  POST /api/practice/{id}/answer
  POST /api/practice/{id}/complete
  GET  /api/practice/{id}
  GET  /api/practice/

RAG client calls are mocked — tests focus on request routing, DB state,
grading flow, and response shapes.
"""

import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Document,
    EducationLevelEnum,
    IngestionStatusEnum,
    PracticeSession,
    PracticeStatusEnum,
    Question,
    QuestionTypeEnum,
    Subject,
    User,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _register_and_login(client: TestClient, role: str = "student", level: str | None = "S6") -> str:
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


def _create_subject(db: Session, name: str = "Mathematics", level: str = "S6") -> Subject:
    s = Subject(name=name, level=EducationLevelEnum(level), icon="🔢")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _create_ingested_document(db: Session, user_id: str, subject: str = "Mathematics", level: str = "S6") -> Document:
    """Create a document with COMPLETED ingestion status for practice."""
    doc = Document(
        filename="test_exam.pdf",
        subject=subject,
        level=EducationLevelEnum(level),
        year="2023",
        file_path="/fake/path/test_exam.pdf",
        uploaded_by=uuid.UUID(user_id),
        ingestion_status=IngestionStatusEnum.COMPLETED,
        collection_name=f"{level}_{subject}".replace(" ", "_"),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _create_pending_document(db: Session, user_id: str) -> Document:
    doc = Document(
        filename="pending.pdf",
        subject="Physics",
        level=EducationLevelEnum.S6,
        year="2023",
        file_path="/fake/path/pending.pdf",
        uploaded_by=uuid.UUID(user_id),
        ingestion_status=IngestionStatusEnum.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _create_questions_for_doc(db: Session, doc: Document, count: int = 3) -> list[Question]:
    """Insert test questions linked to a document."""
    questions = []
    for i in range(count):
        q = Question(
            text=f"What is {i + 1} + {i + 1}?",
            question_type=QuestionTypeEnum.SHORT_ANSWER,
            correct_answer=str((i + 1) * 2),
            difficulty="easy",
            document_id=doc.id,
        )
        db.add(q)
        questions.append(q)
    db.commit()
    for q in questions:
        db.refresh(q)
    return questions


# ── Mock RAG helpers ───────────────────────────────────────────────────────────


def _mock_rag_grade_correct():
    """Return a mock RAG client that grades everything as correct."""
    mock_client = MagicMock()
    mock_client.retrieve.return_value = {
        "results": [
            {
                "content": "The answer is 4.",
                "score": 0.95,
                "metadata": {"page_number": 1, "file_name": "exam.pdf"},
            }
        ]
    }
    mock_client.query_direct.return_value = {
        "answer": json.dumps({
            "is_correct": True,
            "score": 1.0,
            "feedback": "Correct! Great job.",
        })
    }
    return mock_client


def _mock_rag_grade_incorrect():
    """Return a mock RAG client that grades everything as incorrect."""
    mock_client = MagicMock()
    mock_client.retrieve.return_value = {"results": []}
    mock_client.query_direct.return_value = {
        "answer": json.dumps({
            "is_correct": False,
            "score": 0.0,
            "feedback": "That's not right. The correct answer is 4.",
            "correct_answer_explanation": "2 + 2 = 4",
        })
    }
    return mock_client


def _mock_rag_generate_question():
    """Return a mock RAG client that generates a question via query."""
    mock_client = MagicMock()
    mock_client.query.return_value = {
        "answer": json.dumps({
            "text": "What is the capital of Rwanda?",
            "question_type": "short-answer",
            "correct_answer": "Kigali",
            "topic": "Geography",
        })
    }
    return mock_client


# ── Start Practice Session ─────────────────────────────────────────────────────


class TestStartPractice:
    def test_start_with_subject(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db)

        resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 5},
            headers=_auth(student_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == str(subject.id)
        assert data["total_questions"] == 5
        assert data["answered_count"] == 0
        assert data["correct_count"] == 0
        assert data["status"] == "in_progress"
        assert "id" in data

    def test_start_with_document(self, client: TestClient, db: Session):
        admin_token = _register_and_login(client, role="admin")
        user_id = _get_user_id(client, admin_token)
        doc = _create_ingested_document(db, user_id)

        student_token = _register_and_login(client)
        resp = client.post(
            "/api/practice/start",
            json={"document_id": str(doc.id), "question_count": 3},
            headers=_auth(student_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_id"] == str(doc.id)
        assert data["total_questions"] == 3

    def test_start_with_pending_document_fails(self, client: TestClient, db: Session):
        admin_token = _register_and_login(client, role="admin")
        user_id = _get_user_id(client, admin_token)
        doc = _create_pending_document(db, user_id)

        student_token = _register_and_login(client)
        resp = client.post(
            "/api/practice/start",
            json={"document_id": str(doc.id)},
            headers=_auth(student_token),
        )
        assert resp.status_code == 400
        assert "not been ingested" in resp.json()["detail"]

    def test_start_with_nonexistent_document(self, client: TestClient):
        student_token = _register_and_login(client)
        resp = client.post(
            "/api/practice/start",
            json={"document_id": str(uuid.uuid4())},
            headers=_auth(student_token),
        )
        assert resp.status_code == 404

    def test_start_with_nonexistent_subject(self, client: TestClient):
        student_token = _register_and_login(client)
        resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(uuid.uuid4())},
            headers=_auth(student_token),
        )
        assert resp.status_code == 404

    def test_start_requires_auth(self, client: TestClient):
        resp = client.post("/api/practice/start", json={"question_count": 5})
        assert resp.status_code == 401

    def test_start_default_question_count(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="English", level="S3")
        resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id)},
            headers=_auth(student_token),
        )
        assert resp.status_code == 201
        assert resp.json()["total_questions"] == 5  # default


# ── Get Next Question ──────────────────────────────────────────────────────────


class TestNextQuestion:
    def test_next_question_from_db(self, client: TestClient, db: Session):
        """When the document has questions in the DB, they should be served."""
        admin_token = _register_and_login(client, role="admin")
        user_id = _get_user_id(client, admin_token)
        doc = _create_ingested_document(db, user_id)
        _create_questions_for_doc(db, doc, count=3)

        student_token = _register_and_login(client)
        # Start session
        start_resp = client.post(
            "/api/practice/start",
            json={"document_id": str(doc.id), "question_count": 3},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Get first question
        resp = client.get(
            f"/api/practice/{session_id}/next",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_number"] == 1
        assert "text" in data
        assert data["total_questions"] == 3

    @patch("app.api.practice.get_rag_client")
    def test_next_question_from_rag(self, mock_get_rag, client: TestClient, db: Session):
        """When no DB questions exist, fall back to RAG-generated question."""
        mock_get_rag.return_value = _mock_rag_generate_question()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Geography", level="S3")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.get(
            f"/api/practice/{session_id}/next",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "What is the capital of Rwanda?"
        assert data["question_number"] == 1

    def test_next_question_session_not_found(self, client: TestClient):
        student_token = _register_and_login(client)
        resp = client.get(
            f"/api/practice/{uuid.uuid4()}/next",
            headers=_auth(student_token),
        )
        assert resp.status_code == 404

    def test_next_question_requires_auth(self, client: TestClient):
        resp = client.get(f"/api/practice/{uuid.uuid4()}/next")
        assert resp.status_code == 401


# ── Submit Answer ──────────────────────────────────────────────────────────────


class TestSubmitAnswer:
    @patch("app.api.practice.get_rag_client")
    def test_submit_correct_answer(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Maths", level="P6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={
                "question_text": "What is 2 + 2?",
                "answer_text": "4",
            },
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is True
        assert data["score"] == 1.0
        assert data["feedback"]
        assert data["student_answer"] == "4"
        assert data["question_text"] == "What is 2 + 2?"
        assert data["was_handwritten"] is False

    @patch("app.api.practice.get_rag_client")
    def test_submit_incorrect_answer(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_incorrect()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Sci", level="P6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "What is 2 + 2?", "answer_text": "5"},
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        assert data["score"] == 0.0

    @patch("app.api.practice.get_rag_client")
    def test_submit_answer_updates_counters(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Eng", level="S3")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 3},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Submit first answer
        client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1", "answer_text": "A1"},
            headers=_auth(student_token),
        )

        # Check session — should have 1 answered, 1 correct
        session_resp = client.get(
            f"/api/practice/{session_id}",
            headers=_auth(student_token),
        )
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["answered_count"] == 1
        assert session_data["correct_count"] == 1

    @patch("app.api.practice.get_rag_client")
    def test_submit_auto_completes_when_all_answered(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Bio", level="S6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 1},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Submit the only answer
        client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1", "answer_text": "A1"},
            headers=_auth(student_token),
        )

        # Session should auto-complete
        session_resp = client.get(
            f"/api/practice/{session_id}",
            headers=_auth(student_token),
        )
        assert session_resp.json()["status"] == "completed"
        assert session_resp.json()["completed_at"] is not None

    def test_submit_empty_answer_fails(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Hist", level="S3")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1"},
            headers=_auth(student_token),
        )
        assert resp.status_code == 400
        assert "No answer provided" in resp.json()["detail"]

    @patch("app.api.practice.get_rag_client")
    def test_submit_answer_with_source_references(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Chem", level="S6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1", "answer_text": "answer"},
            headers=_auth(student_token),
        )
        data = resp.json()
        assert isinstance(data["source_references"], list)

    @patch("app.api.practice._ocr_handwritten_answer", return_value="4")
    @patch("app.api.practice.get_rag_client")
    def test_submit_handwritten_answer(self, mock_get_rag, mock_ocr, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Art", level="P6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Submit with image (base64 encoded)
        import base64
        fake_image = base64.b64encode(b"fake_image_data").decode()

        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={
                "question_text": "What is 2+2?",
                "answer_image_base64": fake_image,
            },
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["was_handwritten"] is True
        assert data["ocr_text"] == "4"

    @patch("app.api.practice.get_rag_client")
    def test_submit_to_completed_session_fails(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Music", level="P6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 1},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Complete the session by answering all questions
        client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1", "answer_text": "A1"},
            headers=_auth(student_token),
        )

        # Try submitting again
        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q2", "answer_text": "A2"},
            headers=_auth(student_token),
        )
        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"]


# ── Complete Session ───────────────────────────────────────────────────────────


class TestCompleteSession:
    def test_complete_session(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="PE", level="S3")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 5},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        resp = client.post(
            f"/api/practice/{session_id}/complete",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    def test_complete_session_not_found(self, client: TestClient):
        student_token = _register_and_login(client)
        resp = client.post(
            f"/api/practice/{uuid.uuid4()}/complete",
            headers=_auth(student_token),
        )
        assert resp.status_code == 404


# ── Get Session Detail ─────────────────────────────────────────────────────────


class TestGetSession:
    @patch("app.api.practice.get_rag_client")
    def test_get_session_detail_with_answers(self, mock_get_rag, client: TestClient, db: Session):
        mock_get_rag.return_value = _mock_rag_grade_correct()

        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Comp", level="S6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 2},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Submit answer
        client.post(
            f"/api/practice/{session_id}/answer",
            json={"question_text": "Q1", "answer_text": "A1"},
            headers=_auth(student_token),
        )

        # Get full detail
        resp = client.get(
            f"/api/practice/{session_id}",
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answered_count"] == 1
        assert len(data["answers"]) == 1
        assert data["answers"][0]["question_text"] == "Q1"
        assert data["answers"][0]["student_answer"] == "A1"
        assert "feedback" in data["answers"][0]

    def test_get_session_other_student_fails(self, client: TestClient, db: Session):
        student1_token = _register_and_login(client, level="S6")
        student2_token = _register_and_login(client, level="S6")
        subject = _create_subject(db, name="Econ", level="S6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id)},
            headers=_auth(student1_token),
        )
        session_id = start_resp.json()["id"]

        # Other student tries to access
        resp = client.get(
            f"/api/practice/{session_id}",
            headers=_auth(student2_token),
        )
        assert resp.status_code == 404  # Session "not found" for this student

    def test_get_session_accuracy_calculation(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Stats", level="S6")

        start_resp = client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id), "question_count": 3},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Submit two correct, one incorrect
        with patch("app.api.practice.get_rag_client") as mock_rag:
            mock_rag.return_value = _mock_rag_grade_correct()
            client.post(
                f"/api/practice/{session_id}/answer",
                json={"question_text": "Q1", "answer_text": "A1"},
                headers=_auth(student_token),
            )
            client.post(
                f"/api/practice/{session_id}/answer",
                json={"question_text": "Q2", "answer_text": "A2"},
                headers=_auth(student_token),
            )

        with patch("app.api.practice.get_rag_client") as mock_rag:
            mock_rag.return_value = _mock_rag_grade_incorrect()
            client.post(
                f"/api/practice/{session_id}/answer",
                json={"question_text": "Q3", "answer_text": "wrong"},
                headers=_auth(student_token),
            )

        # Check accuracy: 2/3 ≈ 0.6667
        resp = client.get(f"/api/practice/{session_id}", headers=_auth(student_token))
        data = resp.json()
        assert data["correct_count"] == 2
        assert data["answered_count"] == 3
        assert abs(data["accuracy"] - 0.6667) < 0.01


# ── List Sessions ──────────────────────────────────────────────────────────────


class TestListSessions:
    def test_list_sessions(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Kiny", level="P6")

        # Create 3 sessions
        for _ in range(3):
            client.post(
                "/api/practice/start",
                json={"subject_id": str(subject.id), "question_count": 2},
                headers=_auth(student_token),
            )

        resp = client.get("/api/practice", headers=_auth(student_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be ordered by created_at desc
        for session in data:
            assert session["status"] == "in_progress"

    def test_list_sessions_only_own(self, client: TestClient, db: Session):
        student1_token = _register_and_login(client, level="P6")
        student2_token = _register_and_login(client, level="P6")
        subject = _create_subject(db, name="French", level="P6")

        # Student 1 creates a session
        client.post(
            "/api/practice/start",
            json={"subject_id": str(subject.id)},
            headers=_auth(student1_token),
        )

        # Student 2 should see no sessions
        resp = client.get("/api/practice", headers=_auth(student2_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_list_sessions_pagination(self, client: TestClient, db: Session):
        student_token = _register_and_login(client)
        subject = _create_subject(db, name="Rel", level="S3")

        for _ in range(5):
            client.post(
                "/api/practice/start",
                json={"subject_id": str(subject.id)},
                headers=_auth(student_token),
            )

        resp = client.get("/api/practice?limit=2&skip=0", headers=_auth(student_token))
        assert len(resp.json()) == 2

        resp = client.get("/api/practice?limit=2&skip=2", headers=_auth(student_token))
        assert len(resp.json()) == 2

    def test_list_sessions_requires_auth(self, client: TestClient):
        resp = client.get("/api/practice")
        assert resp.status_code == 401


# ── MCQ Quick Grading ──────────────────────────────────────────────────────────


class TestMCQGrading:
    def test_mcq_correct_grading(self, client: TestClient, db: Session):
        """MCQ grading bypasses RAG — tests the direct comparison path."""
        admin_token = _register_and_login(client, role="admin")
        user_id = _get_user_id(client, admin_token)
        doc = _create_ingested_document(db, user_id)

        # Create an MCQ question
        q = Question(
            text="What is the capital of Rwanda?",
            question_type=QuestionTypeEnum.MCQ,
            options="Kigali|Nairobi|Kampala|Dar es Salaam",
            correct_answer="Kigali",
            document_id=doc.id,
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        student_token = _register_and_login(client)
        start_resp = client.post(
            "/api/practice/start",
            json={"document_id": str(doc.id), "question_count": 1},
            headers=_auth(student_token),
        )
        session_id = start_resp.json()["id"]

        # Answer correctly — no RAG mocking needed for MCQ
        resp = client.post(
            f"/api/practice/{session_id}/answer",
            json={
                "question_id": str(q.id),
                "question_text": q.text,
                "answer_text": "Kigali",
            },
            headers=_auth(student_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is True
        assert data["score"] == 1.0
        assert "✅" in data["feedback"]


# ── Internal Helper Unit Tests ─────────────────────────────────────────────────


class TestParseGradeJson:
    """Test the _parse_grade_json helper directly."""

    def test_parse_valid_json(self):
        from app.api.practice import _parse_grade_json
        result = _parse_grade_json('{"is_correct": true, "score": 1.0, "feedback": "Good"}')
        assert result["is_correct"] is True
        assert result["score"] == 1.0

    def test_parse_json_in_markdown_block(self):
        from app.api.practice import _parse_grade_json
        raw = '```json\n{"is_correct": false, "score": 0.5, "feedback": "Partial"}\n```'
        result = _parse_grade_json(raw)
        assert result["is_correct"] is False
        assert result["score"] == 0.5

    def test_parse_json_with_surrounding_text(self):
        from app.api.practice import _parse_grade_json
        raw = 'Here is my assessment:\n{"is_correct": true, "score": 0.8, "feedback": "Almost"}\nEnd.'
        result = _parse_grade_json(raw)
        assert result["is_correct"] is True

    def test_parse_invalid_json_returns_fallback(self):
        from app.api.practice import _parse_grade_json
        result = _parse_grade_json("This is not JSON at all")
        assert result["is_correct"] is False
        assert result["score"] == 0.0
        assert result["feedback"] == "This is not JSON at all"

    def test_parse_empty_string(self):
        from app.api.practice import _parse_grade_json
        result = _parse_grade_json("")
        assert result["is_correct"] is False
        assert result["score"] == 0.0
