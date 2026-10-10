# ADR 0002: SeaweedFS replaces MinIO for local object storage

Status: accepted for local development (2026-10-10)

## Problem

`docker-compose.yml` named `minio/minio:RELEASE.2025-04-22T22-12-26Z`. On 2026-10-10 Docker Hub answered "repository does not exist" for `minio/minio` (any tag) and `quay.io/minio/minio` was not reachable from the build environment, so `docker compose up` could not start storage.

## Decision

Use the SeaweedFS S3 gateway (`chrislusf/seaweedfs:3.97`, Apache-2.0) on tmpfs for local development and integration tests. Production storage remains any private S3-compatible service chosen at deployment.

Measured behaviour that shaped the runtime:

- SeaweedFS rejects a presigned PUT whose `Content-Type` or `x-amz-checksum-sha256` header differs from what was signed (403).
- It does **not** verify the body against the signed SHA256 header: a different body with the correct header was stored. Finalization therefore streams the object and hashes it server-side before accepting it (`PostgresRuntime.complete`). This is required for any store, since an ETag is not a SHA256.
- Each bucket allocates its own volumes; tests delete their bucket afterwards and compose limits volume size, or the volume count runs out.

## Alternatives

Moto (an S3 mock, not a server), Garage and RustFS (pullable, not evaluated further). A mock would not prove presigned-URL behaviour.

## Consequences

`docker-compose.yml` service `minio` is now `s3`; credentials come from `infra/seaweedfs/s3.json` (copy the `.example`). Production deployment must re-run `tests/test_runtime_integration.py` against the real provider.
