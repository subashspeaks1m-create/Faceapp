"""PostgreSQL access: connection pool, ordered SQL migrations and job-event notifications."""

from __future__ import annotations
import asyncio
import contextlib
import hashlib
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

MIGRATIONS = Path(__file__).resolve().parents[3] / "db/migrations"


def open_pool(url: str, *, min_size: int = 1, max_size: int = 10) -> AsyncConnectionPool:
    return AsyncConnectionPool(url, min_size=min_size, max_size=max_size, kwargs={"row_factory": dict_row}, open=False)


def migrate(url: str, directory: Path = MIGRATIONS) -> list[str]:
    """Apply unapplied migrations in filename order; refuse edited, already-applied files."""
    applied: list[str] = []
    with psycopg.connect(url, autocommit=False) as conn:
        conn.execute(
            'CREATE TABLE IF NOT EXISTS "_portraitlab_migrations" '
            "(name text PRIMARY KEY, sha256 char(64) NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        conn.execute("SELECT pg_advisory_xact_lock(724100)")
        done = {r[0]: r[1] for r in conn.execute('SELECT name, sha256 FROM "_portraitlab_migrations"')}
        for path in sorted(directory.glob("*.sql")):
            sql = path.read_text()
            digest = hashlib.sha256(sql.encode()).hexdigest()
            if path.name in done:
                if done[path.name] != digest:
                    raise RuntimeError(f"Applied migration {path.name} was modified")
                continue
            conn.execute(sql)
            conn.execute('INSERT INTO "_portraitlab_migrations"(name, sha256) VALUES (%s, %s)', (path.name, digest))
            applied.append(path.name)
        conn.commit()
    return applied


class JobEvents:
    """One LISTEN connection fans job_events out to in-process waiters.

    Long-poll requests wait on an asyncio.Event, so no pooled connection or
    transaction is held while a client waits.
    """

    def __init__(self, url: str):
        self.url = url
        self._waiters: dict[UUID, set[asyncio.Event]] = {}
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._listen())
        await asyncio.wait_for(self._ready.wait(), timeout=10)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _listen(self) -> None:
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(self.url, autocommit=True) as conn:
                    await conn.execute("LISTEN job_events")
                    self._ready.set()
                    # Wake everyone after a (re)connect: notifications may have been missed.
                    self._wake_all()
                    async for note in conn.notifies():
                        with contextlib.suppress(ValueError):
                            self._wake(UUID(note.payload))
            except asyncio.CancelledError:
                raise
            except psycopg.Error:
                self._wake_all()
                await asyncio.sleep(1)

    def _wake(self, job_id: UUID) -> None:
        for event in self._waiters.get(job_id, ()):
            event.set()

    def _wake_all(self) -> None:
        for events in self._waiters.values():
            for event in events:
                event.set()

    @contextlib.contextmanager
    def subscribe(self, job_id: UUID):
        event = asyncio.Event()
        self._waiters.setdefault(job_id, set()).add(event)
        try:
            yield event
        finally:
            group = self._waiters.get(job_id)
            if group is not None:
                group.discard(event)
                if not group:
                    del self._waiters[job_id]
