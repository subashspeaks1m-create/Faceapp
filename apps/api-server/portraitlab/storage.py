"""Private S3-compatible object storage. Keys are always server-generated."""

from __future__ import annotations
import asyncio
import base64
import hashlib
from dataclasses import dataclass
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from .config import StorageConfig


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectHead:
    byte_length: int
    content_type: str | None


def sha256_hex_to_b64(hex_digest: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_digest)).decode()


class ObjectStore:
    def __init__(self, config: StorageConfig):
        self.bucket = config.bucket
        common = dict(
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
        )
        boto_config = Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 3})
        self._client = boto3.client("s3", endpoint_url=config.internal_endpoint, config=boto_config, **common)
        # Presigned URLs must name the host the device can reach; signing does no I/O.
        self._presigner = boto3.client(
            "s3", endpoint_url=config.public_endpoint or config.internal_endpoint, config=boto_config, **common
        )

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    def ensure_bucket_sync(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)

    def presign_put(self, key: str, content_type: str, sha256_hex: str, expires_seconds: int) -> tuple[str, dict]:
        checksum = sha256_hex_to_b64(sha256_hex)
        url = self._presigner.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type, "ChecksumSHA256": checksum},
            ExpiresIn=expires_seconds,
        )
        # Signed headers: the device must send exactly these or the store rejects the PUT.
        # Some S3-compatible stores verify only the header signature, not the body digest,
        # so finalization independently streams and hashes the object.
        return url, {"Content-Type": content_type, "x-amz-checksum-sha256": checksum}

    async def head(self, key: str) -> ObjectHead | None:
        try:
            r = await self._run(self._client.head_object, Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise StorageError("head failed") from None
        return ObjectHead(int(r["ContentLength"]), r.get("ContentType"))

    async def read_limited(self, key: str, max_bytes: int) -> tuple[bytes, str]:
        """Stream at most max_bytes and return (bytes, sha256 hex); larger objects raise."""

        def _read():
            body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
            digest, chunks, total = hashlib.sha256(), [], 0
            for chunk in body.iter_chunks(64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    body.close()
                    raise StorageError("object exceeds limit")
                digest.update(chunk)
                chunks.append(chunk)
            return b"".join(chunks), digest.hexdigest()

        try:
            return await self._run(_read)
        except ClientError:
            raise StorageError("read failed") from None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await self._run(self._client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        except ClientError:
            raise StorageError("write failed") from None

    async def list_children(self, prefix: str) -> list[str]:
        def _list():
            out: list[str] = []
            for page in self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self.bucket, Prefix=prefix, Delimiter="/"
            ):
                out.extend(p["Prefix"] for p in page.get("CommonPrefixes", []))
            return out

        try:
            return await self._run(_list)
        except ClientError:
            raise StorageError("list failed") from None

    async def delete_prefix(self, prefix: str) -> None:
        """Delete every object, version, delete marker and multipart upload under prefix, then verify."""

        def _delete():
            c, b = self._client, self.bucket
            uploads = c.list_multipart_uploads(Bucket=b, Prefix=prefix).get("Uploads", [])
            for u in uploads:
                c.abort_multipart_upload(Bucket=b, Key=u["Key"], UploadId=u["UploadId"])
            targets: list[dict] = []
            try:
                for page in c.get_paginator("list_object_versions").paginate(Bucket=b, Prefix=prefix):
                    for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
                        targets.append({"Key": v["Key"], "VersionId": v["VersionId"]})
            except ClientError:
                targets = []  # Store without versioning support: fall back to current objects.
            for page in c.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=prefix):
                for o in page.get("Contents", []):
                    targets.append({"Key": o["Key"]})
            for t in targets:
                c.delete_object(Bucket=b, **t)
            remaining = c.list_objects_v2(Bucket=b, Prefix=prefix, MaxKeys=1).get("KeyCount", 0)
            if remaining:
                raise StorageError("objects remain after delete")

        try:
            await self._run(_delete)
        except ClientError:
            raise StorageError("delete failed") from None
