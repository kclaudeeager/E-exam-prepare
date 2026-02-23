"""Chat session endpoints — persist conversation history for Ask AI.

Routes:
  POST   /api/chat/sessions          → create a new chat session
  GET    /api/chat/sessions          → list user's sessions
  GET    /api/chat/sessions/{id}     → get session with messages
  DELETE /api/chat/sessions/{id}     → delete a session
  POST   /api/chat/sessions/{id}/messages → save a message to a session
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.models import ChatMessage, ChatSession, User
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    collection: str
    title: str = "New Chat"


class AddMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    sources: list[dict] | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: str

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    id: str
    collection: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

    class Config:
        from_attributes = True


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _session_to_response(session: ChatSession, include_messages: bool = False):
    """Convert ORM model to response dict."""
    base = {
        "id": str(session.id),
        "collection": session.collection,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "message_count": len(session.messages),
    }
    if include_messages:
        base["messages"] = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json) if m.sources_json else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in session.messages
        ]
    return base


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    session = ChatSession(
        user_id=current_user.id,
        collection=body.collection,
        title=body.title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Created chat session %s for user %s", session.id, current_user.id)
    return _session_to_response(session)


@router.get("/sessions")
def list_sessions(
    collection: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's chat sessions, newest first."""
    q = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.messages))
        .filter(ChatSession.user_id == current_user.id)
    )
    if collection:
        q = q.filter(ChatSession.collection == collection)
    sessions = (
        q.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
    )
    return [_session_to_response(s) for s in sessions]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a chat session with all its messages."""
    session = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.messages))
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return _session_to_response(session, include_messages=True)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return None


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
def add_message(
    session_id: uuid.UUID,
    body: AddMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a message to a chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    message = ChatMessage(
        session_id=session.id,
        role=body.role,
        content=body.content,
        sources_json=json.dumps(body.sources) if body.sources else None,
    )
    db.add(message)

    # Auto-title: use first user message as session title
    if session.title == "New Chat" and body.role == "user":
        session.title = body.content[:80] + ("…" if len(body.content) > 80 else "")

    db.commit()
    db.refresh(message)

    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "sources": json.loads(message.sources_json) if message.sources_json else None,
        "created_at": message.created_at.isoformat(),
    }
