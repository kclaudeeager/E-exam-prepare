"""Quiz generation routes.

Supports three modes (see copilot-instructions.md):
  - adaptive      → weak‑topic‑focused practice
  - topic-focused → random from subscribed topics
  - real-exam     → full exam with official timing
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from app.api.deps import get_current_user
from app.config import settings
from app.db.models import (
    Document,
    EducationLevelEnum,
    IngestionStatusEnum,
    Progress,
    Question,
    QuestionTypeEnum,
    Quiz,
    QuizModeEnum,
    QuizQuestion,
    Topic,
    User,
)
from app.db.session import get_db
from app.schemas.quiz import QuestionRead, QuizGenerateRequest, QuizRead
from app.services.rag_client import get_rag_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── RAG-based question generation ────────────────────────────────────────────

_QUESTION_GEN_PROMPT = """\
You are an exam question generator. Based on the exam content provided, generate exactly {count} \
well-structured exam questions. Return ONLY a JSON array, no other text.

Each question object must have:
- "text": the question text
- "question_type": "mcq" or "short_answer"
- "options": for mcq, a list of 4 options (strings). For short_answer, null.
- "correct_answer": for mcq, the letter (A/B/C/D). For short_answer, the expected answer.
- "topic": the topic or subject area this question covers
- "difficulty": "easy", "medium", or "hard"

{topic_hint}

Important: Questions must be based on the exam content. Make them educational and clear.
Return ONLY valid JSON array like: [{{"text":"...","question_type":"mcq","options":["...","...","...","..."],"correct_answer":"B","topic":"...","difficulty":"medium"}}]
"""


def _get_best_collection(db: Session) -> str | None:
    """Find a RAG collection from an ingested document."""
    doc = (
        db.query(Document)
        .filter(Document.ingestion_status == IngestionStatusEnum.COMPLETED)
        .order_by(Document.created_at.desc())
        .first()
    )
    if doc:
        return f"{doc.level.value}_{doc.subject}".replace(" ", "_")
    return None


def _get_or_create_topic(db: Session, name: str, subject: str = "General") -> Topic:
    """Get existing topic or create a new one."""
    topic = db.query(Topic).filter(Topic.name == name, Topic.subject == subject).first()
    if not topic:
        # Also check by name alone (less strict)
        topic = db.query(Topic).filter(Topic.name == name).first()
    if not topic:
        topic = Topic(name=name, subject=subject)
        db.add(topic)
        db.flush()
    return topic


def _get_or_create_rag_document(db: Session, uploader_id: uuid.UUID) -> Document:
    """Get or create a placeholder document for RAG-generated questions."""
    doc = db.query(Document).filter(Document.filename == "RAG_Generated.pdf").first()
    if not doc:
        doc = Document(
            filename="RAG_Generated.pdf",
            subject="General",
            level=EducationLevelEnum.S3,
            year="2024",
            file_path="generated",
            uploaded_by=uploader_id,
            ingestion_status=IngestionStatusEnum.COMPLETED,
        )
        db.add(doc)
        db.flush()
    return doc


def _parse_questions_json(raw: str) -> list[dict]:
    """Extract a JSON array from the LLM response, even if wrapped in markdown."""
    text = raw.strip()
    # Strip markdown code fences if present
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("["):
                text = stripped
                break
    # Find the JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("Failed to parse questions JSON from LLM response")
        return []


def _generate_questions_via_rag(
    db: Session,
    uploader_id: uuid.UUID,
    count: int = 10,
    topic_names: list[str] | None = None,
    collection: str | None = None,
) -> list[Question]:
    """
    Use the RAG service to generate structured exam questions from ingested content.
    Returns a list of Question ORM objects (already added to session).
    """
    client = get_rag_client()

    # Determine collection and subject
    subject = "General"
    if not collection:
        doc = (
            db.query(Document)
            .filter(Document.ingestion_status == IngestionStatusEnum.COMPLETED)
            .order_by(Document.created_at.desc())
            .first()
        )
        if doc:
            collection = f"{doc.level.value}_{doc.subject}".replace(" ", "_")
            subject = doc.subject
    if not collection:
        logger.warning("No ingested collections found for question generation")
        return []

    topic_hint = ""
    if topic_names:
        topic_hint = f"Focus on these topics: {', '.join(topic_names)}."

    prompt = _QUESTION_GEN_PROMPT.format(count=count, topic_hint=topic_hint)

    try:
        result = client.query(question=prompt, collection=collection, top_k=15)
    except Exception as e:
        logger.error("RAG query failed: %s", e)
        return []

    answer_text = result.get("answer", "")
    parsed = _parse_questions_json(answer_text)

    if not parsed:
        logger.warning("RAG returned no parseable questions. Raw: %s", answer_text[:200])
        return []

    # Persist questions
    rag_doc = _get_or_create_rag_document(db, uploader_id)
    new_questions: list[Question] = []

    for item in parsed[:count]:
        text = item.get("text", "").strip()
        if not text or len(text) < 10:
            continue

        # Check duplicate
        exists = db.query(Question).filter(Question.text == text).first()
        if exists:
            new_questions.append(exists)
            continue

        q_type_str = item.get("question_type", "mcq").lower()
        q_type = QuestionTypeEnum.MCQ if "mcq" in q_type_str else QuestionTypeEnum.SHORT_ANSWER

        options_list = item.get("options")
        options_str = "|".join(options_list) if options_list and isinstance(options_list, list) else None

        topic_name = item.get("topic", "General")
        topic = _get_or_create_topic(db, topic_name, subject=subject)

        q = Question(
            text=text,
            question_type=q_type,
            options=options_str,
            correct_answer=item.get("correct_answer"),
            difficulty=item.get("difficulty", "medium"),
            topic_id=topic.id,
            document_id=rag_doc.id,
        )
        db.add(q)
        new_questions.append(q)

    db.flush()
    logger.info("Generated %d questions via RAG (collection=%s)", len(new_questions), collection)
    return new_questions


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/generate", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    body: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a quiz based on the requested mode."""
    mode = QuizModeEnum(body.mode.value)

    question_query = db.query(Question)
    topic_names_for_rag: list[str] | None = None

    if mode == QuizModeEnum.ADAPTIVE:
        # Find weak topics
        weak = (
            db.query(Progress)
            .filter(
                Progress.student_id == current_user.id,
                Progress.accuracy < settings.WEAK_TOPIC_THRESHOLD,
            )
            .all()
        )
        if weak:
            weak_topic_ids = [p.topic_id for p in weak]
            question_query = question_query.filter(Question.topic_id.in_(weak_topic_ids))
            topic_names_for_rag = [
                p.topic.name for p in weak if p.topic
            ]

    elif mode == QuizModeEnum.TOPIC_FOCUSED:
        if body.topics:
            topic_names_for_rag = body.topics
            question_query = question_query.filter(
                Question.topic.has(Topic.name.in_(body.topics))
            )

    elif mode == QuizModeEnum.REAL_EXAM:
        doc = db.query(Document).filter(
            Document.ingestion_status == IngestionStatusEnum.COMPLETED,
            Document.filename != "RAG_Generated.pdf",
        ).first()
        if doc:
            question_query = question_query.filter(Question.document_id == doc.id)

    # Check local DB first
    questions = question_query.order_by(func.random()).limit(body.count).all()

    # If not enough, generate via RAG
    if len(questions) < body.count:
        needed = body.count - len(questions)
        logger.info("Only %d local questions, generating %d via RAG", len(questions), needed)
        rag_questions = _generate_questions_via_rag(
            db,
            uploader_id=current_user.id,
            count=needed,
            topic_names=topic_names_for_rag,
        )
        questions.extend(rag_questions)

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not generate questions. Please upload and ingest exam papers first.",
        )

    # Limit to requested count
    questions = questions[: body.count]

    # ── Persist quiz ─────────────────────────────────────────────────────
    duration = None
    if mode == QuizModeEnum.REAL_EXAM:
        doc = db.query(Document).filter(
            Document.ingestion_status == IngestionStatusEnum.COMPLETED,
            Document.filename != "RAG_Generated.pdf",
        ).first()
        duration = doc.official_duration_minutes if doc and doc.official_duration_minutes else body.count * 2
    else:
        duration = body.count * 2

    quiz = Quiz(
        mode=mode,
        duration_minutes=duration,
        question_count=len(questions),
        created_by=current_user.id,
    )
    db.add(quiz)
    db.flush()

    for idx, q in enumerate(questions):
        db.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, position=idx))

    db.commit()
    db.refresh(quiz)

    # ── Build response ───────────────────────────────────────────────────
    question_reads = [
        QuestionRead(
            id=q.id,
            text=q.text,
            topic=q.topic.name if q.topic else None,
            difficulty=q.difficulty,
            options=q.options.split("|") if q.options else None,
            question_type=q.question_type.value,
            source_document=str(q.document_id),
        )
        for q in questions
    ]

    return QuizRead(
        id=quiz.id,
        mode=body.mode,
        duration_minutes=quiz.duration_minutes,
        instructions=quiz.instructions,
        questions=question_reads,
        question_count=quiz.question_count,
        created_at=quiz.created_at,
    )


@router.get("/{quiz_id}", response_model=QuizRead)
def get_quiz(
    quiz_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a previously generated quiz."""
    import uuid as _uuid

    quiz = db.query(Quiz).filter(Quiz.id == _uuid.UUID(quiz_id)).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    qq_list = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.position)
        .all()
    )
    questions = [qq.question for qq in qq_list]
    question_reads = [
        QuestionRead(
            id=q.id,
            text=q.text,
            topic=q.topic.name if q.topic else None,
            difficulty=q.difficulty,
            options=q.options.split("|") if q.options else None,
            question_type=q.question_type.value,
            source_document=str(q.document_id),
        )
        for q in questions
    ]

    from app.schemas.quiz import QuizMode

    return QuizRead(
        id=quiz.id,
        mode=QuizMode(quiz.mode.value) if hasattr(quiz.mode, "value") else quiz.mode,
        duration_minutes=quiz.duration_minutes,
        instructions=quiz.instructions,
        questions=question_reads,
        question_count=quiz.question_count,
        created_at=quiz.created_at,
    )
