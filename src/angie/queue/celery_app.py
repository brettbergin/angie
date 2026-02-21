"""Celery application configuration."""

from celery import Celery

from angie.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()

    app = Celery("angie")
    app.config_from_object(
        {
            "broker_url": settings.effective_celery_broker,
            "result_backend": settings.effective_celery_backend,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
            "task_track_started": True,
            "task_acks_late": True,
            "worker_prefetch_multiplier": 1,
            "task_routes": {
                "angie.queue.workers.execute_task": {"queue": "tasks"},
                "angie.queue.workers.execute_workflow": {"queue": "workflows"},
            },
        }
    )
    app.autodiscover_tasks(["angie.queue"], related_name="workers")
    return app


celery_app = create_celery_app()
