"""Rate limiter tests. The Upstash limiter runs its real Lua script against a local redis-server
through a fake Upstash REST endpoint (skipped when redis-server is not installed)."""

import asyncio
import json
import shutil
import socket
import subprocess
import time
import unittest

import httpx

from styleapi.errors import ApiError
from styleapi.ratelimit import MemoryRateLimiter, UpstashRateLimiter, client_id_from

from .helpers import make_settings

TOKEN = "upstash-test-token"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MemoryLimiterTest(unittest.TestCase):
    def test_hourly_limit(self) -> None:
        limiter = MemoryRateLimiter(make_settings(LIMIT_PER_IP_HOUR="2", LIMIT_PER_IP_DAY="10"))
        q1 = asyncio.run(limiter.reserve("a"))
        q2 = asyncio.run(limiter.reserve("a"))
        self.assertEqual((q1.remaining, q2.remaining), (1, 0))
        with self.assertRaises(ApiError) as ctx:
            asyncio.run(limiter.reserve("a"))
        self.assertEqual(ctx.exception.code, "RATE_LIMITED")
        self.assertEqual(asyncio.run(limiter.reserve("b")).remaining, 1)

    def test_refused_in_production(self) -> None:
        s = make_settings(APP_ENV="test")
        object.__setattr__(s, "environment", "production")
        with self.assertRaises(ApiError):
            MemoryRateLimiter(s)

    def test_client_id_is_salted_hash(self) -> None:
        a = client_id_from("203.0.113.5", "salt1")
        self.assertNotIn("203.0.113.5", a)
        self.assertNotEqual(a, client_id_from("203.0.113.5", "salt2"))


@unittest.skipUnless(shutil.which("redis-server"), "redis-server not installed")
class UpstashLimiterTest(unittest.TestCase):
    proc: subprocess.Popen[bytes]
    port: int

    @classmethod
    def setUpClass(cls) -> None:
        import redis

        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            ["redis-server", "--port", str(cls.port), "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        cls.redis = redis.Redis(port=cls.port)
        for _ in range(50):
            try:
                cls.redis.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proc.terminate()
        cls.proc.wait(5)

    def setUp(self) -> None:
        self.redis.flushall()

    def _transport(self) -> httpx.MockTransport:
        r = self.redis

        def handler(request: httpx.Request) -> httpx.Response:
            if request.headers.get("authorization") != f"Bearer {TOKEN}":
                return httpx.Response(401, json={"error": "Unauthorized"})
            command = json.loads(request.content)
            result = r.execute_command(*command)

            def norm(v):  # type: ignore[no-untyped-def]
                if isinstance(v, bytes):
                    return v.decode()
                if isinstance(v, list):
                    return [norm(x) for x in v]
                return v

            return httpx.Response(200, json={"result": norm(result)})

        return httpx.MockTransport(handler)

    def _limiter(self, **overrides: str) -> UpstashRateLimiter:
        settings = make_settings(RATE_LIMIT_BACKEND="upstash", UPSTASH_REDIS_REST_URL="https://upstash.test", UPSTASH_REDIS_REST_TOKEN=TOKEN, **overrides)
        return UpstashRateLimiter(settings, client=httpx.AsyncClient(transport=self._transport()))

    def test_limits_and_rollback(self) -> None:
        limiter = self._limiter(LIMIT_PER_IP_HOUR="2", LIMIT_PER_IP_DAY="5", LIMIT_GLOBAL_DAY="100")
        self.assertEqual(asyncio.run(limiter.reserve("c1")).remaining, 1)
        self.assertEqual(asyncio.run(limiter.reserve("c1")).remaining, 0)
        with self.assertRaises(ApiError) as ctx:
            asyncio.run(limiter.reserve("c1"))
        self.assertEqual(ctx.exception.code, "RATE_LIMITED")
        self.assertGreater(ctx.exception.retry_after_seconds or 0, 0)
        # The refused request was rolled back everywhere: day counter is 2 and global is 2.
        peek = asyncio.run(limiter.peek("c1"))
        self.assertEqual(peek.remaining, 0)
        values = sorted(int(self.redis.get(k)) for k in self.redis.keys("sl:*"))
        self.assertEqual(values, [2, 2, 2])
        # TTLs are set.
        for k in self.redis.keys("sl:*"):
            self.assertGreater(self.redis.ttl(k), 0)

    def test_global_cap_reports_unavailable(self) -> None:
        limiter = self._limiter(LIMIT_PER_IP_HOUR="10", LIMIT_GLOBAL_DAY="2")
        asyncio.run(limiter.reserve("a"))
        asyncio.run(limiter.reserve("b"))
        with self.assertRaises(ApiError) as ctx:
            asyncio.run(limiter.reserve("c"))
        self.assertEqual(ctx.exception.code, "GENERATION_UNAVAILABLE")

    def test_concurrent_reservations_never_exceed_limit(self) -> None:
        limiter = self._limiter(LIMIT_PER_IP_HOUR="3", LIMIT_PER_IP_DAY="100")

        async def many() -> list[object]:
            return await asyncio.gather(*[limiter.reserve("same") for _ in range(10)], return_exceptions=True)

        results = asyncio.run(many())
        self.assertEqual(sum(1 for r in results if not isinstance(r, Exception)), 3)

    def test_fails_closed_when_unreachable_or_unauthorised(self) -> None:
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable", request=request)

        settings = make_settings(RATE_LIMIT_BACKEND="upstash", UPSTASH_REDIS_REST_URL="https://upstash.test", UPSTASH_REDIS_REST_TOKEN=TOKEN)
        for transport in (httpx.MockTransport(down), httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "x"}))):
            limiter = UpstashRateLimiter(settings, client=httpx.AsyncClient(transport=transport))
            with self.assertRaises(ApiError) as ctx:
                asyncio.run(limiter.reserve("x"))
            self.assertEqual(ctx.exception.code, "GENERATION_UNAVAILABLE")

    def test_missing_credentials_fail_closed(self) -> None:
        limiter = UpstashRateLimiter(make_settings(RATE_LIMIT_BACKEND="upstash"))
        with self.assertRaises(ApiError) as ctx:
            asyncio.run(limiter.reserve("x"))
        self.assertEqual(ctx.exception.code, "GENERATION_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
