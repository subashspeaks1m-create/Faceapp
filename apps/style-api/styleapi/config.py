"""Server-only configuration read from environment variables.

Provider keys are held as SecretStr so they never appear in repr(), logs or error bodies.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import SecretStr

Environment = Literal["production", "development", "test"]
RateLimitBackend = Literal["upstash", "memory", "disabled"]
ImageProviderName = Literal["openai", "gemini"]

OPENAI_EDIT_MODELS = ("gpt-image-2", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini")
QUALITIES = ("low", "medium", "high", "auto")
GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-image"
_GEMINI_MODEL = re.compile(r"^[a-z0-9][a-z0-9.\-]{2,63}$")


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
    image_provider: ImageProviderName = "openai"
    gemini_api_key: SecretStr | None = field(default=None, repr=False)
    gemini_model: str = GEMINI_DEFAULT_MODEL
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def provider_configured(self) -> bool:
        key = self.gemini_api_key if self.image_provider == "gemini" else self.openai_api_key
        return key is not None

    @property
    def active_model(self) -> str:
        return self.gemini_model if self.image_provider == "gemini" else self.openai_model


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

    openai_key = _secret(env, "OPENAI_API_KEY")
    gemini_key = _secret(env, "GEMINI_API_KEY")
    provider = env.get("IMAGE_PROVIDER", "").strip().lower()
    if not provider:
        # Unset: use Gemini only when it is the one key present.
        provider = "gemini" if gemini_key is not None and openai_key is None else "openai"
    if provider not in ("openai", "gemini"):
        raise ConfigError("IMAGE_PROVIDER must be openai or gemini")
    gemini_model = env.get("GEMINI_IMAGE_MODEL", GEMINI_DEFAULT_MODEL).strip()
    if not _GEMINI_MODEL.fullmatch(gemini_model):
        raise ConfigError("GEMINI_IMAGE_MODEL is not a valid model id")
    gemini_base = env.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")
    if not gemini_base.startswith("https://") and environment == "production":
        raise ConfigError("GEMINI_BASE_URL must use https in production")
    if provider == "gemini" and environment == "production" and env.get("GEMINI_PAID_TIER", "").strip().lower() != "true":
        # On Google's unpaid tier, submitted content may be used to improve Google's products and be
        # read by human reviewers, which contradicts this app's privacy notice for user photos.
        raise ConfigError("Gemini in production requires a billing-enabled key; set GEMINI_PAID_TIER=true once billing is on")

    return Settings(
        environment=environment,  # type: ignore[arg-type]
        allowed_origins=origins,
        openai_api_key=openai_key,
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
        image_provider=provider,  # type: ignore[arg-type]
        gemini_api_key=gemini_key,
        gemini_model=gemini_model,
        gemini_base_url=gemini_base,
    )
