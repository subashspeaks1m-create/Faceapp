"""Environment configuration. Secret values are read from the environment, never logged."""

from __future__ import annotations
from dataclasses import dataclass, field
import os


class ConfigError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable {name}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None or raw == "" else int(raw)


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    audience: str
    algorithms: tuple[str, ...]
    # Exactly one key source: PEM public key, JWKS URL, or (development only) HMAC secret.
    public_key_pem: str | None = None
    jwks_url: str | None = None
    dev_hmac_secret: str | None = field(default=None, repr=False)
    leeway_seconds: int = 30


@dataclass(frozen=True)
class StorageConfig:
    bucket: str
    internal_endpoint: str | None
    public_endpoint: str | None
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    region: str = "us-east-1"


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str = field(repr=False)
    auth: AuthConfig
    storage: StorageConfig
    media_token_secret: bytes = field(repr=False)
    consent_policy_version: str = "2026-10-01"
    credit_units_per_job: int = 1
    upload_grant_seconds: int = 60
    asset_absolute_ttl_seconds: int = 600
    orphan_upload_seconds: int = 120
    source_idle_purge_seconds: int = 30
    result_delivery_seconds: int = 300
    media_token_seconds: int = 15
    worker_lease_seconds: int = 60
    max_attempts: int = 2
    max_pending_jobs: int = 2
    upload_grants_per_minute: int = 5
    max_upload_bytes: int = 10_485_760
    max_decoded_pixels: int = 24_000_000

    @property
    def production(self) -> bool:
        return self.environment == "production"


def load_settings() -> Settings:
    environment = os.environ.get("PORTRAITLAB_ENV", "development")
    dev_secret = os.environ.get("JWT_DEV_HS256_SECRET") or None
    public_key = os.environ.get("JWT_PUBLIC_KEY_PEM") or None
    jwks_url = os.environ.get("JWT_JWKS_URL") or None
    if environment == "production" and dev_secret:
        raise ConfigError("JWT_DEV_HS256_SECRET must not be set in production")
    sources = [x for x in (dev_secret, public_key, jwks_url) if x]
    if len(sources) != 1:
        raise ConfigError("Configure exactly one of JWT_PUBLIC_KEY_PEM, JWT_JWKS_URL or JWT_DEV_HS256_SECRET")
    algorithms = ("HS256",) if dev_secret else tuple(os.environ.get("JWT_ALGORITHMS", "RS256,ES256").split(","))
    if dev_secret is None and any(a.startswith("HS") for a in algorithms):
        raise ConfigError("Symmetric JWT algorithms are only allowed for isolated development auth")
    media_secret = _required("MEDIA_TOKEN_SECRET").encode()
    if len(media_secret) < 32:
        raise ConfigError("MEDIA_TOKEN_SECRET must be at least 32 bytes")
    return Settings(
        environment=environment,
        database_url=_required("DATABASE_URL"),
        auth=AuthConfig(
            issuer=_required("JWT_ISSUER"),
            audience=_required("JWT_AUDIENCE"),
            algorithms=algorithms,
            public_key_pem=public_key,
            jwks_url=jwks_url,
            dev_hmac_secret=dev_secret,
        ),
        storage=StorageConfig(
            bucket=_required("S3_BUCKET"),
            internal_endpoint=os.environ.get("S3_INTERNAL_ENDPOINT") or None,
            public_endpoint=os.environ.get("S3_PUBLIC_ENDPOINT") or None,
            access_key=_required("S3_ACCESS_KEY"),
            secret_key=_required("S3_SECRET_KEY"),
            region=os.environ.get("S3_REGION", "us-east-1"),
        ),
        media_token_secret=media_secret,
        consent_policy_version=os.environ.get("CONSENT_POLICY_VERSION", "2026-10-01"),
        credit_units_per_job=_int("CREDIT_UNITS_PER_JOB", 1),
    )
