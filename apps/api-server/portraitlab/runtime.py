"""PostgreSQL + S3 implementation of the API Runtime protocol."""

from __future__ import annotations
import asyncio
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from schemas import (
    AssetReceipt,
    ConsentReceipt,
    ConsentRequest,
    DeletionReceipt,
    JobPayload,
    SafeError,
    TransformRequest,
    UploadComplete,
    UploadGrant,
    UploadRequest,
)
from . import ledger, media
from .auth import JwtVerifier
from .config import Settings
from .db import JobEvents
from .errors import ApiError, not_found
from .imaging import ImageRejected, normalize
from .inference import Executor, FaceDetector
from .storage import ObjectStore, StorageError

LIVE = ("QUEUED", "RUNNING", "CANCEL_REQUESTED")
TERMINAL_WIRE = {"succeeded", "failed", "canceled", "expired", "purged"}
HASH_VERSION = "transform-request.v1"


def canonical_request_hash(body: TransformRequest) -> str:
    """SHA256 over validated defaults + options, sorted UTF-8 JSON, versioned normalization rule."""
    data = {"v": HASH_VERSION, **body.model_dump(mode="json")}
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class PostgresRuntime:
    def __init__(
        self,
        settings: Settings,
        pool,
        store: ObjectStore,
        events: JobEvents,
        verifier: JwtVerifier,
        detector: FaceDetector | None,
        executor: Executor,
        on_job_created=None,
    ):
        self.settings, self.pool, self.store, self.events = settings, pool, store, events
        self.verifier, self.detector, self.executor = verifier, detector, executor
        # Optional hook (e.g. wake the outbox relay); the outbox row is the durable record.
        self.on_job_created = on_job_created

    # ------------------------------------------------------------------ identity
    async def authenticate(self, token: str) -> UUID:
        subject = await self.verifier.verify(token)
        async with self.pool.connection() as conn:
            cur = await conn.execute('SELECT id, "deletedAt" FROM "User" WHERE "externalSubject" = %s', (subject,))
            row = await cur.fetchone()
            if row is None:
                async with conn.transaction():
                    await conn.execute(
                        'INSERT INTO "User"(id, "externalSubject") VALUES (%s, %s) '
                        'ON CONFLICT ("externalSubject") DO NOTHING',
                        (uuid4(), subject),
                    )
                    cur = await conn.execute(
                        'SELECT id, "deletedAt" FROM "User" WHERE "externalSubject" = %s', (subject,)
                    )
                    row = await cur.fetchone()
                    await conn.execute(
                        'INSERT INTO "CreditWallet"("userId") VALUES (%s) ON CONFLICT DO NOTHING', (row["id"],)
                    )
        if row["deletedAt"] is not None:
            raise ApiError(403, "ACCOUNT_DELETED")
        return row["id"]

    # ------------------------------------------------------------------ consent
    def _consent(self, row) -> ConsentReceipt:
        return ConsentReceipt(
            consent_receipt_id=row["id"],
            policy_version=row["policyVersion"],
            purpose=row["purpose"],
            processor_region=row["processorRegion"],
            accepted_at=_utc(row["acceptedAt"]),
            withdrawn_at=_utc(row["withdrawnAt"]) if row["withdrawnAt"] else None,
        )

    async def give_consent(self, owner: UUID, body: ConsentRequest) -> ConsentReceipt:
        if body.policy_version != self.settings.consent_policy_version:
            raise ApiError(409, "POLICY_OUTDATED")
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'INSERT INTO "ConsentReceipt"(id, "userId", "policyVersion", "processorRegion", purpose, "acceptedAt") '
                "VALUES (%s, %s, %s, %s, %s, now()) RETURNING *",
                (uuid4(), owner, body.policy_version, body.processor_region, body.purpose),
            )
            return self._consent(await cur.fetchone())

    async def withdraw_consent(self, owner: UUID, consent_id: UUID) -> ConsentReceipt:
        async with self.pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                'SELECT * FROM "ConsentReceipt" WHERE id = %s AND "userId" = %s FOR UPDATE', (consent_id, owner)
            )
            row = await cur.fetchone()
            if row is None:
                raise not_found("CONSENT_NOT_FOUND")
            if row["withdrawnAt"] is None:
                cur = await conn.execute(
                    'UPDATE "ConsentReceipt" SET "withdrawnAt" = now() WHERE id = %s RETURNING *', (consent_id,)
                )
                row = await cur.fetchone()
                # Revoke every dependent asset and job now; the purge daemon removes bytes.
                await conn.execute(
                    'UPDATE "UploadAsset" SET "expiresAt" = LEAST("expiresAt", now()), "nextPurgeAt" = now() '
                    'WHERE "consentReceiptId" = %s AND "purgedAt" IS NULL',
                    (consent_id,),
                )
                cur = await conn.execute(
                    'SELECT j.* FROM "ImageJob" j JOIN "UploadAsset" a ON a.id = j."assetId" '
                    'WHERE a."consentReceiptId" = %s AND j."tombstonedAt" IS NULL FOR UPDATE OF j',
                    (consent_id,),
                )
                for job in await cur.fetchall():
                    await self._tombstone(conn, job)
        return self._consent(row)

    # ------------------------------------------------------------------ uploads
    async def upload(self, owner: UUID, body: UploadRequest) -> UploadGrant:
        s = self.settings
        if body.byte_length > s.max_upload_bytes:
            raise ApiError(422, "UPLOAD_TOO_LARGE")
        async with self.pool.connection() as conn, conn.transaction():
            # Serialize this owner's grant admission on the wallet row.
            await conn.execute('SELECT 1 FROM "CreditWallet" WHERE "userId" = %s FOR UPDATE', (owner,))
            cur = await conn.execute(
                'SELECT "withdrawnAt", "policyVersion" FROM "ConsentReceipt" WHERE id = %s AND "userId" = %s',
                (body.consent_receipt_id, owner),
            )
            consent = await cur.fetchone()
            if consent is None:
                raise not_found("CONSENT_NOT_FOUND")
            if consent["withdrawnAt"] is not None or consent["policyVersion"] != s.consent_policy_version:
                raise ApiError(403, "CONSENT_REQUIRED")
            cur = await conn.execute(
                'SELECT count(*) AS n FROM "UploadAsset" WHERE "userId" = %s AND "createdAt" > now() - interval \'1 minute\'',
                (owner,),
            )
            if (await cur.fetchone())["n"] >= s.upload_grants_per_minute:
                raise ApiError(429, "RATE_LIMITED")
            asset_id = uuid4()
            prefix = f"assets/{asset_id}/{secrets.token_hex(16)}/"
            cur = await conn.execute(
                'INSERT INTO "UploadAsset"(id, "userId", "consentReceiptId", "objectPrefix", "mimeType", "byteLength", '
                '"checksumSha256", "expiresAt") VALUES (%s, %s, %s, %s, %s, %s, %s, now() + make_interval(secs => %s)) '
                'RETURNING "createdAt", "expiresAt"',
                (
                    asset_id,
                    owner,
                    body.consent_receipt_id,
                    prefix,
                    body.mime_type,
                    body.byte_length,
                    body.checksum_sha256,
                    s.asset_absolute_ttl_seconds,
                ),
            )
            row = await cur.fetchone()
        url, headers = self.store.presign_put(
            prefix + "original", body.mime_type, body.checksum_sha256, s.upload_grant_seconds
        )
        return UploadGrant(
            asset_id=asset_id,
            upload_url=url,
            required_headers=headers,
            expires_at=_utc(row["createdAt"]) + timedelta(seconds=s.upload_grant_seconds),
            absolute_purge_at=_utc(row["expiresAt"]),
        )

    async def _asset_receipt(self, conn, asset) -> AssetReceipt:
        cur = await conn.execute('SELECT id FROM "AssetFace" WHERE "assetId" = %s ORDER BY ordinal', (asset["id"],))
        return AssetReceipt(
            asset_id=asset["id"],
            normalized_width=asset["normalizedWidth"],
            normalized_height=asset["normalizedHeight"],
            faces=[r["id"] for r in await cur.fetchall()],
            expires_at=_utc(asset["expiresAt"]),
        )

    async def _reject_upload(self, asset_id: UUID, prefix: str, status: int, code: str) -> ApiError:
        """Delete everything under the asset prefix and close the asset; return the error to raise."""
        try:
            await self.store.delete_prefix(prefix)
            async with self.pool.connection() as conn:
                await conn.execute(
                    'UPDATE "UploadAsset" SET "purgedAt" = now(), "objectPrefix" = NULL, "checksumSha256" = NULL, '
                    '"expiresAt" = LEAST("expiresAt", now()) WHERE id = %s',
                    (asset_id,),
                )
        except StorageError:
            # Leave it for the purge daemon; still revoke use immediately.
            async with self.pool.connection() as conn:
                await conn.execute(
                    'UPDATE "UploadAsset" SET "expiresAt" = LEAST("expiresAt", now()), "nextPurgeAt" = now() '
                    "WHERE id = %s",
                    (asset_id,),
                )
        return ApiError(status, code)

    async def complete(self, owner: UUID, asset_id: UUID, body: UploadComplete) -> AssetReceipt:
        s = self.settings
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'SELECT a.*, c."withdrawnAt" FROM "UploadAsset" a JOIN "ConsentReceipt" c ON c.id = a."consentReceiptId" '
                'WHERE a.id = %s AND a."userId" = %s',
                (asset_id, owner),
            )
            asset = await cur.fetchone()
            if asset is None:
                raise not_found("ASSET_NOT_FOUND")
            if asset["purgedAt"] is not None or _utc(asset["expiresAt"]) <= datetime.now(timezone.utc):
                raise ApiError(410, "ASSET_EXPIRED")
            if asset["finalizedAt"] is not None:
                return await self._asset_receipt(conn, asset)
        if asset["withdrawnAt"] is not None:
            raise ApiError(403, "CONSENT_REQUIRED")
        if body.checksum_sha256 != asset["checksumSha256"]:
            raise ApiError(409, "CHECKSUM_MISMATCH")
        prefix, key = asset["objectPrefix"], asset["objectPrefix"] + "original"
        head = await self.store.head(key)
        if head is None:
            raise ApiError(409, "UPLOAD_MISSING")
        if head.byte_length != asset["byteLength"] or head.byte_length > s.max_upload_bytes:
            raise await self._reject_upload(asset_id, prefix, 422, "UPLOAD_SIZE_MISMATCH")
        try:
            data, digest = await self.store.read_limited(key, s.max_upload_bytes)
        except StorageError:
            raise await self._reject_upload(asset_id, prefix, 422, "UPLOAD_SIZE_MISMATCH") from None
        if digest != asset["checksumSha256"]:
            raise await self._reject_upload(asset_id, prefix, 422, "UPLOAD_CHECKSUM_FAILED")
        try:
            image = await asyncio.to_thread(normalize, data, asset["mimeType"], s.max_decoded_pixels)
        except ImageRejected as e:
            raise await self._reject_upload(asset_id, prefix, 422, e.code) from None
        del data
        if self.detector is None:
            raise await self._reject_upload(asset_id, prefix, 503, "DETECTOR_UNAVAILABLE")
        faces = sorted(await asyncio.to_thread(self.detector.detect, image.rgb), key=lambda f: -f.score)[:8]
        await self.store.put(prefix + "normalized.png", image.png, "image/png")
        await self.store.delete_prefix(prefix + "original")
        async with self.pool.connection() as conn, conn.transaction():
            cur = await conn.execute('SELECT * FROM "UploadAsset" WHERE id = %s FOR UPDATE', (asset_id,))
            current = await cur.fetchone()
            if current["purgedAt"] is not None or _utc(current["expiresAt"]) <= datetime.now(timezone.utc):
                raise ApiError(410, "ASSET_EXPIRED")
            if current["finalizedAt"] is None:
                for ordinal, face in enumerate(faces):
                    await conn.execute(
                        'INSERT INTO "AssetFace"(id, "assetId", "userId", ordinal, bbox, landmarks5, score) '
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (uuid4(), asset_id, owner, ordinal, Jsonb(face.bbox), Jsonb(face.landmarks5), face.score),
                    )
                cur = await conn.execute(
                    'UPDATE "UploadAsset" SET "finalizedAt" = now(), "normalizedWidth" = %s, "normalizedHeight" = %s '
                    "WHERE id = %s RETURNING *",
                    (image.width, image.height, asset_id),
                )
                current = await cur.fetchone()
            return await self._asset_receipt(conn, current)

    # ------------------------------------------------------------------ jobs
    def _payload(self, job) -> JobPayload:
        now = datetime.now(timezone.utc)
        status = job["status"].lower()
        if job["purgedAt"] is not None:
            status = "purged"
        elif status in ("queued", "running", "cancel_requested", "succeeded") and _utc(job["expiresAt"]) <= now:
            status = "expired"
        url = expires = None
        if (
            status == "succeeded"
            and job["tombstonedAt"] is None
            and job["resultObjectKey"] is not None
            and job["resultExpiresAt"] is not None
            and _utc(job["resultExpiresAt"]) > now
        ):
            token_expiry = min(
                int(time.time()) + self.settings.media_token_seconds, int(job["resultExpiresAt"].timestamp())
            )
            token = media.sign(
                self.settings.media_token_secret, media.MediaClaim(job["id"], job["userId"], job["fence"], token_expiry)
            )
            url = f"/api/v1/media/{token}"
            expires = datetime.fromtimestamp(token_expiry, timezone.utc)
        error = None
        if job["safeErrorCode"] and status in ("failed", "canceled", "expired"):
            error = SafeError(
                code=job["safeErrorCode"],
                message="Request could not be completed.",
                retryable=False,
                request_id=uuid4(),
            )
        complete = status == "succeeded"
        return JobPayload(
            job_id=job["id"],
            asset_id=job["assetId"],
            face_id=job["faceId"],
            source_revision=job["sourceRevision"],
            candidate_revision=job["candidateRevision"],
            status=status,
            stage="done" if complete else job["stage"],
            event_revision=job["eventRevision"],
            progress_percent=100.0 if complete else None,
            progress_source="complete" if complete else "indeterminate",
            result_cdn_url=url,
            result_expires_at=expires,
            error=error,
            created_at=_utc(job["createdAt"]),
            updated_at=_utc(job["completedAt"] or job["startedAt"] or job["createdAt"]),
        )

    async def _job(self, conn, owner: UUID, job_id: UUID, *, lock: bool = False):
        cur = await conn.execute(
            'SELECT * FROM "ImageJob" WHERE id = %s AND "userId" = %s' + (" FOR UPDATE" if lock else ""),
            (job_id, owner),
        )
        job = await cur.fetchone()
        if job is None:
            raise not_found("JOB_NOT_FOUND")
        return job

    async def transform(self, owner: UUID, body: TransformRequest, idempotency_key: str) -> JobPayload:
        s = self.settings
        request_hash = canonical_request_hash(body)
        units = s.credit_units_per_job
        async with self.pool.connection() as conn:
            async with conn.transaction():
                # Wallet lock first: concurrent requests from one owner serialize here.
                cur = await conn.execute('SELECT * FROM "CreditWallet" WHERE "userId" = %s FOR UPDATE', (owner,))
                if await cur.fetchone() is None:
                    raise ApiError(401, "UNAUTHENTICATED")
                cur = await conn.execute(
                    'SELECT * FROM "ImageJob" WHERE "userId" = %s AND "idempotencyKey" = %s', (owner, idempotency_key)
                )
                existing = await cur.fetchone()
                if existing is not None:
                    if existing["requestHash"] != request_hash:
                        raise ApiError(409, "IDEMPOTENCY_CONFLICT")
                    return self._payload(existing)
                if body.filter_type not in self.executor.available_filters():
                    raise ApiError(503, "FILTER_UNAVAILABLE")
                cur = await conn.execute(
                    'SELECT a.*, c."withdrawnAt", c."policyVersion" FROM "UploadAsset" a '
                    'JOIN "ConsentReceipt" c ON c.id = a."consentReceiptId" '
                    'WHERE a.id = %s AND a."userId" = %s FOR SHARE OF a',
                    (body.asset_id, owner),
                )
                asset = await cur.fetchone()
                if asset is None or asset["finalizedAt"] is None:
                    raise not_found("ASSET_NOT_FOUND")
                if asset["purgedAt"] is not None or _utc(asset["expiresAt"]) <= datetime.now(timezone.utc):
                    raise ApiError(410, "ASSET_EXPIRED")
                if asset["withdrawnAt"] is not None:
                    raise ApiError(403, "CONSENT_REQUIRED")
                cur = await conn.execute(
                    'SELECT ordinal FROM "AssetFace" WHERE id = %s AND "assetId" = %s AND "userId" = %s',
                    (body.face_id, body.asset_id, owner),
                )
                if await cur.fetchone() is None:
                    raise not_found("FACE_NOT_FOUND")
                cur = await conn.execute(
                    'SELECT count(*) AS n FROM "ImageJob" WHERE "userId" = %s AND status IN '
                    "('QUEUED','RUNNING','CANCEL_REQUESTED') AND \"tombstonedAt\" IS NULL",
                    (owner,),
                )
                if (await cur.fetchone())["n"] >= s.max_pending_jobs:
                    raise ApiError(429, "ADMISSION_LIMIT")
                cur = await conn.execute(
                    'UPDATE "CreditWallet" SET reserved = reserved + %s, version = version + 1 '
                    'WHERE "userId" = %s AND balance - reserved >= %s RETURNING "userId"',
                    (units, owner, units),
                )
                if await cur.fetchone() is None:
                    raise ApiError(402, "CREDIT_REQUIRED")
                job_id = uuid4()
                cur = await conn.execute(
                    'INSERT INTO "ImageJob"(id, "userId", "assetId", "faceId", "filterType", intensity, '
                    '"preserveBackground", parameters, "sourceRevision", "candidateRevision", "idempotencyKey", '
                    '"requestHash", "reservedUnits", "expiresAt") '
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                    (
                        job_id,
                        owner,
                        body.asset_id,
                        body.face_id,
                        body.filter_type,
                        body.intensity,
                        body.preserve_background,
                        Jsonb(body.options.model_dump(mode="json")),
                        body.source_revision,
                        body.candidate_revision,
                        idempotency_key,
                        request_hash,
                        units,
                        asset["expiresAt"],
                    ),
                )
                job = await cur.fetchone()
                await ledger.reserve(conn, owner, job_id, units)
                await conn.execute(
                    'INSERT INTO "OutboxEvent"(id, "aggregateId", "eventType", payload) VALUES (%s, %s, %s, %s)',
                    (uuid4(), job_id, "job.dispatch", Jsonb({"job_id": str(job_id)})),
                )
                await conn.execute(
                    'INSERT INTO "AuditLog"(id, "userId", "jobId", action, "requestId", "safeMetadata") '
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (uuid4(), owner, job_id, "job.created", uuid4(), Jsonb({})),
                )
        if self.on_job_created is not None:
            self.on_job_created(job_id)
        return self._payload(job)

    async def _snapshot(self, owner: UUID, job_id: UUID) -> JobPayload:
        async with self.pool.connection() as conn:
            return self._payload(await self._job(conn, owner, job_id))

    async def status(self, owner: UUID, job_id: UUID, wait_seconds: int, after_revision: int) -> JobPayload:
        snap = await self._snapshot(owner, job_id)
        if wait_seconds == 0 or snap.event_revision > after_revision or snap.status in TERMINAL_WIRE:
            return snap
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        # No connection is held while waiting; each check borrows one briefly.
        with self.events.subscribe(job_id) as changed:
            while True:
                changed.clear()
                snap = await self._snapshot(owner, job_id)
                if snap.event_revision > after_revision or snap.status in TERMINAL_WIRE:
                    return snap
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return snap
                try:
                    await asyncio.wait_for(changed.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    return await self._snapshot(owner, job_id)

    async def _tombstone(self, conn, job) -> None:
        """Revoke a job (row already locked): cancel live work, release its reservation, schedule purge."""
        live = job["status"] in LIVE
        if live:
            await ledger.release(conn, job["userId"], job["id"], job["reservedUnits"])
        await conn.execute(
            'UPDATE "ImageJob" SET "tombstonedAt" = COALESCE("tombstonedAt", now()), '
            '"deleteRequestedAt" = COALESCE("deleteRequestedAt", now()), "nextPurgeAt" = now(), '
            "status = CASE WHEN status IN ('QUEUED','RUNNING','CANCEL_REQUESTED') THEN 'CANCELED'::\"JobStatus\" "
            'ELSE status END, "completedAt" = COALESCE("completedAt", now()), "leaseExpiresAt" = NULL, '
            '"eventRevision" = "eventRevision" + 1 WHERE id = %s',
            (job["id"],),
        )

    async def cancel(self, owner: UUID, job_id: UUID) -> JobPayload:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                job = await self._job(conn, owner, job_id, lock=True)
                if job["status"] == "QUEUED":
                    await ledger.release(conn, owner, job_id, job["reservedUnits"])
                    cur = await conn.execute(
                        'UPDATE "ImageJob" SET status = \'CANCELED\', "completedAt" = now(), '
                        '"eventRevision" = "eventRevision" + 1 WHERE id = %s RETURNING *',
                        (job_id,),
                    )
                    job = await cur.fetchone()
                elif job["status"] == "RUNNING":
                    # The worker's lease heartbeat and conditional attach observe this and release.
                    cur = await conn.execute(
                        "UPDATE \"ImageJob\" SET status = 'CANCEL_REQUESTED', "
                        '"eventRevision" = "eventRevision" + 1 WHERE id = %s RETURNING *',
                        (job_id,),
                    )
                    job = await cur.fetchone()
            return self._payload(job)

    async def delete(self, owner: UUID, job_id: UUID) -> DeletionReceipt:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                job = await self._job(conn, owner, job_id, lock=True)
                if job["tombstonedAt"] is None or job["deleteRequestedAt"] is None:
                    await self._tombstone(conn, job)
                    # Purge the source too unless another live, unrevoked job still needs it.
                    await conn.execute(
                        'UPDATE "UploadAsset" a SET "expiresAt" = LEAST(a."expiresAt", now()), "nextPurgeAt" = now() '
                        'WHERE a.id = %s AND a."purgedAt" IS NULL AND NOT EXISTS (SELECT 1 FROM "ImageJob" j '
                        'WHERE j."assetId" = a.id AND j.id <> %s AND j."tombstonedAt" IS NULL)',
                        (job["assetId"], job_id),
                    )
                    job = await self._job(conn, owner, job_id)
        if job["purgedAt"] is not None:
            state = "complete"
        elif job["purgeAttemptCount"] >= 3:
            state = "partial_failure"
        elif job["purgeAttemptCount"] > 0:
            state = "deleting"
        else:
            state = "requested"
        return DeletionReceipt(job_id=job_id, status=state, requested_at=_utc(job["deleteRequestedAt"]))

    # ------------------------------------------------------------------ media gateway
    async def media(self, token: str) -> bytes:
        claim = media.verify(self.settings.media_token_secret, token)
        if claim is None:
            raise not_found("MEDIA_NOT_FOUND")
        if claim.expires_at <= int(time.time()):
            raise ApiError(410, "MEDIA_EXPIRED")
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                'SELECT * FROM "ImageJob" WHERE id = %s AND "userId" = %s', (claim.job_id, claim.owner)
            )
            job = await cur.fetchone()
        now = datetime.now(timezone.utc)
        if (
            job is None
            or job["status"] != "SUCCEEDED"
            or job["fence"] != claim.fence
            or job["tombstonedAt"] is not None
            or job["purgedAt"] is not None
            or job["resultObjectKey"] is None
            or _utc(job["resultExpiresAt"]) <= now
            or _utc(job["expiresAt"]) <= now
        ):
            raise ApiError(410, "MEDIA_EXPIRED")
        try:
            data, _ = await self.store.read_limited(job["resultObjectKey"], 64 * 1024 * 1024)
        except StorageError:
            raise ApiError(410, "MEDIA_EXPIRED") from None
        return data
