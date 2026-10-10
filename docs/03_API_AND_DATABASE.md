# 4. API contract and database implementation rules

`openapi.json` is a complete OpenAPI3.1 document generated from the FastAPI source and Pydantic2 models. JSON is accepted directly by Swagger/OpenAPI tools. All portrait routes require Bearer JWT; issuer/audience/signature/expiration verification belongs to the Runtime implementation. `result_cdn_url` retains the requested field name but means a short-lived authenticated private media grant with no shared cache. No public CDN portraits.

## Upload and transform

1. POST `/api/v1/faces/upload-url`: verify current owner-bound consent; allocate a random server-owned asset prefix and absolute10min deadline. Accept JPEG/PNG/HEIC up to10MiB; source decoded limit24MP. Return201 with a PUT URL valid60sec and exact required checksum/content-type headers. Enforce provider-supported signed content-length or final HEAD/stream validation and promptly delete oversized uploads; browser fetch cannot set forbidden Content-Length headers.
2. PUT bytes directly to the given URL. Never use client-supplied arbitrary object keys or remote image URLs. Bind expected SHA256 through S3 checksum signing; hex request hash converts to provider base64 checksum. An ETag is not SHA256. MinIO compatibility is an integration test.
3. POST `/uploads/{asset_id}/complete` after PUT: ownership check, HEAD/stream actual byte/type/hash verification, hardened decoder, EXIF orientation, ICC conversion to sRGB, EXIF/GPS stripping, pixel limit, detection. Return opaque face IDs bound to this asset/detection revision; IDs never identify people. Keep spatial metadata in expiring secured runtime storage, not permanent recognition profiles. No uploaded asset is usable before finalizedAt.
4. POST `/transform` with `Idempotency-Key`. Pydantic rejects unknown fields, NaN, booleans masquerading as numeric strength, unsupported presets and incompatible options. Server rejects missing/expired/non-owned face/asset/consent and blocked model. Source/candidate revisions prevent stale display; they are not authorization.
5. GET `/jobs/{job_id}?wait_seconds=25&after_revision=3`: return immediately if current event_revision>3 or terminal, otherwise wait up to25sec without holding a database connection/transaction. Return latest snapshot on timeout200. Token expiry/disconnection cancels waiter, not the job. UI uses jittered backoff and one pending poll/job. Optional WebSocket messages use exactly JobPayload plus monotonic event_revision; WebSocket transport is not implemented here.
6. Cancel returns202 cancel_requested when executing. Deletion202 means accepted; keep checking status until complete. Tombstone/revoke reads before asynchronous byte deletion; unavailable storage yields partial_failure, never an invented complete receipt.

## Representative transform request

```json
{"asset_id":"00000000-0000-4000-8000-000000000001","face_id":"00000000-0000-4000-8000-000000000002","filter_type":"age_50s","intensity":0.35,"preserve_background":true,"source_revision":0,"candidate_revision":1,"options":{}}
```

## State machine and safe errors

QUEUED→RUNNING→SUCCEEDED|FAILED; QUEUED/RUNNING→CANCEL_REQUESTED→CANCELED; live/terminal states→EXPIRED/PURGED when due. A tombstoned/purged job can never return to live state. Every change increments event_revision in the same transaction. `progress_percent=null` + indeterminate is honest unknown progress; measured_steps can expose actual denoising iteration count, not fabricated wall-time percentages. Only completed processing uses100. All response snapshots bind job_id,asset_id,face_id,source_revision,candidate_revision.

Errors:401 unauthenticated; owner-mismatched IDs return404;403 policy denied;409 request key/body conflict or stale source;410 asset expired/purged;422 bad input/no face/unsupported pose;429 insufficient admission quota;503 worker cold/filter unavailable. Safe envelope code/message/retryable/request_id; never expose model stack traces, object keys, tokens, input bytes or presigned URLs in logs. Insufficient credits uses402 with CREDIT_REQUIRED; add this to routes when paid Runtime is enabled. Rate limits begin at5 grants/min/user,2 pending transforms/user,20 status requests/min/user; tune after load testing.

## PostgreSQL / Prisma

`schema.prisma` uses explicitly versioned Prisma6 syntax (Prisma7 configuration differs). Core requested User/ImageJob/FilterPreset/CreditTransaction/AuditLog are joined by ConsentReceipt/UploadAsset/CreditWallet/OutboxEvent to close consent/ownership/billing races. `migration_constraints.sql` adds raw CHECKs, composite owner FKs and partial indexes Prisma does not express. Apply it after generated base migration. Never rely only on application enum/number constraints. Final production migrations must be reviewed/tested on PostgreSQL16.

Wallet balance is spendable total, reserved is in-flight encumbrance, available=balance-reserved. GRANT amount=+units; RESERVE/RELEASE amount=0; SETTLE amount=-units; REFUND amount=+units. Append ledger; don't mutate historical credit transactions. Monetary purchase receipts are separate store records before granting units. No portrait bytes/landmarks/recognition vectors in AuditLog; metadata allowlist={safe_code,manifest_version,worker_version,duration_bucket,deletion_status}.

## Atomic creation and credit reservation

Service pseudocode is a transaction contract, not an implemented repository:

```sql
BEGIN;
-- Acquire wallet row BEFORE checking existing keys, so concurrent owner requests serialize.
SELECT balance,reserved FROM "CreditWallet" WHERE "userId"=$1 FOR UPDATE;
SELECT id,"requestHash" FROM "ImageJob" WHERE "userId"=$1 AND "idempotencyKey"=$2;
-- Existing: same canonical hash returns original job; mismatch ROLLBACK +409.
-- Canonical SHA256 covers validated defaults+options+asset/face/revisions+filter;
-- use sorted UTF-8 JSON with finite numbers and a versioned normalization rule.
UPDATE "CreditWallet" SET reserved=reserved+$3,version=version+1
 WHERE "userId"=$1 AND balance-reserved >= $3 RETURNING "userId";
-- Zero rows: ROLLBACK +CREDIT_REQUIRED. Verify locked asset/consent/expiry/face first.
-- INSERT ImageJob, RESERVE ledger, and OutboxEvent in the SAME transaction.
-- All placeholders bound, job/user FK and uniqueness enforce owner/idempotency.
COMMIT;
```

Outbox relay claims rows FOR UPDATE SKIP LOCKED, publishes opaque job_id+fence to Celery and marks dispatched; publish/commit gap permits redelivery. Worker claims job by conditional update with incremented fence and lease; output object key includes fence. Completion requires statusRUNNING, same fence, no tombstone, unexpired asset/job. Only successful CAS may SETTLE and decrease wallet balance/reserved transactionally. Failure/cancel RELEASE reduces reserved. Distinct SETTLE/RELEASE rows alone do not prevent double settlement: require same locked job state and one settlement transition. Dead worker lease sweeper retries at mostonce within deadline; reconcile orphan reservations transactionally.

Privacy tombstones/revoked grants stay until all task retries/late outputs are past their allowed write horizon; later remove object keys/hash/face metadata and retain only legally justified non-image financial/audit records with a documented separate schedule. Do not label metadata “zero retention.”

## Implementation status

API source is an executable contract/health shell. Runtime auth/storage/repository/queue/billing/purge integrations deliberately return503 until implemented. It is not a finished production backend. User/job examples and generated schemas are real contracts; no payment processor credentials or commercial AI weights are supplied.
