"""Job execution under at-least-once delivery: leases, fences, conditional attach and one-time settlement."""

from __future__ import annotations
import asyncio
import contextlib
import logging
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from . import ledger
from .config import Settings
from .inference import ExecutionFailed, ExecutionRequest, Executor
from .storage import ObjectStore, StorageError

log = logging.getLogger("portraitlab.worker")


def result_prefix(job_id: UUID, fence: int) -> str:
    return f"jobs/{job_id}/f{fence}/"


class JobWorker:
    def __init__(self, settings: Settings, pool, store: ObjectStore, executor: Executor):
        self.settings, self.pool, self.store, self.executor = settings, pool, store, executor

    async def _claim(self, job_id: UUID):
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'UPDATE "ImageJob" SET status = \'RUNNING\', fence = fence + 1, "attemptCount" = "attemptCount" + 1, '
                '"leaseExpiresAt" = now() + make_interval(secs => %s), "startedAt" = COALESCE("startedAt", now()), '
                'stage = \'decode\', "eventRevision" = "eventRevision" + 1 '
                'WHERE id = %s AND status = \'QUEUED\' AND "tombstonedAt" IS NULL AND "expiresAt" > now() '
                'AND "attemptCount" < %s RETURNING *',
                (self.settings.worker_lease_seconds, job_id, self.settings.max_attempts),
            )
            return await cur.fetchone()

    async def _renew(self, job_id: UUID, fence: int) -> bool:
        """Extend the lease while this fence still owns a live, unrevoked job."""
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'UPDATE "ImageJob" SET "leaseExpiresAt" = now() + make_interval(secs => %s) '
                "WHERE id = %s AND fence = %s AND status = 'RUNNING' AND \"tombstonedAt\" IS NULL "
                'AND "expiresAt" > now() RETURNING id',
                (self.settings.worker_lease_seconds, job_id, fence),
            )
            return await cur.fetchone() is not None

    async def _heartbeat(self, job_id: UUID, fence: int, lost: threading.Event) -> None:
        interval = max(1.0, self.settings.worker_lease_seconds / 3)
        while not lost.is_set():
            await asyncio.sleep(interval)
            if not await self._renew(job_id, fence):
                lost.set()

    async def _finish_without_result(self, job, fence: int, code: str) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "UPDATE \"ImageJob\" SET status = CASE WHEN status = 'CANCEL_REQUESTED' "
                "THEN 'CANCELED'::\"JobStatus\" ELSE 'FAILED'::\"JobStatus\" END, "
                '"safeErrorCode" = %s, "completedAt" = now(), "leaseExpiresAt" = NULL, '
                '"eventRevision" = "eventRevision" + 1 '
                "WHERE id = %s AND fence = %s AND status IN ('RUNNING','CANCEL_REQUESTED') RETURNING *",
                (code, job["id"], fence),
            )
            if await cur.fetchone() is not None:
                await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"])

    async def process(self, job_id: UUID) -> str:
        """Run one delivery of a job. Returns an outcome label for logs/tests (never portrait data)."""
        job = await self._claim(job_id)
        if job is None:
            return "not_claimable"  # Duplicate delivery, cancelled, tombstoned, expired or retries exhausted.
        fence = job["fence"]
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'SELECT a."objectPrefix", a."purgedAt", f.ordinal FROM "UploadAsset" a '
                'JOIN "AssetFace" f ON f."assetId" = a.id AND f.id = %s WHERE a.id = %s AND a."userId" = %s '
                'AND a."expiresAt" > now()',
                (job["faceId"], job["assetId"], job["userId"]),
            )
            source = await cur.fetchone()
        if source is None or source["purgedAt"] is not None or source["objectPrefix"] is None:
            await self._finish_without_result(job, fence, "ASSET_EXPIRED")
            return "failed"
        if not await self._renew(job_id, fence):  # Fence check before fetching input.
            await self._finish_without_result(job, fence, "JOB_CANCELED")
            return "lost_before_fetch"
        try:
            source_png, _ = await self.store.read_limited(source["objectPrefix"] + "normalized.png", 256 * 1024 * 1024)
        except StorageError:
            await self._finish_without_result(job, fence, "ASSET_EXPIRED")
            return "failed"
        request = ExecutionRequest(
            filter_type=job["filterType"],
            intensity=float(job["intensity"]),
            face_ordinal=source["ordinal"],
            preserve_background=job["preserveBackground"],
            options=dict(job["parameters"] or {}),
        )
        lost = threading.Event()
        heartbeat = asyncio.create_task(self._heartbeat(job_id, fence, lost))
        try:
            output = await asyncio.to_thread(self.executor.run, source_png, request, lost.is_set)
        except ExecutionFailed as e:
            await self._finish_without_result(job, fence, e.code)
            return "failed"
        except Exception:
            log.exception("job execution error job=%s", job_id)  # Opaque id only.
            await self._finish_without_result(job, fence, "INTERNAL_ERROR")
            return "failed"
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            del source_png
        if lost.is_set() or not await self._renew(job_id, fence):
            await self._finish_without_result(job, fence, "JOB_CANCELED")
            return "lost_before_write"
        prefix = result_prefix(job_id, fence)
        key = prefix + "result.png"
        await self.store.put(key, output, "image/png")
        return await self._attach(job, fence, key, prefix)

    async def _attach(self, job, fence: int, key: str, prefix: str) -> str:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    "UPDATE \"ImageJob\" SET status = 'SUCCEEDED', stage = 'done', \"resultObjectKey\" = %s, "
                    '"resultExpiresAt" = LEAST(now() + make_interval(secs => %s), "expiresAt"), '
                    '"completedAt" = now(), "leaseExpiresAt" = NULL, "eventRevision" = "eventRevision" + 1 '
                    "WHERE id = %s AND fence = %s AND status = 'RUNNING' AND \"tombstonedAt\" IS NULL "
                    'AND "expiresAt" > now() RETURNING *',
                    (key, self.settings.result_delivery_seconds, job["id"], fence),
                )
                if await cur.fetchone() is not None:
                    await ledger.settle(conn, job["userId"], job["id"], job["reservedUnits"])
                    await conn.execute(
                        'INSERT INTO "AuditLog"(id, "userId", "jobId", action, "requestId", "safeMetadata") '
                        "VALUES (%s, %s, %s, 'job.succeeded', %s, %s)",
                        (uuid4(), job["userId"], job["id"], uuid4(), Jsonb({})),
                    )
                    return "succeeded"
        # Lost the race (cancel, delete, purge, expiry or a newer fence): resolve and drop the output.
        await self._finish_without_result(job, fence, "JOB_CANCELED")
        await self.store.delete_prefix(prefix)
        return "late_output_deleted"


class Reconciler:
    """Dead-lease recovery, expiry of queued work and orphan reservation repair."""

    def __init__(self, settings: Settings, pool):
        self.settings, self.pool = settings, pool

    async def run_once(self) -> dict[str, int]:
        counts = {"requeued": 0, "failed": 0, "canceled": 0, "expired": 0, "released": 0}
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    "SELECT * FROM \"ImageJob\" WHERE status IN ('RUNNING','CANCEL_REQUESTED') "
                    'AND "leaseExpiresAt" < now() FOR UPDATE SKIP LOCKED LIMIT 100'
                )
                for job in await cur.fetchall():
                    retry = (
                        job["status"] == "RUNNING"
                        and job["attemptCount"] < self.settings.max_attempts
                        and job["tombstonedAt"] is None
                        and job["expiresAt"] > datetime.now(timezone.utc)
                    )
                    if retry:
                        await conn.execute(
                            "UPDATE \"ImageJob\" SET status = 'QUEUED', stage = 'queued', \"leaseExpiresAt\" = NULL, "
                            '"eventRevision" = "eventRevision" + 1 WHERE id = %s',
                            (job["id"],),
                        )
                        await conn.execute(
                            'INSERT INTO "OutboxEvent"(id, "aggregateId", "eventType", payload) VALUES (%s, %s, %s, %s)',
                            (uuid4(), job["id"], "job.dispatch", Jsonb({"job_id": str(job["id"])})),
                        )
                        counts["requeued"] += 1
                        continue
                    canceled = job["status"] == "CANCEL_REQUESTED" or job["tombstonedAt"] is not None
                    await conn.execute(
                        'UPDATE "ImageJob" SET status = %s, "safeErrorCode" = %s, "completedAt" = now(), '
                        '"leaseExpiresAt" = NULL, "eventRevision" = "eventRevision" + 1 WHERE id = %s',
                        (
                            "CANCELED" if canceled else "FAILED",
                            "JOB_CANCELED" if canceled else "WORKER_LOST",
                            job["id"],
                        ),
                    )
                    await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"])
                    counts["canceled" if canceled else "failed"] += 1
                cur = await conn.execute(
                    'SELECT * FROM "ImageJob" WHERE status = \'QUEUED\' AND "expiresAt" <= now() '
                    "FOR UPDATE SKIP LOCKED LIMIT 100"
                )
                for job in await cur.fetchall():
                    await conn.execute(
                        "UPDATE \"ImageJob\" SET status = 'EXPIRED', \"safeErrorCode\" = 'JOB_EXPIRED', "
                        '"completedAt" = now(), "eventRevision" = "eventRevision" + 1 WHERE id = %s',
                        (job["id"],),
                    )
                    await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"])
                    counts["expired"] += 1
                # Terminal jobs whose reservation was never closed (crash between steps).
                cur = await conn.execute(
                    "SELECT j.* FROM \"ImageJob\" j WHERE j.status NOT IN ('QUEUED','RUNNING','CANCEL_REQUESTED') "
                    "AND j.status <> 'SUCCEEDED' AND NOT EXISTS (SELECT 1 FROM \"CreditTransaction\" t "
                    "WHERE t.\"jobId\" = j.id AND t.kind IN ('SETTLE','RELEASE')) FOR UPDATE OF j SKIP LOCKED LIMIT 100"
                )
                for job in await cur.fetchall():
                    if await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"]):
                        counts["released"] += 1
        return counts


class OutboxRelay:
    """Publishes committed dispatch events. A crash between publish and mark causes redelivery, which the claim tolerates."""

    def __init__(self, pool, publish):
        self.pool, self.publish = pool, publish

    async def run_once(self, limit: int = 50) -> int:
        sent = 0
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    'SELECT id, "aggregateId" FROM "OutboxEvent" WHERE "dispatchedAt" IS NULL '
                    'ORDER BY "createdAt" FOR UPDATE SKIP LOCKED LIMIT %s',
                    (limit,),
                )
                for row in await cur.fetchall():
                    await asyncio.to_thread(self.publish, row["aggregateId"])
                    await conn.execute('UPDATE "OutboxEvent" SET "dispatchedAt" = now() WHERE id = %s', (row["id"],))
                    sent += 1
        return sent
