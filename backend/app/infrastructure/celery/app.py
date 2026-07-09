from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "graphrag_assistant",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.ingestion_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,  # re-deliver to another worker if this one dies mid-task
    worker_prefetch_multiplier=1,  # fair dispatch across concurrent PDF jobs
    task_time_limit=60 * 20,
    task_soft_time_limit=60 * 18,
    result_expires=60 * 60 * 24,
    broker_connection_retry_on_startup=True,
)
