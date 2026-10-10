"""Ephemeral purge daemon: tombstone and revoke first, then delete bytes, verify, and redact pointers."""

from __future__ import annotations
import random
from uuid import UUID
from . import ledger
from .config import Settings
from .storage import ObjectStore, StorageError

CLAIM_SECONDS = 60  # A claimed row is invisible to other purge workers while its I/O runs.


def _backoff(attempt: int) -> float:
    return min(60.0, 2.0**attempt) * random.uniform(0.5, 1.0)


class PurgeDaemon:
    def __init__(self, settings: Settings, pool, store: ObjectStore):
        self.settings, self.pool, self.store = settings, pool, store

    async def run_once(self) -> dict[str, int]:
        counts = {"jobs": 0, "assets": 0, "failures": 0, "stray_prefixes": 0}
        for job_id in await self._claim_jobs():
            ok = await self._purge_job(job_id)
            counts["jobs" if ok else "failures"] += 1
        for asset_id, prefix in await self._claim_assets():
            ok = await self._purge_asset(asset_id, prefix)
            counts["assets" if ok else "failures"] += 1
        return counts

    # ---------------------------------------------------------------- jobs
    async def _claim_jobs(self) -> list[UUID]:
        claimed: list[UUID] = []
        async with self.pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                'SELECT * FROM "ImageJob" WHERE "purgedAt" IS NULL '
                'AND ("nextPurgeAt" IS NULL OR "nextPurgeAt" <= now()) AND ('
                '  "tombstonedAt" IS NOT NULL OR "expiresAt" <= now() '
                "  OR (status = 'SUCCEEDED' AND \"resultExpiresAt\" <= now())"
                ") FOR UPDATE SKIP LOCKED LIMIT 20"
            )
            for job in await cur.fetchall():
                if job["status"] in ("QUEUED", "RUNNING", "CANCEL_REQUESTED"):
                    await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"])
                # Tombstone + revoke before any byte deletion; state can never return to live.
                await conn.execute(
                    'UPDATE "ImageJob" SET "tombstonedAt" = COALESCE("tombstonedAt", now()), '
                    "status = CASE WHEN status IN ('QUEUED','RUNNING','CANCEL_REQUESTED','SUCCEEDED') "
                    "THEN 'EXPIRED'::\"JobStatus\" ELSE status END, "
                    '"completedAt" = COALESCE("completedAt", now()), "leaseExpiresAt" = NULL, '
                    '"nextPurgeAt" = now() + make_interval(secs => %s), "eventRevision" = "eventRevision" + 1 '
                    "WHERE id = %s",
                    (CLAIM_SECONDS, job["id"]),
                )
                claimed.append(job["id"])
        return claimed

    async def _purge_job(self, job_id: UUID) -> bool:
        try:
            await self.store.delete_prefix(f"jobs/{job_id}/")
        except StorageError:
            await self._retry_later("ImageJob", job_id)
            return False
        async with self.pool.connection() as conn:
            await conn.execute(
                'UPDATE "ImageJob" SET status = \'PURGED\', "purgedAt" = now(), "resultObjectKey" = NULL, '
                '"resultExpiresAt" = NULL, "nextPurgeAt" = NULL, "eventRevision" = "eventRevision" + 1 WHERE id = %s',
                (job_id,),
            )
        return True

    # ---------------------------------------------------------------- assets
    async def _claim_assets(self) -> list[tuple[UUID, str | None]]:
        s = self.settings
        claimed: list[tuple[UUID, str | None]] = []
        async with self.pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                'SELECT a.id, a."objectPrefix" FROM "UploadAsset" a WHERE a."purgedAt" IS NULL '
                'AND (a."nextPurgeAt" IS NULL OR a."nextPurgeAt" <= now()) AND ('
                '  a."expiresAt" <= now() '
                '  OR (a."finalizedAt" IS NULL AND a."createdAt" <= now() - make_interval(secs => %s)) '
                '  OR (a."finalizedAt" IS NOT NULL AND EXISTS (SELECT 1 FROM "ImageJob" j WHERE j."assetId" = a.id) '
                '      AND NOT EXISTS (SELECT 1 FROM "ImageJob" j WHERE j."assetId" = a.id AND ('
                "        (j.status IN ('QUEUED','RUNNING','CANCEL_REQUESTED') AND j.\"tombstonedAt\" IS NULL) "
                '        OR j."completedAt" > now() - make_interval(secs => %s))))'
                ") FOR UPDATE OF a SKIP LOCKED LIMIT 20",
                (s.orphan_upload_seconds, s.source_idle_purge_seconds),
            )
            for row in await cur.fetchall():
                await conn.execute(
                    'UPDATE "UploadAsset" SET "expiresAt" = LEAST("expiresAt", now()), '
                    '"nextPurgeAt" = now() + make_interval(secs => %s) WHERE id = %s',
                    (CLAIM_SECONDS, row["id"]),
                )
                claimed.append((row["id"], row["objectPrefix"]))
        return claimed

    async def _purge_asset(self, asset_id: UUID, prefix: str | None) -> bool:
        try:
            if prefix:
                await self.store.delete_prefix(prefix)
        except StorageError:
            await self._retry_later("UploadAsset", asset_id)
            return False
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute('DELETE FROM "AssetFace" WHERE "assetId" = %s', (asset_id,))
            await conn.execute(
                'UPDATE "UploadAsset" SET "purgedAt" = now(), "objectPrefix" = NULL, "checksumSha256" = NULL, '
                '"nextPurgeAt" = NULL WHERE id = %s',
                (asset_id,),
            )
        return True

    async def _retry_later(self, table: str, row_id: UUID) -> None:
        assert table in ("ImageJob", "UploadAsset")
        async with self.pool.connection() as conn:
            cur = await conn.execute(f'SELECT "purgeAttemptCount" AS n FROM "{table}" WHERE id = %s', (row_id,))
            attempts = (await cur.fetchone())["n"] + 1
            await conn.execute(
                f'UPDATE "{table}" SET "purgeAttemptCount" = %s, '
                '"nextPurgeAt" = now() + make_interval(secs => %s) WHERE id = %s',
                (attempts, _backoff(attempts), row_id),
            )

    # ---------------------------------------------------------------- inventory backstop
    async def sweep_inventory(self) -> int:
        """Delete object prefixes no live metadata row accounts for (crash between write and attach/record)."""
        removed = 0
        for top, table in (("jobs/", "ImageJob"), ("assets/", "UploadAsset")):
            for child in await self.store.list_children(top):
                try:
                    row_id = UUID(child[len(top) :].strip("/"))
                except ValueError:
                    row_id = None
                keep = False
                if row_id is not None:
                    async with self.pool.connection() as conn:
                        cur = await conn.execute(f'SELECT "purgedAt" FROM "{table}" WHERE id = %s', (row_id,))
                        row = await cur.fetchone()
                    keep = row is not None and row["purgedAt"] is None
                if not keep:
                    await self.store.delete_prefix(child)
                    removed += 1
        return removed
