"""Celery transport. The queue carries only an opaque job id; PostgreSQL holds all state."""

from __future__ import annotations
import asyncio
import threading
from uuid import UUID
from celery import Celery
import celery_config
from .config import load_settings
from .db import open_pool
from .service import FILTERS, REGISTRY
from .inference import RegistryExecutor
from .storage import ObjectStore
from .worker import JobWorker

app = Celery("portraitlab")
app.config_from_object(celery_config)

_loop: asyncio.AbstractEventLoop | None = None
_worker: JobWorker | None = None
_lock = threading.Lock()


def _get_worker() -> tuple[asyncio.AbstractEventLoop, JobWorker]:
    global _loop, _worker
    with _lock:
        if _worker is None:
            settings = load_settings()
            _loop = asyncio.new_event_loop()
            pool = open_pool(settings.database_url, max_size=2)
            _loop.run_until_complete(pool.open(wait=True))
            _worker = JobWorker(settings, pool, ObjectStore(settings.storage), RegistryExecutor(REGISTRY, FILTERS))
        return _loop, _worker


@app.task(name="portraitlab.process_job", ignore_result=True)
def process_job(job_id: str) -> None:
    loop, worker = _get_worker()
    loop.run_until_complete(worker.process(UUID(job_id)))


def publish_job(job_id: UUID) -> None:
    process_job.apply_async(args=[str(job_id)])
