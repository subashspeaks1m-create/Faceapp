"""Server-only configuration read from environment variables.

The provider key is held as a SecretStr so it never appears in repr(), logs or error bodies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from pydantic import SecretStr

Environment = Literal["production", "development", "test"]
RateLimitBackend = Literal["upstash", "memory", "disabled"]

OPENAI_EDIT_MODELS = ("gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini")
QUALITIES = ("low", "medium", "high", "auto")


class ConfigError(ValueError):
    pass


def _int(env: dict[str, str], name: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer") from e
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}")
    return value


def _secret(env: dict[str, str], name: str) -> SecretStr | None:
    raw = env.get(name, "").strip()
    return SecretStr(raw) if raw else None


@dataclass(frozen=True)
class Settings:
    environment: Environment
    allowed_origins: tuple[str, ...]
    openai_api_key: SecretStr | None = field(repr=False)
    openai_model: str
    openai_quality: str
    openai_base_url: str
    provider_timeout_seconds: int
    max_upload_bytes: int
    max_input_pixels: int
    min_input_side: int
    rate_limit_backend: RateLimitBackend
    upstash_url: str | None
    upstash_token: SecretStr | None = field(repr=False)
    rate_limit_salt: SecretStr | None = field(repr=False)
    limit_per_ip_hour: int
    limit_per_ip_day: int
    limit_global_day: int
    trust_proxy_headers: bool

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def provider_configured(self) -> bool:
        return self.openai_api_key is not None


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if environ is None else environ)
    environment = env.get("APP_ENV", "production").strip() or "production"
    if environment not in ("production", "development", "test"):
        raise ConfigError("APP_ENV must be production, development or test")

    origins = tuple(o.strip().rstrip("/") for o in env.get("ALLOWED_ORIGINS", "").split(",") if o.strip())
    for o in origins:
        if o == "*" or not (o.startswith("https://") or (environment != "production" and o.startswith("http://"))):
            raise ConfigError("ALLOWED_ORIGINS must list explicit https origins (no wildcard)")

    model = env.get("OPENAI_IMAGE_MODEL", "gpt-image-2").strip()
    if model not in OPENAI_EDIT_MODELS:
        raise ConfigError(f"OPENAI_IMAGE_MODEL must be one of {', '.join(OPENAI_EDIT_MODELS)}")
    quality = env.get("OPENAI_IMAGE_QUALITY", "medium").strip()
    if quality not in QUALITIES:
        raise ConfigError(f"OPENAI_IMAGE_QUALITY must be one of {', '.join(QUALITIES)}")

    backend = env.get("RATE_LIMIT_BACKEND", "upstash").strip()
    if backend not in ("upstash", "memory", "disabled"):
        raise ConfigError("RATE_LIMIT_BACKEND must be upstash, memory or disabled")
    if environment == "production" and backend != "upstash":
        # A per-instance counter is not a limit when several serverless instances run.
        raise ConfigError("production requires RATE_LIMIT_BACKEND=upstash")

    base_url = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if not base_url.startswith("https://") and environment == "production":
        raise ConfigError("OPENAI_BASE_URL must use https in production")

    return Settings(
        environment=environment,  # type: ignore[arg-type]
        allowed_origins=origins,
        openai_api_key=_secret(env, "OPENAI_API_KEY"),
        openai_model=model,
        openai_quality=quality,
        openai_base_url=base_url,
        provider_timeout_seconds=_int(env, "PROVIDER_TIMEOUT_SECONDS", 240, 10, 780),
        max_upload_bytes=_int(env, "MAX_UPLOAD_BYTES", 4_000_000, 100_000, 4_200_000),
        max_input_pixels=_int(env, "MAX_INPUT_PIXELS", 16_000_000, 1_000_000, 40_000_000),
        min_input_side=_int(env, "MIN_INPUT_SIDE", 256, 64, 1024),
        rate_limit_backend=backend,  # type: ignore[arg-type]
        # Vercel's Upstash integration may inject KV_REST_API_* instead; either name works.
        upstash_url=((env.get("UPSTASH_REDIS_REST_URL") or env.get("KV_REST_API_URL") or "").strip().rstrip("/") or None),
        upstash_token=_secret(env, "UPSTASH_REDIS_REST_TOKEN") or _secret(env, "KV_REST_API_TOKEN"),
        rate_limit_salt=_secret(env, "RATE_LIMIT_SALT"),
        limit_per_ip_hour=_int(env, "LIMIT_PER_IP_HOUR", 5, 1, 1000),
        limit_per_ip_day=_int(env, "LIMIT_PER_IP_DAY", 15, 1, 10000),
        limit_global_day=_int(env, "LIMIT_GLOBAL_DAY", 200, 1, 1_000_000),
        trust_proxy_headers=env.get("TRUST_PROXY_HEADERS", "true").strip().lower() == "true",
    )
