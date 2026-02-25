"""Practice mode routes — question-by-question with RAG grading.

Flow:
  1. POST /api/practice/start     → generate questions, return first one
  2. POST /api/practice/{id}/answer → submit answer (text or image), get feedback
  3. GET  /api/practice/{id}/next  → get next question
  4. POST /api/practice/{id}/complete → mark session complete
  5. GET  /api/practice/{id}       → get full session results
  6. GET  /api/practice/           → list student's practice sessions
"""

import json
import logging
import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from app.api.deps import get_current_user
from app.db.models import (
    Document,
    IngestionStatusEnum,
    PracticeAnswer,
    PracticeSession,
    PracticeStatusEnum,
    Progress,
    Question,
    Subject,
    Topic,
    User,
)
from app.db.session import get_db
from app.schemas.practice import (
    PracticeAnswerResult,
    PracticeAnswerSubmit,
    PracticeQuestionRead,
    PracticeSessionDetail,
    PracticeSessionRead,
    PracticeStartRequest,
    QuestionSourceReference,
    PracticeStatus,
    SourceReference,
)
from app.services.rag_client import get_rag_client
from app.services.rate_limiter import require_rag_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Grading prompt templates ──────────────────────────────────────────────────

_GRADE_PROMPT = """\
You are an expert exam grader. Grade the student's answer to this question.

Question: {question}
{options_text}
Expected/Correct Answer: {correct_answer}
Student's Answer: {student_answer}

Context from exam materials:
{context}

Provide your assessment as JSON:
{{
  "is_correct": true/false,
  "score": 0.0 to 1.0 (0=wrong, 0.5=partial, 1.0=fully correct),
  "feedback": "Detailed explanation of why the answer is correct/incorrect. Explain the correct answer. Be encouraging and educational.",
  "correct_answer_explanation": "Brief explanation of the correct answer"
}}

Important:
- For MCQ: check if the student picked the right option
- For short answers: accept different phrasings, spelling variants, partial credit
- For essays: evaluate key concepts, give partial credit
- Always explain WHY the correct answer is correct
- Return ONLY valid JSON, no other text
"""

_OCR_PROMPT = """\
This is a photograph/scan of a student's handwritten answer to an exam question.
Please transcribe the handwritten text as accurately as possible.
Preserve mathematical notation where possible (use standard notation).
If parts are unclear, indicate with [unclear].

The question was: {question}

Transcribe the student's handwritten response:
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_grade_json(raw: str) -> dict:
    """Extract grading JSON from LLM response."""
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                text = stripped
                break
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"is_correct": False, "score": 0.0, "feedback": text}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"is_correct": False, "score": 0.0, "feedback": text}


def _get_collection_for_document(doc: Document) -> str | None:
    """Get the RAG collection name for a document."""
    if doc.collection_name:
        return doc.collection_name
    return f"{doc.level.value}_{doc.subject}".replace(" ", "_")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/start", response_model=PracticeSessionRead, status_code=status.HTTP_201_CREATED)
async def start_practice_session(
    body: PracticeStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(require_rag_rate_limit),
):
    """Start a new practice session.

    Subject-centric: questions are pulled from ALL ingested papers in the
    subject by default. If document_id is provided (real-exam mode), only
    that paper is used.
    """
    # Validate subject
    subject = db.query(Subject).filter(Subject.id == body.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    collection = f"{subject.level.value}_{subject.name}".replace(" ", "_")
    document_id = None

    # Helper: find docs in this subject (by FK or text matching)
    def _find_subject_docs(extra_filters=None):
        """Find documents for this subject — tries subject_id FK first, falls
        back to text-based subject + level matching."""
        q = db.query(Document).filter(
            Document.ingestion_status == IngestionStatusEnum.COMPLETED,
        )
        if extra_filters:
            for flt in extra_filters:
                q = q.filter(flt)
        # Try FK match first
        fk_docs = q.filter(Document.subject_id == body.subject_id).all()
        if fk_docs:
            return fk_docs
        # Fall back to text matching
        return q.filter(
            Document.subject == subject.name,
            Document.level == subject.level,
        ).all()

    if body.document_id:
        # Single-paper mode (real-exam)
        doc = db.query(Document).filter(
            Document.id == body.document_id,
            Document.ingestion_status == IngestionStatusEnum.COMPLETED,
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found or not ingested")
        # Auto-link subject_id if missing
        if not doc.subject_id:
            doc.subject_id = body.subject_id
            db.flush()
        collection = _get_collection_for_document(doc)
        document_id = doc.id
    elif body.mode == "real_exam":
        # Randomly pick an exam paper from the subject
        docs = _find_subject_docs()
        if not docs:
            raise HTTPException(
                status_code=404,
                detail="No ingested exam papers found for this subject",
            )
        doc = random.choice(docs)
        # Auto-link subject_id if missing
        if not doc.subject_id:
            doc.subject_id = body.subject_id
            db.flush()
        collection = _get_collection_for_document(doc)
        document_id = doc.id
    else:
        # Subject practice mode: auto-link all matching docs that lack subject_id
        unlinked_docs = db.query(Document).filter(
            Document.subject == subject.name,
            Document.level == subject.level,
            Document.subject_id.is_(None),
            Document.ingestion_status == IngestionStatusEnum.COMPLETED,
        ).all()
        for d in unlinked_docs:
            d.subject_id = body.subject_id
        if unlinked_docs:
            db.flush()
            logger.info("Auto-linked %d docs to subject %s", len(unlinked_docs), subject.name)

    session = PracticeSession(
        student_id=current_user.id,
        subject_id=body.subject_id,
        document_id=document_id,
        collection_name=collection,
        total_questions=body.question_count,
        status=PracticeStatusEnum.IN_PROGRESS,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return _session_to_read(session)


@router.get("/{session_id}/next", response_model=PracticeQuestionRead | None)
async def get_next_question(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(require_rag_rate_limit),
):
    """Get the next question in the practice session.

    Pulls from ALL documents in the subject (unless document_id is set,
    meaning real-exam mode restricts to that single paper).
    Falls back to RAG generation when no DB questions exist.
    """
    session = _get_session(session_id, current_user.id, db)

    if session.answered_count >= session.total_questions:
        raise HTTPException(
            status_code=404,
            detail="All questions answered — session complete",
        )

    answered_ids = [a.question_id for a in session.answers if a.question_id]
    answered_texts = [a.question_text for a in session.answers if a.question_text]
    question_number = session.answered_count + 1

    # ── Try DB questions first ─────────────────────────────────────────
    existing_questions: list[Question] = []
    subject = None
    if session.subject_id:
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()

    if session.document_id:
        # Real-exam mode: single paper
        q = db.query(Question).filter(
            Question.document_id == session.document_id,
        )
        if answered_ids:
            q = q.filter(~Question.id.in_(answered_ids))
        existing_questions = q.order_by(func.random()).limit(1).all()
    elif session.subject_id:
        # Subject-wide practice: query from all docs in this subject
        # Try FK first, then text matching
        subject_doc_ids = [
            d.id for d in db.query(Document.id).filter(
                Document.subject_id == session.subject_id,
                Document.ingestion_status == IngestionStatusEnum.COMPLETED,
            ).all()
        ]
        if not subject_doc_ids and subject:
            subject_doc_ids = [
                d.id for d in db.query(Document.id).filter(
                    Document.subject == subject.name,
                    Document.level == subject.level,
                    Document.ingestion_status == IngestionStatusEnum.COMPLETED,
                ).all()
            ]
        if subject_doc_ids:
            q = db.query(Question).filter(
                Question.document_id.in_(subject_doc_ids),
            )
            if answered_ids:
                q = q.filter(~Question.id.in_(answered_ids))
            existing_questions = q.order_by(func.random()).limit(1).all()

    if existing_questions:
        question = existing_questions[0]
        # Build source references so student can view the relevant document page
        q_sources: list[QuestionSourceReference] = []
        if question.document_id:
            doc = db.query(Document).filter(Document.id == question.document_id).first()
            if doc:
                q_sources.append(QuestionSourceReference(
                    document_name=doc.filename,
                    document_id=str(doc.id),
                    page_number=None,  # DB questions don't have page info
                ))
        return PracticeQuestionRead(
            id=question.id,
            question_number=question_number,
            text=question.text,
            question_type=question.question_type.value,
            options=question.options.split("|") if question.options else None,
            topic=question.topic.name if question.topic else None,
            difficulty=question.difficulty,
            total_questions=session.total_questions,
            source_references=q_sources,
        )

    # ── Generate via RAG (no DB questions) ─────────────────────────────
    if session.collection_name:
        try:
            generated = _generate_rag_question(
                collection=session.collection_name,
                subject_name=subject.name if subject else None,
                question_number=question_number,
                total_questions=session.total_questions,
                already_asked=answered_texts,
                db=db,
            )
            if generated:
                return PracticeQuestionRead(
                    id=uuid.uuid4(),
                    question_number=question_number,
                    text=generated["text"],
                    question_type=generated.get("question_type", "short-answer"),
                    options=generated.get("options"),
                    topic=generated.get("topic"),
                    difficulty=generated.get("difficulty", "medium"),
                    total_questions=session.total_questions,
                    source_references=[
                        QuestionSourceReference(**s)
                        for s in generated.get("source_references", [])
                    ],
                )
        except Exception as e:
            logger.error("RAG question generation failed: %s", e)

    raise HTTPException(
        status_code=404,
        detail="No more questions available for this practice session",
    )


@router.post("/{session_id}/answer", response_model=PracticeAnswerResult)
async def submit_practice_answer(
    session_id: uuid.UUID,
    body: PracticeAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl=Depends(require_rag_rate_limit),
):
    """Submit an answer (text or handwritten image) and get RAG-powered feedback."""
    session = _get_session(session_id, current_user.id, db)

    if session.status != PracticeStatusEnum.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Practice session is not active")

    # Get question details
    question_text = body.question_text or ""
    correct_answer = None
    question_type = "short-answer"
    db_question_id = None  # Only set to a real DB question_id

    if body.question_id:
        question = db.query(Question).filter(Question.id == body.question_id).first()
        if question:
            db_question_id = question.id  # Exists in DB → safe for FK
            question_text = question.text
            correct_answer = question.correct_answer
            question_type = question.question_type.value
        # else: RAG-generated question with random UUID → db_question_id stays None

    # Handle handwritten answer via OCR
    student_answer = body.answer_text or ""
    is_handwritten = False
    ocr_text = None

    if body.answer_image_base64:
        is_handwritten = True
        ocr_text = _ocr_handwritten_answer(
            body.answer_image_base64, question_text
        )
        student_answer = ocr_text or student_answer
        if not student_answer:
            student_answer = "[Could not read handwritten answer]"

    if not student_answer:
        raise HTTPException(status_code=400, detail="No answer provided")

    # Grade using RAG
    grade_result = _grade_answer_with_rag(
        question_text=question_text,
        student_answer=student_answer,
        correct_answer=correct_answer,
        question_type=question_type,
        collection=session.collection_name,
        db=db,
    )

    # Save the answer (question_id=None for RAG-generated questions to avoid FK violation)
    answer_record = PracticeAnswer(
        session_id=session.id,
        question_id=db_question_id,
        question_text=question_text,
        question_type=question_type,
        student_answer=student_answer,
        is_handwritten=is_handwritten,
        ocr_text=ocr_text,
        is_correct=grade_result["is_correct"],
        score=grade_result["score"],
        feedback=grade_result["feedback"],
        correct_answer=correct_answer or grade_result.get("correct_answer"),
        source_references=json.dumps(grade_result.get("sources", [])),
    )
    db.add(answer_record)

    # Update session counters
    session.answered_count += 1
    if grade_result["is_correct"]:
        session.correct_count += 1
    if session.answered_count >= session.total_questions:
        session.status = PracticeStatusEnum.COMPLETED
        session.completed_at = datetime.now(timezone.utc)

    db.commit()

    return PracticeAnswerResult(
        question_text=question_text,
        student_answer=student_answer,
        is_correct=grade_result["is_correct"],
        score=grade_result["score"],
        feedback=grade_result["feedback"],
        correct_answer=correct_answer or grade_result.get("correct_answer"),
        source_references=[
            SourceReference(
                page_number=s.get("page_number"),
                content=s.get("content", ""),
                score=s.get("score", 0.0),
                document_name=s.get("document_name"),
                document_id=s.get("document_id"),
            )
            for s in grade_result.get("sources", [])
        ],
        was_handwritten=is_handwritten,
        ocr_text=ocr_text,
    )


@router.post("/{session_id}/complete", response_model=PracticeSessionRead)
def complete_practice_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a practice session as completed and update progress tracking."""
    session = _get_session(session_id, current_user.id, db)
    session.status = PracticeStatusEnum.COMPLETED
    session.completed_at = datetime.now(timezone.utc)

    # ── Update Progress tracking ──────────────────────────────────────
    _update_progress_from_session(session, current_user.id, db)

    db.commit()
    db.refresh(session)
    return _session_to_read(session)


@router.get("/{session_id}", response_model=PracticeSessionDetail)
def get_practice_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full practice session with all graded answers."""
    session = _get_session(session_id, current_user.id, db)

    answers = [
        PracticeAnswerResult(
            question_text=a.question_text,
            student_answer=a.student_answer,
            is_correct=a.is_correct,
            score=a.score,
            feedback=a.feedback or "",
            correct_answer=a.correct_answer,
            source_references=[
                SourceReference(**s)
                for s in (json.loads(a.source_references) if a.source_references else [])
            ],
            was_handwritten=a.is_handwritten,
            ocr_text=a.ocr_text,
        )
        for a in session.answers
    ]

    read = _session_to_read(session)
    return PracticeSessionDetail(**read.model_dump(), answers=answers)


@router.get("", response_model=list[PracticeSessionRead])
def list_practice_sessions(
    skip: int = 0,
    limit: int = 20,
    subject_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current student's practice sessions, optionally filtered by subject."""
    q = db.query(PracticeSession).filter(PracticeSession.student_id == current_user.id)
    if subject_id:
        q = q.filter(PracticeSession.subject_id == subject_id)
    sessions = (
        q.order_by(PracticeSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_session_to_read(s) for s in sessions]


# ── Internal helpers ──────────────────────────────────────────────────────────


def _get_session(
    session_id: uuid.UUID, student_id: uuid.UUID, db: Session
) -> PracticeSession:
    session = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.id == session_id,
            PracticeSession.student_id == student_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Practice session not found")
    return session


def _session_to_read(session: PracticeSession) -> PracticeSessionRead:
    accuracy = 0.0
    if session.answered_count > 0:
        accuracy = round(session.correct_count / session.answered_count, 4)
    return PracticeSessionRead(
        id=session.id,
        student_id=session.student_id,
        subject_id=session.subject_id,
        document_id=session.document_id,
        status=PracticeStatus(session.status.value),
        total_questions=session.total_questions,
        answered_count=session.answered_count,
        correct_count=session.correct_count,
        accuracy=accuracy,
        created_at=session.created_at,
        completed_at=session.completed_at,
    )


def _grade_answer_with_rag(
    question_text: str,
    student_answer: str,
    correct_answer: str | None,
    question_type: str,
    collection: str | None,
    db: Session | None = None,
) -> dict:
    """Grade an answer using RAG context + LLM."""
    # Quick MCQ grading
    if question_type == "mcq" and correct_answer:
        is_correct = student_answer.strip().upper() == correct_answer.strip().upper()
        return {
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0,
            "feedback": (
                f"✅ Correct! The answer is {correct_answer}."
                if is_correct
                else f"❌ Incorrect. The correct answer is {correct_answer}."
            ),
            "sources": [],
        }

    # For non-MCQ: use RAG for context + LLM for grading
    context = ""
    sources = []

    if collection:
        try:
            client = get_rag_client()
            retrieve_result = client.retrieve(
                query=f"{question_text} {correct_answer or ''}",
                collection=collection,
                top_k=5,
            )
            raw_results = retrieve_result.get("results", [])
            context = "\n\n".join(r.get("content", "") for r in raw_results)

            # Build a filename → document_id lookup from the DB
            doc_id_cache: dict[str, str] = {}
            if db:
                filenames = list({
                    r.get("metadata", {}).get("file_name", "")
                    for r in raw_results
                    if r.get("metadata", {}).get("file_name")
                })
                if filenames:
                    # Try exact filename match first
                    docs = db.query(Document.id, Document.filename, Document.file_path).filter(
                        Document.filename.in_(filenames)
                    ).all()
                    doc_id_cache = {d.filename: str(d.id) for d in docs}

                    # Also match by file_path basename for UUID-prefixed filenames
                    if len(doc_id_cache) < len(filenames):
                        all_docs = db.query(Document.id, Document.file_path).all()
                        for adoc in all_docs:
                            if adoc.file_path:
                                basename = adoc.file_path.rsplit("/", 1)[-1]
                                if basename in filenames and basename not in doc_id_cache:
                                    doc_id_cache[basename] = str(adoc.id)

            sources = [
                {
                    "page_number": r.get("metadata", {}).get("page_number"),
                    "content": r.get("content", "")[:200],
                    "score": r.get("score", 0.0),
                    "document_name": r.get("metadata", {}).get("file_name"),
                    "document_id": doc_id_cache.get(
                        r.get("metadata", {}).get("file_name", "")
                    ),
                }
                for r in raw_results
            ]
        except Exception as e:
            logger.warning("RAG retrieval for grading failed: %s", e)

    options_text = ""
    prompt = _GRADE_PROMPT.format(
        question=question_text,
        options_text=options_text,
        correct_answer=correct_answer or "Not provided — grade based on context",
        student_answer=student_answer,
        context=context or "No additional context available",
    )

    try:
        client = get_rag_client()
        result = client.query_direct(question=prompt)
        grade = _parse_grade_json(result.get("answer", ""))
        grade["sources"] = sources
        return grade
    except Exception as e:
        logger.error("RAG grading failed: %s", e)
        # Fallback: simple text comparison
        if correct_answer:
            from app.services.grading import grade_answer

            is_correct = grade_answer(
                question_type=question_type,
                student_answer=student_answer,
                correct_answer=correct_answer,
                question_text=question_text,
            )
            return {
                "is_correct": is_correct,
                "score": 1.0 if is_correct else 0.0,
                "feedback": (
                    "✅ Correct!" if is_correct else f"❌ The expected answer is: {correct_answer}"
                ),
                "sources": sources,
            }
        return {
            "is_correct": None,
            "score": 0.0,
            "feedback": "Unable to grade this answer automatically. Please review with your teacher.",
            "sources": sources,
        }


def _ocr_handwritten_answer(image_base64: str, question_text: str) -> str | None:
    """OCR a handwritten answer image using Groq Vision (VLM)."""
    try:
        client = get_rag_client()
        prompt = _OCR_PROMPT.format(question=question_text)

        # Call the RAG service's OCR endpoint
        result = client._http.post(
            "/ocr/handwritten",
            json={
                "image_base64": image_base64,
                "prompt": prompt,
            },
            timeout=30.0,
        )
        result.raise_for_status()
        data = result.json()
        return data.get("text", "")
    except Exception as e:
        logger.error("Handwritten OCR failed: %s", e)
        return None


# ── RAG question generation with variety ──────────────────────────────────────

# Question type templates for diverse generation
_QUESTION_TYPES = [
    "short-answer",
    "multiple-choice",
    "fill-in-the-blank",
    "true-or-false",
    "explain",
]

# Seed phrases to vary the RAG retrieval (different chunks each time)
_RETRIEVAL_SEEDS = [
    "important concepts and definitions",
    "key facts and figures",
    "practical applications",
    "cause and effect relationships",
    "comparisons and differences",
    "processes and procedures",
    "examples and illustrations",
    "principles and laws",
    "classifications and categories",
    "problems and solutions",
    "experiments and observations",
    "historical events and dates",
    "formulas and calculations",
]


def _generate_rag_question(
    collection: str,
    subject_name: str | None,
    question_number: int,
    total_questions: int,
    already_asked: list[str],
    db: Session | None = None,
) -> dict | None:
    """Generate a unique exam question via RAG with varied prompts.

    Key improvements over the old approach:
    - Random retrieval seed → different chunks → different questions
    - Includes previously asked questions to avoid repeats
    - Varied question types (MCQ, short-answer, true/false, etc.)
    - Uses query_direct for the generation (no caching)
    - Subject-aware context
    - Returns source references (page, document) for diagram context
    """
    client = get_rag_client()
    subject_label = subject_name or collection.replace("_", " ")

    # 1) Retrieve diverse content from the collection using a random seed
    seed = random.choice(_RETRIEVAL_SEEDS)
    retrieval_query = f"{subject_label}: {seed}"

    try:
        retrieve_result = client.retrieve(
            query=retrieval_query,
            collection=collection,
            top_k=8,
        )
        chunks = retrieve_result.get("results", [])
    except Exception as e:
        logger.warning("RAG retrieval for question gen failed: %s", e)
        chunks = []

    if not chunks:
        return None

    # Shuffle and pick a subset of chunks for variety
    random.shuffle(chunks)
    selected_chunks = chunks[: min(4, len(chunks))]
    context = "\n\n---\n\n".join(c.get("content", "") for c in selected_chunks)

    # 2) Pick a question type
    q_type = random.choice(_QUESTION_TYPES)

    # 3) Build the "already asked" block so the LLM avoids repeats
    avoid_block = ""
    if already_asked:
        avoid_list = "\n".join(f"  - {q}" for q in already_asked[-10:])
        avoid_block = (
            f"\n\nDo NOT repeat these already-asked questions:\n{avoid_list}\n"
            "Generate a COMPLETELY DIFFERENT question about a different topic/concept.\n"
        )

    # 4) Build generation prompt — sent via query_direct (no index, no cache)
    type_instructions = {
        "multiple-choice": (
            'The question should be multiple-choice with 4 options (A, B, C, D). '
            'Include the options as a list in the "options" field.'
        ),
        "true-or-false": (
            'The question should be a true-or-false statement. '
            'Set "question_type" to "true-or-false" and "correct_answer" to "True" or "False".'
        ),
        "fill-in-the-blank": (
            'The question should have a blank (indicated by ___) that the student fills in. '
            'Set "question_type" to "fill-in-the-blank".'
        ),
        "explain": (
            'Ask the student to explain a concept or process. '
            'Set "question_type" to "short-answer".'
        ),
        "short-answer": (
            'The question should require a brief factual answer (1-3 sentences). '
            'Set "question_type" to "short-answer".'
        ),
    }

    gen_prompt = f"""\
You are creating exam practice questions for {subject_label}.
This is question {question_number} of {total_questions} in a practice session.

Based on the following exam content, generate ONE practice question.
{type_instructions.get(q_type, type_instructions["short-answer"])}
{avoid_block}
EXAM CONTENT:
{context}

Return ONLY a JSON object with these fields:
{{
  "text": "The question text",
  "question_type": "{q_type if q_type != 'explain' else 'short-answer'}",
  "correct_answer": "The correct answer",
  "topic": "The topic this question covers",
  "difficulty": "easy" or "medium" or "hard"{', "options": ["A. ...", "B. ...", "C. ...", "D. ..."]' if q_type == 'multiple-choice' else ''}
}}

IMPORTANT:
- The question MUST be directly based on the exam content above
- The question must be appropriate for the {subject_label} subject
- If the exam content references a diagram, figure, table, map, or image:
  * Do NOT say "in the diagram" or "refer to the figure" without describing it
  * Instead, DESCRIBE the visual element in words (e.g. "Given a circuit with a 5Ω resistor connected to a 12V battery...")
  * Or ask about the concept the visual illustrates without requiring the student to see it
  * The student can view the source document page, but the question should still be answerable with the text description
- Return ONLY valid JSON, no other text
"""

    # Build source references from the chunks for the frontend (page links)
    source_refs: list[dict] = []
    doc_id_cache: dict[str, str] = {}
    if db:
        filenames = list({
            c.get("metadata", {}).get("file_name", "")
            for c in selected_chunks
            if c.get("metadata", {}).get("file_name")
        })
        if filenames:
            docs = db.query(Document.id, Document.filename, Document.file_path).filter(
                Document.filename.in_(filenames)
            ).all()
            doc_id_cache = {d.filename: str(d.id) for d in docs}
            # Also match by file_path basename
            if len(doc_id_cache) < len(filenames):
                all_docs = db.query(Document.id, Document.file_path).all()
                for adoc in all_docs:
                    if adoc.file_path:
                        basename = adoc.file_path.rsplit("/", 1)[-1]
                        if basename in filenames and basename not in doc_id_cache:
                            doc_id_cache[basename] = str(adoc.id)

    seen_pages: set[tuple[str | None, int | None]] = set()
    for chunk in selected_chunks:
        meta = chunk.get("metadata", {})
        fname = meta.get("file_name")
        page = meta.get("page_number")
        key = (fname, page)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        source_refs.append({
            "page_number": page,
            "document_name": fname,
            "document_id": doc_id_cache.get(fname or ""),
            "content_snippet": chunk.get("content", "")[:120],
        })

    try:
        result = client.query_direct(question=gen_prompt)
        answer_text = result.get("answer", "")
        parsed = _parse_grade_json(answer_text)
        if parsed.get("text"):
            # Ensure options are a list for MCQ
            options = parsed.get("options")
            if isinstance(options, str):
                options = [o.strip() for o in options.split("|") if o.strip()]
            return {
                "text": parsed["text"],
                "question_type": parsed.get("question_type", "short-answer"),
                "correct_answer": parsed.get("correct_answer"),
                "topic": parsed.get("topic"),
                "difficulty": parsed.get("difficulty", "medium"),
                "options": options,
                "source_references": source_refs,
            }
    except Exception as e:
        logger.error("RAG question generation (direct) failed: %s", e)

    return None


# ── Progress tracking from practice sessions ─────────────────────────────────


def _update_progress_from_session(
    session: PracticeSession,
    student_id: uuid.UUID,
    db: Session,
) -> None:
    """Update per-topic Progress rows from a practice session's answers.

    For RAG-generated questions (no topic_id), we create/find a topic
    based on the subject name. This mirrors what attempts.py does.
    """
    if not session.answers:
        return

    # Collect subject context for topic creation
    subject_name = None
    if session.subject_id:
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
        if subject:
            subject_name = subject.name

    # Bucket answers by topic
    topic_tallies: dict[str, dict] = {}

    for answer in session.answers:
        topic_name = "General"
        topic_id = None

        # Try to get topic from the linked DB question
        if answer.question_id and answer.question:
            if answer.question.topic:
                topic_name = answer.question.topic.name
                topic_id = answer.question.topic_id
        else:
            # RAG-generated: use subject name as topic
            topic_name = subject_name or "General"

        bucket = topic_tallies.setdefault(
            topic_name,
            {"correct": 0, "total": 0, "topic_id": topic_id},
        )
        bucket["total"] += 1
        if answer.is_correct:
            bucket["correct"] += 1

    # Update/create Progress rows
    for topic_name, tally in topic_tallies.items():
        topic_id = tally["topic_id"]

        # If no topic_id, find or create a topic
        if topic_id is None:
            existing_topic = (
                db.query(Topic)
                .filter(
                    Topic.subject == (subject_name or "General"),
                    Topic.name == topic_name,
                )
                .first()
            )
            if existing_topic:
                topic_id = existing_topic.id
            else:
                new_topic = Topic(
                    subject=subject_name or "General",
                    name=topic_name,
                )
                db.add(new_topic)
                db.flush()
                topic_id = new_topic.id

        # Upsert progress
        prog = (
            db.query(Progress)
            .filter(
                Progress.student_id == student_id,
                Progress.topic_id == topic_id,
            )
            .first()
        )
        if prog is None:
            prog = Progress(student_id=student_id, topic_id=topic_id)
            db.add(prog)
            db.flush()

        prog.total_correct += tally["correct"]
        prog.total_questions += tally["total"]
        prog.attempt_count += 1
        prog.accuracy = (
            round(prog.total_correct / prog.total_questions, 4)
            if prog.total_questions
            else 0.0
        )
        prog.last_attempted_at = datetime.now(timezone.utc)