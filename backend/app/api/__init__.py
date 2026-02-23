"""API route package — imports all routers for main.py."""

from app.api.health import router as health_router  # noqa: F401
from app.api.users import router as users_router  # noqa: F401
from app.api.documents import router as documents_router  # noqa: F401
from app.api.quiz import router as quiz_router  # noqa: F401
from app.api.attempts import router as attempts_router  # noqa: F401
from app.api.progress import router as progress_router  # noqa: F401
from app.api.rag import router as rag_router  # noqa: F401
from app.api.chat import router as chat_router  # noqa: F401
from app.api.admin import router as admin_router  # noqa: F401
