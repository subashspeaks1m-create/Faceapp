"""Service wiring and operator CLI.

python -m portraitlab.service migrate
python -m portraitlab.service daemons          # outbox relay + reconciler + purge loops
python -m portraitlab.service grant-credits SUBJECT UNITS KEY
python -m portraitlab.service dev-token SUBJECT  # development auth only
"""

from __future__ import annotations
import argparse
import asyncio
import logging
import time
from pathlib import Path
from uuid import uuid4
from .auth import JwtVerifier
from .config import Settings, load_settings
from .db import JobEvents, migrate, open_pool
from .inference import RegistryExecutor, detector_from_registry
from .purge import PurgeDaemon
from .runtime import PostgresRuntime
from .storage import ObjectStore
from .worker import OutboxRelay, Reconciler

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "model-registry.json"
FILTERS = ROOT / "assets/filters.json"
log = logging.getLogger("portraitlab.service")


async def build_runtime(settings: Settings, *, detector=None, executor=None, on_job_created=None):
    """Open pool/listener and return (runtime, closer). Detector/executor default to the approved registry."""
    pool = open_pool(settings.database_url)
    await pool.open(wait=True)
    events = JobEvents(settings.database_url)
    await events.start()
    store = ObjectStore(settings.storage)
    runtime = PostgresRuntime(
        settings,
        pool,
        store,
        events,
        JwtVerifier(settings.auth),
        detector if detector is not None else detector_from_registry(REGISTRY, ROOT),
        executor if executor is not None else RegistryExecutor(REGISTRY, FILTERS),
        on_job_created=on_job_created,
    )

    async def close():
        await events.stop()
        await pool.close()

    return runtime, close


async def run_daemons(settings: Settings, publish, *, interval: float = 5.0) -> None:
    pool = open_pool(settings.database_url, max_size=4)
    await pool.open(wait=True)
    store = ObjectStore(settings.storage)
    relay, reconciler, purge = (
        OutboxRelay(pool, publish),
        Reconciler(settings, pool),
        PurgeDaemon(settings, pool, store),
    )
    last_sweep = 0.0
    try:
        while True:
            for name, step in (
                ("relay", relay.run_once),
                ("reconcile", reconciler.run_once),
                ("purge", purge.run_once),
            ):
                try:
                    await step()
                except Exception:
                    log.exception("daemon step failed: %s", name)
            if time.monotonic() - last_sweep > 60:
                try:
                    await purge.sweep_inventory()
                except Exception:
                    log.exception("inventory sweep failed")
                last_sweep = time.monotonic()
            await asyncio.sleep(interval)
    finally:
        await pool.close()


async def _grant(settings: Settings, subject: str, units: int, key: str) -> bool:
    from . import ledger

    pool = open_pool(settings.database_url, max_size=1)
    await pool.open(wait=True)
    try:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute(
                'INSERT INTO "User"(id, "externalSubject") VALUES (%s, %s) ON CONFLICT ("externalSubject") DO NOTHING',
                (uuid4(), subject),
            )
            cur = await conn.execute('SELECT id FROM "User" WHERE "externalSubject" = %s', (subject,))
            user_id = (await cur.fetchone())["id"]
            await conn.execute('INSERT INTO "CreditWallet"("userId") VALUES (%s) ON CONFLICT DO NOTHING', (user_id,))
            await conn.execute('SELECT 1 FROM "CreditWallet" WHERE "userId" = %s FOR UPDATE', (user_id,))
            return await ledger.grant(conn, user_id, units, key)
    finally:
        await pool.close()


def dev_token(settings: Settings, subject: str, ttl: int = 3600) -> str:
    import jwt

    if settings.production or not settings.auth.dev_hmac_secret:
        raise SystemExit("dev-token is only available with JWT_DEV_HS256_SECRET outside production")
    now = int(time.time())
    claims = {"sub": subject, "iss": settings.auth.issuer, "aud": settings.auth.audience, "iat": now, "exp": now + ttl}
    return jwt.encode(claims, settings.auth.dev_hmac_secret, algorithm="HS256")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="portraitlab.service")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    sub.add_parser("ensure-bucket")
    sub.add_parser("daemons")
    g = sub.add_parser("grant-credits")
    g.add_argument("subject")
    g.add_argument("units", type=int)
    g.add_argument("deduplication_key")
    t = sub.add_parser("dev-token")
    t.add_argument("subject")
    args = parser.parse_args()
    settings = load_settings()
    if args.command == "migrate":
        print("applied:", migrate(settings.database_url) or "nothing")
    elif args.command == "ensure-bucket":
        ObjectStore(settings.storage).ensure_bucket_sync()
        print("bucket ready")
    elif args.command == "daemons":
        from .tasks import publish_job

        asyncio.run(run_daemons(settings, publish_job))
    elif args.command == "grant-credits":
        print(
            "granted"
            if asyncio.run(_grant(settings, args.subject, args.units, args.deduplication_key))
            else "duplicate"
        )
    elif args.command == "dev-token":
        print(dev_token(settings, args.subject))


if __name__ == "__main__":
    main()
