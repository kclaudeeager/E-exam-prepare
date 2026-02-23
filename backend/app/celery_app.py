"""Celery application — async task worker for background jobs."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "e_exam_prepare",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Run tasks synchronously in-process when True (dev default, no Redis needed).
    # Set CELERY_TASK_ALWAYS_EAGER=false in .env when running a real worker.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,  # Raise task exceptions immediately when eager
)

# Auto-discover tasks from this module (registered below) and any
# future ``tasks.py`` files inside backend packages.
celery_app.autodiscover_tasks(["app"])
