"""Integration tests for the PostgreSQL/S3 runtime against real services.

Requires PORTRAITLAB_TEST_DATABASE_URL (a role allowed to CREATE DATABASE) and
PORTRAITLAB_TEST_S3_ENDPOINT/ACCESS_KEY/SECRET_KEY. Without them every test is
skipped (reported as skipped, never as passed).

The face detector and executor here are TEST FIXTURES: the detector reports one
fixed box and the executor inverts pixels. They exercise the job/credit/privacy
lifecycle only and say nothing about model quality.
"""

import asyncio
import hashlib
import importlib.util
import io
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from uuid import UUID, uuid4

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "packages/shared-types"))
sys.path.insert(0, str(R / "apps/api-server"))

DB_ADMIN = os.environ.get("PORTRAITLAB_TEST_DATABASE_URL")
S3_ENDPOINT = os.environ.get("PORTRAITLAB_TEST_S3_ENDPOINT")
S3_KEY = os.environ.get("PORTRAITLAB_TEST_S3_ACCESS_KEY", "")
S3_SECRET = os.environ.get("PORTRAITLAB_TEST_S3_SECRET_KEY", "")
ENABLED = bool(DB_ADMIN and S3_ENDPOINT)

if ENABLED:
    import httpx
    import jwt
    import psycopg
    from PIL import Image
    from portraitlab import media
    from portraitlab.auth import JwtVerifier
    from portraitlab.config import AuthConfig, Settings, StorageConfig
    from portraitlab.db import JobEvents, migrate, open_pool
    from portraitlab.inference import ExecutionFailed, FaceBox
    from portraitlab.purge import PurgeDaemon
    from portraitlab.runtime import PostgresRuntime
    from portraitlab.storage import ObjectStore
    from portraitlab.worker import JobWorker, OutboxRelay, Reconciler

    spec = importlib.util.spec_from_file_location("api_for_integration", R / "apps/api-server/main.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)

DEV_SECRET = "integration-test-secret-not-for-production-use"
ISS, AUD = "https://auth.test.invalid/", "portraitlab-test"


def token(sub: str, **overrides) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": ISS, "aud": AUD, "iat": now, "exp": now + 600, **overrides}
    return jwt.encode(claims, DEV_SECRET, algorithm="HS256")


def portrait_jpeg(width=40, height=20, orientation=6) -> bytes:
    """Synthetic image with EXIF orientation and GPS tags that normalization must apply/strip."""
    img = Image.new("RGB", (width, height), (200, 120, 90))
    for x in range(width // 2):
        img.putpixel((x, 0), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = orientation
    exif[0x8825] = {1: "N", 2: (51.0, 30.0, 0.0)}
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif.tobytes(), quality=95)
    return out.getvalue()


class FixtureDetector:
    def detect(self, rgb):
        w, h = rgb.size
        return [
            FaceBox(
                (w * 0.2, h * 0.2, w * 0.8, h * 0.8),
                ((0.3, 0.4), (0.7, 0.4), (0.5, 0.55), (0.35, 0.7), (0.65, 0.7)),
                0.99,
            )
        ]


class FixtureExecutor:
    """Inverts pixels. Optional gates block selected calls so tests can interleave races."""

    def __init__(self):
        self.gates: list[threading.Event] = []
        self.fail_code: str | None = None
        self.calls = 0

    def available_filters(self):
        return frozenset({"age_50s", "hair_color"})

    def run(self, source_png, request, canceled):
        self.calls += 1
        if self.gates:
            gate = self.gates.pop(0)
            gate.wait(10)
        if self.fail_code:
            raise ExecutionFailed(self.fail_code)
        img = Image.open(io.BytesIO(source_png)).convert("RGB")
        out = io.BytesIO()
        Image.eval(img, lambda v: 255 - v).save(out, format="PNG")
        return out.getvalue()


@unittest.skipUnless(ENABLED, "PORTRAITLAB_TEST_DATABASE_URL / PORTRAITLAB_TEST_S3_ENDPOINT not configured")
class RuntimeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_name = f"pl_test_{uuid4().hex[:12]}"
        with psycopg.connect(DB_ADMIN, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{cls.db_name}"')
        base = DB_ADMIN.rsplit("/", 1)[0]
        cls.db_url = f"{base}/{cls.db_name}"
        cls.applied = migrate(cls.db_url)
        cls.bucket = f"pl-test-{uuid4().hex[:12]}"
        cls.settings = Settings(
            environment="test",
            database_url=cls.db_url,
            auth=AuthConfig(issuer=ISS, audience=AUD, algorithms=("HS256",), dev_hmac_secret=DEV_SECRET),
            storage=StorageConfig(
                bucket=cls.bucket,
                internal_endpoint=S3_ENDPOINT,
                public_endpoint=S3_ENDPOINT,
                access_key=S3_KEY,
                secret_key=S3_SECRET,
            ),
            media_token_secret=b"m" * 32,
            worker_lease_seconds=30,
        )
        ObjectStore(cls.settings.storage).ensure_bucket_sync()

    @classmethod
    def tearDownClass(cls):
        store = ObjectStore(cls.settings.storage)
        asyncio.run(store.delete_prefix(""))
        store._client.delete_bucket(Bucket=cls.bucket)
        with psycopg.connect(DB_ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{cls.db_name}" WITH (FORCE)')

    async def asyncSetUp(self):
        self.pool = open_pool(self.db_url, max_size=6)
        await self.pool.open(wait=True)
        self.events = JobEvents(self.db_url)
        await self.events.start()
        self.store = ObjectStore(self.settings.storage)
        self.executor = FixtureExecutor()
        self.runtime = PostgresRuntime(
            self.settings,
            self.pool,
            self.store,
            self.events,
            JwtVerifier(self.settings.auth),
            FixtureDetector(),
            self.executor,
        )
        api.app.state.runtime = self.runtime
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://api.test")
        self.worker = JobWorker(self.settings, self.pool, self.store, self.executor)
        self.purge = PurgeDaemon(self.settings, self.pool, self.store)
        self.reconciler = Reconciler(self.settings, self.pool)
        self.sub = f"user-{uuid4().hex}"
        self.auth = {"Authorization": f"Bearer {token(self.sub)}"}

    async def asyncTearDown(self):
        api.app.state.runtime = None
        await self.client.aclose()
        await self.events.stop()
        await self.pool.close()

    # ---------------------------------------------------------------- helpers
    async def sql(self, query, params=()):
        async with self.pool.connection() as conn:
            cur = await conn.execute(query, params)
            return await cur.fetchall() if cur.description else None

    async def grant(self, units, sub=None):
        await self.client.post("/api/v1/consents", headers=self.auth, json=self.consent_body())  # provisions user
        rows = await self.sql('SELECT id FROM "User" WHERE "externalSubject" = %s', (sub or self.sub,))
        from portraitlab import ledger

        async with self.pool.connection() as conn, conn.transaction():
            await ledger.grant(conn, rows[0]["id"], units, f"test-{uuid4()}")
        return rows[0]["id"]

    async def wallet(self, user_id):
        return (await self.sql('SELECT balance, reserved FROM "CreditWallet" WHERE "userId" = %s', (user_id,)))[0]

    def consent_body(self):
        return {
            "policy_version": self.settings.consent_policy_version,
            "purpose": "portrait_editing",
            "processor_region": "eu",
        }

    async def consent(self, headers=None):
        r = await self.client.post("/api/v1/consents", headers=headers or self.auth, json=self.consent_body())
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["consent_receipt_id"]

    async def put_bytes(self, grant, data, **header_overrides):
        headers = {**grant["required_headers"], **header_overrides}
        async with httpx.AsyncClient() as raw:
            return await raw.put(grant["upload_url"], content=data, headers=headers)

    async def upload(self, data=None, mime="image/jpeg", declared=None):
        data = data if data is not None else portrait_jpeg()
        declared = declared if declared is not None else data
        consent_id = await self.consent()
        body = {
            "mime_type": mime,
            "byte_length": len(declared),
            "checksum_sha256": hashlib.sha256(declared).hexdigest(),
            "consent_receipt_id": consent_id,
        }
        r = await self.client.post("/api/v1/faces/upload-url", headers=self.auth, json=body)
        self.assertEqual(r.status_code, 201, r.text)
        grant = r.json()
        put = await self.put_bytes(grant, data)
        r = await self.client.post(
            f"/api/v1/faces/uploads/{grant['asset_id']}/complete",
            headers=self.auth,
            json={"checksum_sha256": body["checksum_sha256"]},
        )
        return grant, put, r

    async def ready_asset(self):
        grant, put, r = await self.upload()
        self.assertEqual(put.status_code, 200)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    async def submit(self, receipt, key=None, **changes):
        body = {
            "asset_id": receipt["asset_id"],
            "face_id": receipt["faces"][0],
            "filter_type": "age_50s",
            "intensity": 0.4,
            "source_revision": 0,
            "candidate_revision": 1,
            **changes,
        }
        return await self.client.post(
            "/api/v1/faces/transform", headers={**self.auth, "Idempotency-Key": key or uuid4().hex}, json=body
        )

    async def objects(self, prefix):
        def _list():
            return self.store._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix).get("KeyCount", 0)

        return await asyncio.to_thread(_list)

    # ---------------------------------------------------------------- migrations and auth
    async def test_migrations_applied_and_constraints_active(self):
        self.assertEqual(self.applied, ["0001_prisma_baseline.sql", "0002_constraints.sql", "0003_runtime.sql"])
        self.assertEqual(migrate(self.db_url), [])
        user = await self.grant(0)
        with self.assertRaises(psycopg.errors.CheckViolation):
            await self.sql('UPDATE "CreditWallet" SET reserved = 5 WHERE "userId" = %s', (user,))

    async def test_jwt_signature_issuer_audience_expiry_enforced(self):
        bad = [
            jwt.encode(
                {"sub": "x", "iss": ISS, "aud": AUD, "iat": 0, "exp": 2**40},
                "wrong-secret-wrong-secret-123456",
                algorithm="HS256",
            ),
            token("x", iss="https://other.invalid/"),
            token("x", aud="someone-else"),
            token("x", exp=int(time.time()) - 3600),
            jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "iat": 0, "exp": 2**40}, None, algorithm="none"),
            "not-a-jwt",
        ]
        for value in bad:
            r = await self.client.post(
                "/api/v1/consents", headers={"Authorization": f"Bearer {value}"}, json=self.consent_body()
            )
            self.assertEqual(r.status_code, 401, value[:20])
            self.assertEqual(r.headers["cache-control"], "no-store")
        r = await self.client.post("/api/v1/consents", json=self.consent_body())
        self.assertEqual(r.status_code, 401)

    # ---------------------------------------------------------------- uploads
    async def test_upload_normalizes_orientation_and_strips_metadata(self):
        receipt = await self.ready_asset()
        self.assertEqual((receipt["normalized_width"], receipt["normalized_height"]), (20, 40))  # EXIF 6 applied
        self.assertEqual(len(receipt["faces"]), 1)
        rows = await self.sql('SELECT "objectPrefix" FROM "UploadAsset" WHERE id = %s', (receipt["asset_id"],))
        prefix = rows[0]["objectPrefix"]
        self.assertEqual(await self.objects(prefix + "original"), 0)  # Raw upload with EXIF removed.
        data, _ = await self.store.read_limited(prefix + "normalized.png", 10**7)
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "PNG")
        self.assertFalse(img.getexif())
        self.assertNotIn("exif", img.info)
        self.assertNotIn("icc_profile", img.info)

    async def test_upload_body_must_match_declared_checksum(self):
        good = portrait_jpeg()
        grant, put, r = await self.upload(data=portrait_jpeg(orientation=1), declared=good)
        # Store accepted the bytes (it only checks the signed header); finalization must not.
        self.assertIn(r.status_code, (422,))
        self.assertIn(r.json()["code"], ("UPLOAD_CHECKSUM_FAILED", "UPLOAD_SIZE_MISMATCH"))
        self.assertEqual(await self.objects(f"assets/{grant['asset_id']}/"), 0)

    async def test_upload_type_mismatch_and_pixel_bomb_rejected(self):
        html = b"<html><script>alert(1)</script></html>"
        grant, put, r = await self.upload(data=html, mime="image/png")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["code"], "UPLOAD_TYPE_MISMATCH")
        bomb = io.BytesIO()
        Image.new("L", (6000, 5000)).save(bomb, format="PNG")  # 30 MP > 24 MP limit, small file.
        grant, put, r = await self.upload(data=bomb.getvalue(), mime="image/png")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["code"], "IMAGE_TOO_LARGE")

    async def test_signed_headers_cannot_be_changed(self):
        data = portrait_jpeg()
        consent_id = await self.consent()
        body = {
            "mime_type": "image/jpeg",
            "byte_length": len(data),
            "checksum_sha256": hashlib.sha256(data).hexdigest(),
            "consent_receipt_id": consent_id,
        }
        grant = (await self.client.post("/api/v1/faces/upload-url", headers=self.auth, json=body)).json()
        self.assertTrue(grant["upload_url"].startswith(S3_ENDPOINT))
        self.assertEqual((await self.put_bytes(grant, data, **{"Content-Type": "text/html"})).status_code, 403)

    async def test_assets_and_consents_are_owner_bound(self):
        receipt = await self.ready_asset()
        other = {"Authorization": f"Bearer {token('intruder-' + uuid4().hex)}"}
        r = await self.client.post(
            f"/api/v1/faces/uploads/{receipt['asset_id']}/complete", headers=other, json={"checksum_sha256": "0" * 64}
        )
        self.assertEqual(r.status_code, 404)
        my_consent = await self.consent()
        body = {
            "mime_type": "image/jpeg",
            "byte_length": 10,
            "checksum_sha256": "a" * 64,
            "consent_receipt_id": my_consent,
        }
        self.assertEqual(
            (await self.client.post("/api/v1/faces/upload-url", headers=other, json=body)).status_code, 404
        )
        await self.grant(5)
        r = await self.client.post(
            "/api/v1/faces/transform",
            headers={**other, "Idempotency-Key": uuid4().hex},
            json={
                "asset_id": receipt["asset_id"],
                "face_id": receipt["faces"][0],
                "filter_type": "age_50s",
                "intensity": 0.4,
                "source_revision": 0,
                "candidate_revision": 1,
            },
        )
        self.assertIn(r.status_code, (402, 404))  # Intruder has no credits; with credits it is 404 below.
        intruder = (await self.sql('SELECT id FROM "User" WHERE "externalSubject" LIKE %s', ("intruder-%",)))[0]["id"]
        from portraitlab import ledger

        async with self.pool.connection() as conn, conn.transaction():
            await ledger.grant(conn, intruder, 3, f"t-{uuid4()}")
        r = await self.client.post(
            "/api/v1/faces/transform",
            headers={**other, "Idempotency-Key": uuid4().hex},
            json={
                "asset_id": receipt["asset_id"],
                "face_id": receipt["faces"][0],
                "filter_type": "age_50s",
                "intensity": 0.4,
                "source_revision": 0,
                "candidate_revision": 1,
            },
        )
        self.assertEqual(r.status_code, 404)

    # ---------------------------------------------------------------- transform admission and credits
    async def test_unavailable_filter_and_missing_credits(self):
        user = await self.grant(0)
        receipt = await self.ready_asset()
        r = await self.submit(receipt, filter_type="laugh")
        self.assertEqual((r.status_code, r.json()["code"]), (503, "FILTER_UNAVAILABLE"))
        r = await self.submit(receipt)
        self.assertEqual((r.status_code, r.json()["code"]), (402, "CREDIT_REQUIRED"))
        self.assertEqual(dict(await self.wallet(user)), {"balance": 0, "reserved": 0})

    async def test_idempotent_replay_and_conflict(self):
        user = await self.grant(3)
        receipt = await self.ready_asset()
        first = await self.submit(receipt, key="k" * 20)
        again = await self.submit(receipt, key="k" * 20)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(again.json()["job_id"], first.json()["job_id"])
        self.assertEqual(dict(await self.wallet(user)), {"balance": 3, "reserved": 1})
        conflict = await self.submit(receipt, key="k" * 20, intensity=0.9)
        self.assertEqual((conflict.status_code, conflict.json()["code"]), (409, "IDEMPOTENCY_CONFLICT"))
        rows = await self.sql(
            'SELECT count(*) AS n FROM "OutboxEvent" WHERE "aggregateId" = %s', (first.json()["job_id"],)
        )
        self.assertEqual(rows[0]["n"], 1)

    async def test_concurrent_same_key_creates_one_job(self):
        user = await self.grant(5)
        receipt = await self.ready_asset()
        results = await asyncio.gather(*(self.submit(receipt, key="same-key-123456789") for _ in range(5)))
        self.assertEqual({r.status_code for r in results}, {202})
        self.assertEqual(len({r.json()["job_id"] for r in results}), 1)
        self.assertEqual((await self.wallet(user))["reserved"], 1)

    async def test_pending_admission_limit(self):
        await self.grant(5)
        receipt = await self.ready_asset()
        self.assertEqual((await self.submit(receipt)).status_code, 202)
        self.assertEqual((await self.submit(receipt)).status_code, 202)
        r = await self.submit(receipt)
        self.assertEqual((r.status_code, r.json()["code"]), (429, "ADMISSION_LIMIT"))

    # ---------------------------------------------------------------- execution, settlement and redelivery
    async def test_success_settles_once_under_redelivery_and_media_gateway(self):
        user = await self.grant(2)
        receipt = await self.ready_asset()
        job = (await self.submit(receipt)).json()
        published = []
        await OutboxRelay(self.pool, published.append).run_once(limit=1000)
        self.assertEqual(published.count(UUID(job["job_id"])), 1)
        await OutboxRelay(self.pool, published.append).run_once(limit=1000)
        self.assertEqual(published.count(UUID(job["job_id"])), 1)  # Marked dispatched; not re-sent.
        self.assertEqual(await self.worker.process(UUID(job["job_id"])), "succeeded")
        self.assertEqual(await self.worker.process(UUID(job["job_id"])), "not_claimable")  # Redelivery.
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})
        kinds = await self.sql(
            'SELECT kind FROM "CreditTransaction" WHERE "jobId" = %s ORDER BY kind', (job["job_id"],)
        )
        self.assertEqual([k["kind"] for k in kinds], ["RESERVE", "SETTLE"])
        status = (await self.client.get(f"/api/v1/faces/jobs/{job['job_id']}", headers=self.auth)).json()
        self.assertEqual(
            (status["status"], status["progress_source"], status["progress_percent"]), ("succeeded", "complete", 100.0)
        )
        r = await self.client.get(status["result_cdn_url"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["cache-control"], "no-store")
        out = Image.open(io.BytesIO(r.content))
        self.assertEqual(out.size, (20, 40))  # Source resolution preserved.
        tampered = status["result_cdn_url"][:-3] + ("AAA" if not status["result_cdn_url"].endswith("AAA") else "BBB")
        self.assertEqual((await self.client.get(tampered)).status_code, 404)
        expired = media.sign(
            self.settings.media_token_secret, media.MediaClaim(UUID(job["job_id"]), user, 1, int(time.time()) - 1)
        )
        self.assertEqual((await self.client.get(f"/api/v1/media/{expired}")).status_code, 410)

    async def test_failure_releases_reservation_once(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job = (await self.submit(receipt)).json()
        self.executor.fail_code = "MODEL_ERROR"
        self.assertEqual(await self.worker.process(UUID(job["job_id"])), "failed")
        await self.reconciler.run_once()
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})
        status = (await self.client.get(f"/api/v1/faces/jobs/{job['job_id']}", headers=self.auth)).json()
        self.assertEqual((status["status"], status["error"]["code"]), ("failed", "MODEL_ERROR"))

    async def test_dead_worker_lease_is_retried_and_stale_fence_cannot_attach(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job_id = UUID((await self.submit(receipt)).json()["job_id"])
        gate = threading.Event()
        self.executor.gates.append(gate)
        first = asyncio.create_task(self.worker.process(job_id))
        while self.executor.calls == 0:
            await asyncio.sleep(0.02)
        await self.sql(
            'UPDATE "ImageJob" SET "leaseExpiresAt" = now() - interval \'1 second\' WHERE id = %s', (job_id,)
        )
        self.assertEqual((await self.reconciler.run_once())["requeued"], 1)
        self.assertEqual(await self.worker.process(job_id), "succeeded")  # Second delivery, fence 2.
        gate.set()
        self.assertEqual(await first, "lost_before_write")
        self.assertEqual(await self.objects(f"jobs/{job_id}/f1/"), 0)
        self.assertEqual(dict(await self.wallet(user)), {"balance": 0, "reserved": 0})

    async def test_retries_exhausted_fail_and_release(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job_id = UUID((await self.submit(receipt)).json()["job_id"])
        await self.sql(
            'UPDATE "ImageJob" SET status = \'RUNNING\', "attemptCount" = 2, "leaseExpiresAt" = now() - interval \'1 second\' WHERE id = %s',
            (job_id,),
        )
        self.assertEqual((await self.reconciler.run_once())["failed"], 1)
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})

    # ---------------------------------------------------------------- cancellation and deletion races
    async def test_cancel_queued_releases_and_worker_skips(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job = (await self.submit(receipt)).json()
        r = await self.client.post(f"/api/v1/faces/jobs/{job['job_id']}/cancel", headers=self.auth)
        self.assertEqual((r.status_code, r.json()["status"]), (202, "canceled"))
        self.assertEqual(await self.worker.process(UUID(job["job_id"])), "not_claimable")
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})

    async def test_cancel_while_running_discards_output(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job_id = UUID((await self.submit(receipt)).json()["job_id"])
        gate = threading.Event()
        self.executor.gates.append(gate)
        task = asyncio.create_task(self.worker.process(job_id))
        while self.executor.calls == 0:
            await asyncio.sleep(0.02)
        r = await self.client.post(f"/api/v1/faces/jobs/{job_id}/cancel", headers=self.auth)
        self.assertEqual(r.json()["status"], "cancel_requested")
        gate.set()
        self.assertEqual(await task, "lost_before_write")
        status = (await self.client.get(f"/api/v1/faces/jobs/{job_id}", headers=self.auth)).json()
        self.assertEqual((status["status"], status["result_cdn_url"]), ("canceled", None))
        self.assertEqual(await self.objects(f"jobs/{job_id}/"), 0)
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})

    async def test_delete_concurrent_with_output_write_never_resurrects(self):
        user = await self.grant(1)
        receipt = await self.ready_asset()
        job_id = UUID((await self.submit(receipt)).json()["job_id"])
        job = (await self.sql('SELECT * FROM "ImageJob" WHERE id = %s', (job_id,)))[0]
        claimed = await self.worker._claim(job_id)
        # Simulate the worker having written its output just as deletion lands.
        key = f"jobs/{job_id}/f{claimed['fence']}/result.png"
        await self.store.put(key, b"late-output", "image/png")
        r = await self.client.delete(f"/api/v1/faces/jobs/{job_id}/data", headers=self.auth)
        self.assertEqual((r.status_code, r.json()["status"]), (202, "requested"))
        outcome = await self.worker._attach(job, claimed["fence"], key, f"jobs/{job_id}/f{claimed['fence']}/")
        self.assertEqual(outcome, "late_output_deleted")
        counts = await self.purge.run_once()
        self.assertGreaterEqual(counts["jobs"], 1)
        self.assertEqual(await self.objects(f"jobs/{job_id}/"), 0)
        self.assertEqual(await self.objects(f"assets/{receipt['asset_id']}/"), 0)  # Source purged too.
        status = (await self.client.get(f"/api/v1/faces/jobs/{job_id}", headers=self.auth)).json()
        self.assertEqual(status["status"], "purged")
        r = await self.client.delete(f"/api/v1/faces/jobs/{job_id}/data", headers=self.auth)
        self.assertEqual(r.json()["status"], "complete")
        self.assertEqual(dict(await self.wallet(user)), {"balance": 1, "reserved": 0})
        faces = await self.sql('SELECT count(*) AS n FROM "AssetFace" WHERE "assetId" = %s', (receipt["asset_id"],))
        self.assertEqual(faces[0]["n"], 0)

    async def test_media_revoked_after_delete(self):
        await self.grant(1)
        receipt = await self.ready_asset()
        job_id = (await self.submit(receipt)).json()["job_id"]
        await self.worker.process(UUID(job_id))
        url = (await self.client.get(f"/api/v1/faces/jobs/{job_id}", headers=self.auth)).json()["result_cdn_url"]
        await self.client.delete(f"/api/v1/faces/jobs/{job_id}/data", headers=self.auth)
        self.assertEqual((await self.client.get(url)).status_code, 410)  # Revoked before bytes are gone.

    async def test_consent_withdrawal_revokes_assets(self):
        await self.grant(2)
        receipt = await self.ready_asset()
        consent_id = (
            await self.sql('SELECT "consentReceiptId" AS c FROM "UploadAsset" WHERE id = %s', (receipt["asset_id"],))
        )[0]["c"]
        r = await self.client.delete(f"/api/v1/consents/{consent_id}", headers=self.auth)
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()["withdrawn_at"])
        r = await self.submit(receipt)
        self.assertIn(r.json()["code"], ("ASSET_EXPIRED", "CONSENT_REQUIRED"))
        await self.purge.run_once()
        self.assertEqual(await self.objects(f"assets/{receipt['asset_id']}/"), 0)

    # ---------------------------------------------------------------- purge lifecycle
    async def test_orphan_upload_and_expired_asset_purged(self):
        data = portrait_jpeg()
        consent_id = await self.consent()
        body = {
            "mime_type": "image/jpeg",
            "byte_length": len(data),
            "checksum_sha256": hashlib.sha256(data).hexdigest(),
            "consent_receipt_id": consent_id,
        }
        grant = (await self.client.post("/api/v1/faces/upload-url", headers=self.auth, json=body)).json()
        await self.put_bytes(grant, data)
        await self.sql(
            'UPDATE "UploadAsset" SET "createdAt" = now() - interval \'3 minutes\' WHERE id = %s', (grant["asset_id"],)
        )
        receipt = await self.ready_asset()
        await self.sql(
            'UPDATE "UploadAsset" SET "expiresAt" = now() - interval \'1 second\' WHERE id = %s', (receipt["asset_id"],)
        )
        counts = await self.purge.run_once()
        self.assertGreaterEqual(counts["assets"], 2)
        self.assertEqual(await self.objects(f"assets/{grant['asset_id']}/"), 0)
        self.assertEqual(await self.objects(f"assets/{receipt['asset_id']}/"), 0)
        rows = await self.sql(
            'SELECT "objectPrefix", "checksumSha256" FROM "UploadAsset" WHERE id = %s', (receipt["asset_id"],)
        )
        self.assertEqual(dict(rows[0]), {"objectPrefix": None, "checksumSha256": None})
        r = await self.client.post(
            f"/api/v1/faces/uploads/{receipt['asset_id']}/complete",
            headers=self.auth,
            json={"checksum_sha256": "0" * 64},
        )
        self.assertEqual(r.status_code, 410)

    async def test_result_window_expiry_purges_output(self):
        await self.grant(1)
        receipt = await self.ready_asset()
        job_id = (await self.submit(receipt)).json()["job_id"]
        await self.worker.process(UUID(job_id))
        await self.sql(
            'UPDATE "ImageJob" SET "resultExpiresAt" = now() - interval \'1 second\' WHERE id = %s', (job_id,)
        )
        await self.purge.run_once()
        self.assertEqual(await self.objects(f"jobs/{job_id}/"), 0)
        status = (await self.client.get(f"/api/v1/faces/jobs/{job_id}", headers=self.auth)).json()
        self.assertEqual((status["status"], status["result_cdn_url"]), ("purged", None))

    async def test_inventory_sweep_removes_unregistered_prefix(self):
        stray = uuid4()
        await self.store.put(f"jobs/{stray}/f1/result.png", b"x", "image/png")
        self.assertGreaterEqual(await self.purge.sweep_inventory(), 1)
        self.assertEqual(await self.objects(f"jobs/{stray}/"), 0)

    # ---------------------------------------------------------------- long polling
    async def test_long_poll_wakes_on_change_without_holding_connections(self):
        await self.grant(1)
        receipt = await self.ready_asset()
        job = (await self.submit(receipt)).json()
        url = f"/api/v1/faces/jobs/{job['job_id']}?wait_seconds=10&after_revision={job['event_revision']}"
        started = time.monotonic()
        poll = asyncio.create_task(self.client.get(url, headers=self.auth))
        await asyncio.sleep(0.5)
        stats = self.pool.get_stats()
        self.assertEqual(stats["pool_size"] - stats.get("pool_available", 0), 0)  # Nothing checked out while waiting.
        await self.client.post(f"/api/v1/faces/jobs/{job['job_id']}/cancel", headers=self.auth)
        r = await poll
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(r.json()["status"], "canceled")
        self.assertGreater(r.json()["event_revision"], job["event_revision"])

    async def test_long_poll_times_out_with_snapshot(self):
        await self.grant(1)
        receipt = await self.ready_asset()
        job = (await self.submit(receipt)).json()
        started = time.monotonic()
        r = await self.client.get(
            f"/api/v1/faces/jobs/{job['job_id']}?wait_seconds=1&after_revision={job['event_revision']}",
            headers=self.auth,
        )
        self.assertGreaterEqual(time.monotonic() - started, 0.9)
        self.assertEqual((r.status_code, r.json()["status"], r.json()["progress_percent"]), (200, "queued", None))


if __name__ == "__main__":
    unittest.main()
