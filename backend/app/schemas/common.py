"""Shared / generic schemas."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error envelope (see copilot‑instructions.md)."""

    success: bool = False
    error_code: str
    message: str
    details: dict[str, Any] | None = None


class SuccessResponse(BaseModel):
    """Generic success wrapper."""

    success: bool = True
    message: str = "ok"
    data: dict[str, Any] | None = None
