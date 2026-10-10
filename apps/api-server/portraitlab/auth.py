"""Bearer JWT verification: signature, issuer, audience, expiry and subject are all mandatory."""

from __future__ import annotations
import asyncio
import jwt
from .config import AuthConfig
from .errors import unauthenticated


class JwtVerifier:
    def __init__(self, config: AuthConfig):
        self.config = config
        self._jwks = jwt.PyJWKClient(config.jwks_url, cache_keys=True) if config.jwks_url else None

    def _key(self, token: str):
        if self._jwks is not None:
            return self._jwks.get_signing_key_from_jwt(token).key
        if self.config.public_key_pem is not None:
            return self.config.public_key_pem
        return self.config.dev_hmac_secret

    def verify_sync(self, token: str) -> str:
        """Return the verified external subject or raise 401 without revealing why."""
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self.config.algorithms:
                raise unauthenticated()
            claims = jwt.decode(
                token,
                self._key(token),
                algorithms=list(self.config.algorithms),
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, ValueError):
            raise unauthenticated() from None
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 0 < len(subject) <= 255:
            raise unauthenticated()
        return subject

    async def verify(self, token: str) -> str:
        if self._jwks is not None:
            # JWKS refresh performs blocking network I/O.
            return await asyncio.to_thread(self.verify_sync, token)
        return self.verify_sync(token)
