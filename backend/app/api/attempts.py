"""Attempt submission and retrieval routes."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import (
    Attempt,
    AttemptAnswer,
    Document,
    IngestionStatusEnum,
    Progress,
    Question,
    Quiz,
    QuizQuestion,
    User,
)
from app.db.session import get_db
from app.schemas.attempt import AttemptRead, AttemptSubmit, TopicScore, AttemptDetailRead, AttemptAnswerRead
from app.services.rag_client import get_rag_client
from app.services.grading import grade_answer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=AttemptRead, status_code=status.HTTP_201_CREATED)
def submit_attempt(
    body: AttemptSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit answers for a quiz and receive graded results.
    
    This endpoint:
    1. Grades all answers
    2. Tracks the source document (if provided)
    3. Updates per-topic progress metrics for personalized learning
    """
    quiz = db.query(Quiz).filter(Quiz.id == body.quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    # Fetch quiz questions in order
    qq_rows = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.position)
        .all()
    )
    question_map: dict[uuid.UUID, Question] = {
        qq.question_id: qq.question for qq in qq_rows
    }

    # Determine source document from first question if available
    source_document_id = None
    if question_map:
        first_question = next(iter(question_map.values()))
        if first_question.document_id:
            source_document_id = first_question.document_id

    # ── Grade answers ────────────────────────────────────────────────────
    attempt = Attempt(
        quiz_id=quiz.id,
        student_id=current_user.id,
        document_id=source_document_id,  # Track source document
        total=len(question_map),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.flush()

    correct_count = 0
    topic_tallies: dict[str, dict] = {}  # topic_name → {correct, total}

    # Get RAG client for LLM-based grading of non-MCQ questions
    try:
        rag_client = get_rag_client()
    except Exception:
        rag_client = None
        logger.warning("RAG client unavailable — falling back to text-only grading")

    for qid_str, answer_text in body.answers.items():
        qid = uuid.UUID(qid_str)
        question = question_map.get(qid)
        if question is None:
            continue

        is_correct = grade_answer(
            question_type=question.question_type.value,
            student_answer=answer_text,
            correct_answer=question.correct_answer,
            question_text=question.text,
            rag_client=rag_client,
        )
        if is_correct:
            correct_count += 1

        db.add(
            AttemptAnswer(
                attempt_id=attempt.id,
                question_id=qid,
                answer=answer_text,
                is_correct=is_correct,
            )
        )

        # Accumulate per‑topic for progress tracking
        topic_name = question.topic.name if question.topic else "General"
        bucket = topic_tallies.setdefault(
            topic_name, {"correct": 0, "total": 0, "topic_id": question.topic_id}
        )
        bucket["total"] += 1
        if is_correct:
            bucket["correct"] += 1

    attempt.score = correct_count
    attempt.percentage = (
        round(correct_count / attempt.total * 100, 2) if attempt.total else 0.0
    )

    # ── Update per‑topic Progress rows ───────────────────────────────────
    # This enables the system to identify weak topics for adaptive learning
    for topic_name, tally in topic_tallies.items():
        if tally["topic_id"] is None:
            continue
        prog = (
            db.query(Progress)
            .filter(
                Progress.student_id == current_user.id,
                Progress.topic_id == tally["topic_id"],
            )
            .first()
        )
        if prog is None:
            prog = Progress(student_id=current_user.id, topic_id=tally["topic_id"])
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

    db.commit()
    db.refresh(attempt)

    # ── Build response ───────────────────────────────────────────────────
    topic_scores = [
        TopicScore(
            topic=name,
            correct=t["correct"],
            total=t["total"],
            accuracy=round(t["correct"] / t["total"], 4) if t["total"] else 0.0,
        )
        for name, t in topic_tallies.items()
    ]

    return AttemptRead(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        student_id=attempt.student_id,
        score=attempt.score,
        total=attempt.total,
        percentage=attempt.percentage,
        topic_breakdown=topic_scores,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
    )


@router.get("/", response_model=list[AttemptRead])
def list_attempts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current student's past attempts."""
    rows = (
        db.query(Attempt)
        .filter(Attempt.student_id == current_user.id)
        .order_by(Attempt.submitted_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for attempt in rows:
        # Build topic breakdown from stored answers
        topic_tallies: dict[str, dict] = {}
        for aa in attempt.answers:
            q = aa.question
            topic_name = q.topic.name if q.topic else "General"
            bucket = topic_tallies.setdefault(topic_name, {"correct": 0, "total": 0})
            bucket["total"] += 1
            if aa.is_correct:
                bucket["correct"] += 1

        topic_scores = [
            TopicScore(
                topic=name,
                correct=t["correct"],
                total=t["total"],
                accuracy=round(t["correct"] / t["total"], 4) if t["total"] else 0.0,
            )
            for name, t in topic_tallies.items()
        ]

        results.append(
            AttemptRead(
                id=attempt.id,
                quiz_id=attempt.quiz_id,
                student_id=attempt.student_id,
                score=attempt.score,
                total=attempt.total,
                percentage=attempt.percentage,
                topic_breakdown=topic_scores,
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
            )
        )

    return results


@router.get("/{attempt_id}", response_model=AttemptDetailRead)
def get_attempt(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single attempt with per-question answers for review."""
    import uuid as _uuid

    attempt = (
        db.query(Attempt)
        .filter(
            Attempt.id == _uuid.UUID(attempt_id),
            Attempt.student_id == current_user.id,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        )

    # Build per-question answer list
    answer_reads = []
    topic_tallies: dict[str, dict] = {}
    for aa in attempt.answers:
        q = aa.question
        topic_name = q.topic.name if q.topic else "General"
        answer_reads.append(
            AttemptAnswerRead(
                question_id=aa.question_id,
                question_text=q.text,
                student_answer=aa.answer,
                correct_answer=q.correct_answer,
                is_correct=aa.is_correct,
                topic=topic_name,
                options=q.options.split("|") if q.options else None,
            )
        )
        bucket = topic_tallies.setdefault(topic_name, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if aa.is_correct:
            bucket["correct"] += 1

    topic_scores = [
        TopicScore(
            topic=name,
            correct=t["correct"],
            total=t["total"],
            accuracy=round(t["correct"] / t["total"], 4) if t["total"] else 0.0,
        )
        for name, t in topic_tallies.items()
    ]

    return AttemptDetailRead(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        student_id=attempt.student_id,
        score=attempt.score,
        total=attempt.total,
        percentage=attempt.percentage,
        topic_breakdown=topic_scores,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        answers=answer_reads,
    )


# ── AI Review helpers ─────────────────────────────────────────────────────────


def _get_best_collection(db: Session) -> str | None:
    """Find the most recent ingested collection name."""
    doc = (
        db.query(Document)
        .filter(Document.ingestion_status == IngestionStatusEnum.COMPLETED)
        .order_by(Document.created_at.desc())
        .first()
    )
    if doc:
        return f"{doc.level.value}_{doc.subject}".replace(" ", "_")
    return None


def _build_attempt_summary(attempt: Attempt) -> str:
    """Build a human-readable summary of an attempt for the AI prompt."""
    lines = [
        f"Quiz attempt: {attempt.score}/{attempt.total} ({attempt.percentage:.0f}%)",
        f"Submitted: {attempt.submitted_at}",
        "",
        "Questions and answers:",
    ]
    for i, aa in enumerate(attempt.answers, 1):
        q = aa.question
        topic = q.topic.name if q.topic else "General"
        status_icon = "✓" if aa.is_correct else "✗"
        lines.append(f"\nQ{i} [{topic}] ({status_icon} {'Correct' if aa.is_correct else 'Wrong'}):")
        lines.append(f"  Question: {q.text}")
        if q.options:
            for j, opt in enumerate(q.options.split("|")):
                letter = chr(65 + j)
                lines.append(f"    {letter}. {opt}")
        lines.append(f"  Student answered: {aa.answer}")
        lines.append(f"  Correct answer: {q.correct_answer or 'N/A'}")
    return "\n".join(lines)


class AIReviewRequest(BaseModel):
    """Optional follow-up question for the AI review."""
    question: str | None = None


class AIReviewResponse(BaseModel):
    """AI-generated review/explanation."""
    explanation: str
    sources: list[dict] = []


class QuestionExplainRequest(BaseModel):
    """Optional follow-up question about a specific question."""
    question: str | None = None


# ── AI Review of full attempt ─────────────────────────────────────────────────


@router.post("/{attempt_id}/review", response_model=AIReviewResponse)
def review_attempt_with_ai(
    attempt_id: str,
    body: AIReviewRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an AI-powered review of the entire attempt."""
    import uuid as _uuid

    attempt = (
        db.query(Attempt)
        .filter(
            Attempt.id == _uuid.UUID(attempt_id),
            Attempt.student_id == current_user.id,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    summary = _build_attempt_summary(attempt)

    follow_up = ""
    if body and body.question:
        follow_up = f"\n\nThe student also asks: {body.question}"

    prompt = (
        f"{summary}{follow_up}\n\n"
        "Provide a thorough, encouraging review. For each wrong answer, "
        "explain the correct answer clearly and WHY it is correct. "
        "At the end, give 3-5 specific, actionable study tips."
    )

    system_prompt = (
        "You are an expert, friendly exam tutor reviewing a student's exam attempt. "
        "Your job is to help them learn from their mistakes. "
        "For EVERY wrong answer: explain what the correct answer is and WHY, "
        "explain why the student's answer was wrong, and give a brief concept explanation. "
        "For open-ended/short-answer questions, also explain what a good answer looks like. "
        "Be encouraging, use simple language, and provide examples or analogies. "
        "Identify knowledge gaps and provide specific study recommendations."
    )

    collection = _get_best_collection(db)
    client = get_rag_client()

    # Tier 1: Try RAG with collection (uses document context)
    if collection:
        try:
            result = client.query(question=prompt, collection=collection, top_k=5)
            return AIReviewResponse(
                explanation=result.get("answer", "Unable to generate review."),
                sources=result.get("sources", []),
            )
        except Exception as e:
            logger.info("RAG collection query failed (expected if no index): %s", e)

    # Tier 2: Try direct LLM (no collection needed, uses training knowledge)
    try:
        result = client.query_direct(
            question=prompt, system_prompt=system_prompt
        )
        return AIReviewResponse(
            explanation=result.get("answer", "Unable to generate review."),
            sources=[],
        )
    except Exception as e:
        logger.warning("Direct LLM review also failed: %s", e)

    # Tier 3: Static fallback (always works, no LLM needed)
    wrong_qs = [aa for aa in attempt.answers if not aa.is_correct]
    lines = [
        f"## Attempt Review: {attempt.score}/{attempt.total} ({attempt.percentage:.0f}%)\n",
    ]
    if not wrong_qs:
        lines.append("🎉 **Perfect score!** You got every question right. Great job!\n")
    else:
        lines.append(f"You got **{len(wrong_qs)} question(s) wrong**. Let's review them:\n")
        for i, aa in enumerate(wrong_qs, 1):
            q = aa.question
            lines.append(f"### {i}. {q.text}")
            lines.append(f"- **Your answer:** {aa.answer}")
            lines.append(f"- **Correct answer:** {q.correct_answer or 'N/A'}")
            lines.append("")
        lines.append("### 💡 Study Tips")
        topics = set(
            aa.question.topic.name
            for aa in wrong_qs
            if aa.question.topic
        )
        if topics:
            lines.append(f"Focus on these topics: **{', '.join(topics)}**")
        lines.append("Review the material and try practicing more questions in these areas.")
    return AIReviewResponse(explanation="\n".join(lines), sources=[])


# ── AI Explanation for a single question ──────────────────────────────────────


@router.post("/{attempt_id}/questions/{question_id}/explain", response_model=AIReviewResponse)
def explain_question_with_ai(
    attempt_id: str,
    question_id: str,
    body: QuestionExplainRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an AI explanation for a specific question in an attempt."""
    import uuid as _uuid

    attempt = (
        db.query(Attempt)
        .filter(
            Attempt.id == _uuid.UUID(attempt_id),
            Attempt.student_id == current_user.id,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    # Find the specific answer
    answer_record = None
    for aa in attempt.answers:
        if str(aa.question_id) == question_id:
            answer_record = aa
            break

    if not answer_record:
        raise HTTPException(status_code=404, detail="Question not found in this attempt")

    q = answer_record.question
    topic = q.topic.name if q.topic else "General"

    # Build question context
    q_context = f"Question (Topic: {topic}):\n{q.text}\n"
    if q.options:
        for j, opt in enumerate(q.options.split("|")):
            letter = chr(65 + j)
            q_context += f"  {letter}. {opt}\n"
    else:
        q_context += "(This is an open-ended question requiring a written answer)\n"
    q_context += f"\nStudent's answer: {answer_record.answer}\n"
    q_context += f"Correct answer: {q.correct_answer or 'N/A'}\n"
    q_context += f"Result: {'Correct ✓' if answer_record.is_correct else 'Wrong ✗'}\n"

    follow_up = ""
    if body and body.question:
        follow_up = f"\n\nThe student asks specifically: {body.question}"

    prompt = (
        f"{q_context}{follow_up}\n\n"
        "Give a clear, educational explanation."
    )

    if q.options:
        system_prompt = (
            "You are an expert, friendly tutor. A student needs help understanding this "
            "multiple-choice exam question. "
            "Explain the correct answer thoroughly, then explain why EACH option is right or wrong. "
            f"The student's answer was {'correct' if answer_record.is_correct else 'wrong'}. "
            "Use simple language, examples, and analogies. Be encouraging."
        )
    else:
        system_prompt = (
            "You are an expert, friendly tutor. A student needs help understanding this "
            "open-ended exam question. "
            "Explain what the correct answer means and why it is correct. "
            "Explain what was wrong or incomplete about the student's answer. "
            "Give an example of a model answer and explain the key concepts. "
            f"The student's answer was {'correct' if answer_record.is_correct else 'wrong'}. "
            "Use simple language, examples, and analogies. Be encouraging."
        )

    collection = _get_best_collection(db)
    client = get_rag_client()

    # Tier 1: Try RAG with collection
    if collection:
        try:
            result = client.query(question=prompt, collection=collection, top_k=5)
            return AIReviewResponse(
                explanation=result.get("answer", "Unable to generate explanation."),
                sources=result.get("sources", []),
            )
        except Exception as e:
            logger.info("RAG collection query failed (expected if no index): %s", e)

    # Tier 2: Try direct LLM
    try:
        result = client.query_direct(
            question=prompt, system_prompt=system_prompt
        )
        return AIReviewResponse(
            explanation=result.get("answer", "Unable to generate explanation."),
            sources=[],
        )
    except Exception as e:
        logger.warning("Direct LLM explain also failed: %s", e)

    # Tier 3: Static fallback
    lines = [f"## Explanation: {q.text}\n"]
    if answer_record.is_correct:
        lines.append(f"✅ **Correct!** Your answer '{answer_record.answer}' is right.\n")
    else:
        lines.append(f"❌ **Incorrect.** You answered '{answer_record.answer}', "
                    f"but the correct answer is '{q.correct_answer}'.\n")
    if q.options:
        lines.append("### Options breakdown:")
        for j, opt in enumerate(q.options.split("|")):
            letter = chr(65 + j)
            marker = "✓" if q.correct_answer and q.correct_answer.upper() == letter else ""
            lines.append(f"- **{letter}.** {opt} {marker}")
        lines.append("")
    else:
        lines.append("### What a good answer looks like:")
        lines.append(f"The expected answer is: **{q.correct_answer or 'N/A'}**")
        lines.append("")
    lines.append(f"**Topic:** {topic}")
    lines.append("\nReview this topic to strengthen your understanding.")
    return AIReviewResponse(explanation="\n".join(lines), sources=[])