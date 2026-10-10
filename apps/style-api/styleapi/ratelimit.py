"""Generation quotas shared by every serverless instance.

Upstash Redis (REST) runs one Lua script per request that increments the per-client hourly, per-client
daily and global daily counters together and rolls all of them back if any is over its limit. When
Upstash cannot be reached the request is refused (fail closed); a paid call never runs unmetered.

Clients are identified by an HMAC of their IP address with a server-side salt, so raw IPs are never
stored in Redis.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from .config import Settings
from .errors import ApiError

# KEYS: counters. ARGV: [n, limit1..limitn, ttl1..ttln]. Returns {0, remaining...} or {index, retry_ttl}.
_RESERVE_LUA = """
local n = tonumber(ARGV[1])
local counts = {}
for i = 1, n do
  counts[i] = redis.call('INCR', KEYS[i])
  if counts[i] == 1 then redis.call('EXPIRE', KEYS[i], tonumber(ARGV[1 + n + i])) end
end
for i = 1, n do
  if counts[i] > tonumber(ARGV[1 + i]) then
    for j = 1, n do redis.call('DECR', KEYS[j]) end
    local ttl = redis.call('TTL', KEYS[i])
    return {i, ttl}
  end
end
local out = {0}
for i = 1, n do out[i + 1] = tonumber(ARGV[1 + i]) - counts[i] end
return out
"""


@dataclass(frozen=True)
class Quota:
    """Remaining generations in the tightest window for this client."""

    remaining: int
    limit: int
    window: str


@dataclass(frozen=True)
class _Window:
    name: str
    limit: int
    ttl: int
    key: str


class RateLimiter(Protocol):
    async def reserve(self, client_id: str) -> Quota: ...

    async def peek(self, client_id: str) -> Quota: ...


def client_id_from(ip: str, salt: str) -> str:
    return hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


def _windows(settings: Settings, client_id: str, now: float) -> list[_Window]:
    hour = int(now // 3600)
    day = int(now // 86400)
    return [
        _Window("hour", settings.limit_per_ip_hour, 3600, f"sl:ip:{client_id}:h:{hour}"),
        _Window("day", settings.limit_per_ip_day, 86400, f"sl:ip:{client_id}:d:{day}"),
        _Window("global", settings.limit_global_day, 86400, f"sl:global:d:{day}"),
    ]


def _tightest(windows: list[_Window], remaining: list[int]) -> Quota:
    # The global window is not the caller's own allowance; report it only when it is the binding one.
    idx = min(range(len(windows)), key=lambda i: remaining[i])
    return Quota(remaining=max(0, remaining[idx]), limit=windows[idx].limit, window=windows[idx].name)


class UpstashRateLimiter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _require(self) -> tuple[str, str]:
        s = self._settings
        if not s.upstash_url or s.upstash_token is None:
            raise ApiError("GENERATION_UNAVAILABLE")
        return s.upstash_url, s.upstash_token.get_secret_value()

    async def _post(self, path: str, body: list[object]) -> object:
        url, token = self._require()
        try:
            if self._client is not None:
                resp = await self._client.post(f"{url}{path}", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(f"{url}{path}", json=body, headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
        except httpx.HTTPError as e:
            raise ApiError("GENERATION_UNAVAILABLE") from e
        if resp.status_code != 200:
            raise ApiError("GENERATION_UNAVAILABLE")
        try:
            payload = resp.json()
        except ValueError as e:
            raise ApiError("GENERATION_UNAVAILABLE") from e
        if not isinstance(payload, dict) or "result" not in payload:
            raise ApiError("GENERATION_UNAVAILABLE")
        return payload["result"]

    async def reserve(self, client_id: str) -> Quota:
        ws = _windows(self._settings, client_id, time.time())
        n = len(ws)
        args: list[object] = ["EVAL", _RESERVE_LUA, str(n), *[w.key for w in ws], str(n), *[str(w.limit) for w in ws], *[str(w.ttl) for w in ws]]
        result = await self._post("", args)
        if not isinstance(result, list) or not result or not all(isinstance(x, int) for x in result):
            raise ApiError("GENERATION_UNAVAILABLE")
        if result[0] != 0:
            idx = result[0] - 1
            if not 0 <= idx < n or len(result) < 2:
                raise ApiError("GENERATION_UNAVAILABLE")
            retry = result[1] if result[1] > 0 else ws[idx].ttl
            if ws[idx].name == "global":
                raise ApiError("GENERATION_UNAVAILABLE", "Today's generation capacity has been used up. Try again tomorrow.", retry_after_seconds=retry)
            raise ApiError("RATE_LIMITED", retry_after_seconds=retry)
        if len(result) != n + 1:
            raise ApiError("GENERATION_UNAVAILABLE")
        return _tightest(ws, list(result[1:]))

    async def peek(self, client_id: str) -> Quota:
        ws = _windows(self._settings, client_id, time.time())
        result = await self._post("", ["MGET", *[w.key for w in ws]])
        if not isinstance(result, list) or len(result) != len(ws):
            raise ApiError("GENERATION_UNAVAILABLE")
        used = []
        for v in result:
            try:
                used.append(int(v) if v is not None else 0)
            except (TypeError, ValueError) as e:
                raise ApiError("GENERATION_UNAVAILABLE") from e
        return _tightest(ws, [w.limit - u for w, u in zip(ws, used, strict=True)])


class MemoryRateLimiter:
    """Single-process limiter for local development only. Config refuses it in production."""

    def __init__(self, settings: Settings) -> None:
        if settings.is_production:
            raise ApiError("GENERATION_UNAVAILABLE")
        self._settings = settings
        self._counts: dict[str, tuple[int, float]] = {}

    def _get(self, key: str, now: float) -> int:
        count, expires = self._counts.get(key, (0, 0.0))
        return count if expires > now else 0

    async def reserve(self, client_id: str) -> Quota:
        now = time.time()
        ws = _windows(self._settings, client_id, now)
        counts = [self._get(w.key, now) + 1 for w in ws]
        for w, c in zip(ws, counts, strict=True):
            if c > w.limit:
                code = "GENERATION_UNAVAILABLE" if w.name == "global" else "RATE_LIMITED"
                raise ApiError(code, retry_after_seconds=w.ttl)  # type: ignore[arg-type]
        for w, c in zip(ws, counts, strict=True):
            _, expires = self._counts.get(w.key, (0, 0.0))
            self._counts[w.key] = (c, expires if expires > now else now + w.ttl)
        return _tightest(ws, [w.limit - c for w, c in zip(ws, counts, strict=True)])

    async def peek(self, client_id: str) -> Quota:
        now = time.time()
        ws = _windows(self._settings, client_id, now)
        return _tightest(ws, [w.limit - self._get(w.key, now) for w in ws])


class DisabledRateLimiter:
    """Explicit opt-out for tests and local runs. Config refuses it in production."""

    def __init__(self, settings: Settings) -> None:
        if settings.is_production:
            raise ApiError("GENERATION_UNAVAILABLE")
        self._limit = settings.limit_per_ip_day

    async def reserve(self, client_id: str) -> Quota:
        return Quota(remaining=self._limit, limit=self._limit, window="day")

    async def peek(self, client_id: str) -> Quota:
        return Quota(remaining=self._limit, limit=self._limit, window="day")


def make_limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_backend == "upstash":
        return UpstashRateLimiter(settings)
    if settings.rate_limit_backend == "memory":
        return MemoryRateLimiter(settings)
    return DisabledRateLimiter(settings)
