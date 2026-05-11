"""Tasks package for Celery workers."""

from workers.tasks import research, browser

__all__ = ["research", "browser"]
