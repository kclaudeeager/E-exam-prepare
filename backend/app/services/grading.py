"""Smart grading service for non-MCQ questions.

MCQ questions use exact letter comparison (A/B/C/D).
Short-answer questions use a multi-tier approach:
  1. Normalised text comparison (case, punctuation, articles, whitespace)
  2. Token-set matching (key answer tokens present in student answer)
  3. LLM-based semantic grading via RAG service (if available)
"""

from __future__ import annotations

import logging
import re
import json
from typing import Any

logger = logging.getLogger(__name__)

# ── Text normalisation helpers ────────────────────────────────────────────────

_STRIP_ARTICLES = re.compile(r"\b(the|a|an)\b", re.IGNORECASE)
_STRIP_PUNCT = re.compile(r"[^\w\s]")
_MULTI_SPACE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Aggressively normalise text for comparison.

    Lowercases, strips articles, punctuation, and collapses whitespace.
    'World Health Organisation' → 'world health organisation'
    'Food, Shelter' → 'food shelter'
    """
    t = text.lower().strip()
    t = _STRIP_ARTICLES.sub(" ", t)
    t = _STRIP_PUNCT.sub(" ", t)
    t = _MULTI_SPACE.sub(" ", t).strip()
    return t


def _tokenise(text: str) -> set[str]:
    """Split normalised text into a set of tokens."""
    return set(_normalise(text).split())


# ── Spelling equivalence ─────────────────────────────────────────────────────

_SPELLING_EQUIVALENTS: list[tuple[str, str]] = [
    ("organization", "organisation"),
    ("recognize", "recognise"),
    ("realize", "realise"),
    ("analyze", "analyse"),
    ("center", "centre"),
    ("color", "colour"),
    ("honor", "honour"),
    ("favor", "favour"),
    ("defense", "defence"),
    ("offense", "offence"),
    ("license", "licence"),
    ("practice", "practise"),
    ("catalog", "catalogue"),
    ("dialog", "dialogue"),
    ("program", "programme"),
    ("labor", "labour"),
    ("neighbor", "neighbour"),
    ("behavior", "behaviour"),
]


def _unify_spelling(text: str) -> str:
    """Map British ↔ American spelling variants to a canonical form."""
    t = text.lower()
    for american, british in _SPELLING_EQUIVALENTS:
        t = t.replace(british, american).replace(american, american)
    return t


# ── Tier 1: Normalised exact match ───────────────────────────────────────────

def _tier1_normalised_match(student: str, correct: str) -> bool:
    """After normalisation + spelling unification, are they equal?"""
    s = _unify_spelling(_normalise(student))
    c = _unify_spelling(_normalise(correct))
    return s == c


# ── Tier 2: Token-set match ──────────────────────────────────────────────────

def _tier2_token_match(student: str, correct: str) -> bool:
    """Check if the key tokens in the correct answer are present in the student answer.

    This handles:
    - 'Food and shelter' matches 'Food, Shelter' (both have {food, shelter})
    - 'Understanding, Empathy' does NOT match 'Honesty, Integrity'
    """
    student_unified = _unify_spelling(_normalise(student))
    correct_unified = _unify_spelling(_normalise(correct))

    student_tokens = set(student_unified.split())
    correct_tokens = set(correct_unified.split())

    # Remove very common filler words and single-char fragments (e.g. 's' from possessives)
    noise = {"and", "or", "of", "for", "in", "to", "is", "are", "was", "were", "be"}
    correct_key = {t for t in correct_tokens - noise if len(t) > 1}
    student_key = {t for t in student_tokens - noise if len(t) > 1}

    if not correct_key:
        return True

    # Handle possessive/plural merging: 'childrens' should match 'children'
    # Build a set of stems by also checking if a token minus trailing 's' matches
    student_expanded = set(student_key)
    for token in list(student_key):
        if token.endswith("s") and len(token) > 2:
            student_expanded.add(token[:-1])  # 'childrens' → 'children'

    correct_expanded = set(correct_key)
    for token in list(correct_key):
        if token.endswith("s") and len(token) > 2:
            correct_expanded.add(token[:-1])

    # Student must have all key correct tokens (with expanded forms)
    return correct_key.issubset(student_expanded) or correct_expanded.issubset(student_expanded)


# ── Tier 3: LLM-based semantic grading ──────────────────────────────────────

_GRADING_PROMPT = """\
You are a fair and accurate exam grader. Grade the student's answer against the expected answer.

Question: {question_text}
Expected answer: {correct_answer}
Student's answer: {student_answer}

Grading rules:
- Accept spelling variations (British/American English: "organisation"/"organization")
- Accept equivalent phrasing or synonyms that convey the same meaning
- Accept answers that contain the correct information even if they include extra correct details
- For list-type questions, accept if the student provides at least the required number of valid items
- Partial abbreviation expansions should be marked correct if the key words are there
- Do NOT accept factually wrong answers even if they sound similar
- Be lenient with formatting (commas vs "and", capitalization, etc.)

Respond with ONLY a JSON object:
{{"correct": true/false, "reason": "brief explanation"}}"""


def _tier3_llm_grade(
    question_text: str,
    correct_answer: str,
    student_answer: str,
    rag_client: Any,
) -> bool | None:
    """Use the LLM to semantically compare answers.

    Returns True/False if grading succeeds, None if LLM is unavailable.
    """
    try:
        prompt = _GRADING_PROMPT.format(
            question_text=question_text,
            correct_answer=correct_answer,
            student_answer=student_answer,
        )

        result = rag_client.query_direct(
            question=prompt,
            system_prompt=(
                "You are a strict but fair exam grader. "
                "Respond ONLY with a JSON object: "
                '{"correct": true/false, "reason": "brief explanation"}'
            ),
        )

        answer_text = result.get("answer", "")

        # Parse the JSON response
        # Try to extract JSON from the response
        text = answer_text.strip()
        # Remove markdown code fences if present
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
        if start != -1 and end != -1:
            parsed = json.loads(text[start : end + 1])
            is_correct = parsed.get("correct", False)
            reason = parsed.get("reason", "")
            logger.info(
                "LLM grading: student='%s' correct='%s' → %s (%s)",
                student_answer[:50], correct_answer[:50],
                is_correct, reason[:80],
            )
            return bool(is_correct)

        logger.warning("LLM grading response not parseable: %s", answer_text[:200])
        return None

    except Exception as e:
        logger.warning("LLM grading unavailable: %s", e)
        return None


# ── Main grading function ────────────────────────────────────────────────────

def grade_answer(
    question_type: str,
    student_answer: str,
    correct_answer: str | None,
    question_text: str = "",
    rag_client: Any = None,
) -> bool:
    """Grade a student answer against the expected correct answer.

    For MCQ: exact letter match (A/B/C/D), case-insensitive.
    For short_answer/essay: multi-tier fuzzy + semantic matching.

    Args:
        question_type: "mcq", "short-answer", or "essay"
        student_answer: The student's response text
        correct_answer: The expected correct answer (from question bank)
        question_text: The original question (used for LLM context)
        rag_client: Optional RAG client for LLM-based grading

    Returns:
        True if the answer is considered correct.
    """
    if correct_answer is None:
        return False

    student = student_answer.strip()
    correct = correct_answer.strip()

    if not student:
        return False

    # ── MCQ: exact letter match ──────────────────────────────────────────
    if question_type == "mcq":
        return student.lower() == correct.lower()

    # ── Short answer / Essay: multi-tier grading ─────────────────────────

    # Tier 1: Normalised match (handles case, punctuation, articles, spelling)
    if _tier1_normalised_match(student, correct):
        logger.debug("Tier 1 match: '%s' ≈ '%s'", student[:40], correct[:40])
        return True

    # Tier 2: Token-set match (all key tokens in correct answer found in student answer)
    if _tier2_token_match(student, correct):
        logger.debug("Tier 2 token match: '%s' ≈ '%s'", student[:40], correct[:40])
        return True

    # Tier 3: LLM semantic grading (if RAG client available)
    if rag_client is not None:
        llm_result = _tier3_llm_grade(question_text, correct, student, rag_client)
        if llm_result is not None:
            return llm_result

    # No match found at any tier
    logger.debug(
        "No match: student='%s' correct='%s'",
        student[:60], correct[:60],
    )
    return False
