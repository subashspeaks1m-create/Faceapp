"""Credit ledger transitions. Each helper runs inside the caller's transaction, after the job row is locked.

The ledger row is inserted first with ON CONFLICT DO NOTHING; the wallet only moves when
that insert succeeded, so a replayed settlement or release can never move credits twice.
"""

from __future__ import annotations
from uuid import UUID, uuid4


async def _ledger(conn, user_id: UUID, job_id: UUID, kind: str, amount: int, units: int) -> bool:
    cur = await conn.execute(
        'INSERT INTO "CreditTransaction"(id, "userId", "jobId", kind, amount, units, "deduplicationKey") '
        "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
        (uuid4(), user_id, job_id, kind, amount, units, f"{job_id}:{kind}"),
    )
    return await cur.fetchone() is not None


async def reserve(conn, user_id: UUID, job_id: UUID, units: int) -> None:
    await _ledger(conn, user_id, job_id, "RESERVE", 0, units)


async def _closed(conn, job_id: UUID) -> bool:
    cur = await conn.execute(
        "SELECT 1 FROM \"CreditTransaction\" WHERE \"jobId\" = %s AND kind IN ('SETTLE', 'RELEASE')", (job_id,)
    )
    return await cur.fetchone() is not None


async def release(conn, user_id: UUID, job_id: UUID, units: int) -> bool:
    if await _closed(conn, job_id) or not await _ledger(conn, user_id, job_id, "RELEASE", 0, units):
        return False
    await conn.execute(
        'UPDATE "CreditWallet" SET reserved = reserved - %s, version = version + 1 WHERE "userId" = %s',
        (units, user_id),
    )
    return True


async def settle(conn, user_id: UUID, job_id: UUID, units: int) -> bool:
    if await _closed(conn, job_id) or not await _ledger(conn, user_id, job_id, "SETTLE", -units, units):
        return False
    await conn.execute(
        'UPDATE "CreditWallet" SET balance = balance - %s, reserved = reserved - %s, version = version + 1 '
        'WHERE "userId" = %s',
        (units, units, user_id),
    )
    return True


async def grant(conn, user_id: UUID, units: int, deduplication_key: str) -> bool:
    cur = await conn.execute(
        'INSERT INTO "CreditTransaction"(id, "userId", kind, amount, units, "deduplicationKey") '
        "VALUES (%s, %s, 'GRANT', %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
        (uuid4(), user_id, units, units, deduplication_key),
    )
    if await cur.fetchone() is None:
        return False
    await conn.execute(
        'UPDATE "CreditWallet" SET balance = balance + %s, version = version + 1 WHERE "userId" = %s',
        (units, user_id),
    )
    return True
