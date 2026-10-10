"""Short-lived signed media capabilities. A token names a job/owner/fence; the gateway re-checks the database."""

from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
import base64
import hashlib
import hmac
import json


@dataclass(frozen=True)
class MediaClaim:
    job_id: UUID
    owner: UUID
    fence: int
    expires_at: int  # Unix seconds


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(secret: bytes, claim: MediaClaim) -> str:
    payload = json.dumps(
        {"j": str(claim.job_id), "u": str(claim.owner), "f": claim.fence, "e": claim.expires_at},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    mac = hmac.new(secret, b"media.v1." + payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(mac)}"


def verify(secret: bytes, token: str) -> MediaClaim | None:
    """Return the claim for an authentic token (caller checks expiry), else None."""
    try:
        payload_b64, mac_b64 = token.split(".")
        payload = _unb64(payload_b64)
        expected = hmac.new(secret, b"media.v1." + payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(mac_b64)):
            return None
        data = json.loads(payload)
        claim = MediaClaim(UUID(data["j"]), UUID(data["u"]), int(data["f"]), int(data["e"]))
    except (ValueError, KeyError, TypeError):
        return None
    return claim
