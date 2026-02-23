"""Pydantic schemas — re‑exported for convenience."""

from app.schemas.common import ErrorResponse, SuccessResponse  # noqa: F401
from app.schemas.user import (  # noqa: F401
    UserCreate,
    UserLogin,
    UserRead,
    Token,
)
from app.schemas.document import (  # noqa: F401
    DocumentCreate,
    DocumentRead,
)
from app.schemas.quiz import (  # noqa: F401
    QuizMode,
    EducationLevel,
    QuizGenerateRequest,
    QuizRead,
    QuestionRead,
)
from app.schemas.attempt import (  # noqa: F401
    AttemptSubmit,
    AttemptRead,
    TopicScore,
)
from app.schemas.progress import (  # noqa: F401
    TopicMetric,
    ProgressRead,
)
