# Ephemeral purge daemon and security contract

## Retention modes

“Zero archival retention” means no saved portrait history on servers; working processing and delivery bytes still exist briefly. Source/crop/mask/embedding deletion target<=30s after the last dependent terminal completion/cancel; result<=5min delivery and delete immediately after authenticated save acknowledgment; all descendants hard access cutoff<=10min from initial upload; orphan uploads<=2min. Hard cutoff is enforced on reads/grants immediately, not by eventual lifecycle rules. Privacy text must disclose delivery window. No backups of image bucket. Optional identity vectors live only in the job process, never database or logs.

## Daemon contract

Run every5s. Claim metadata using SELECT FOR UPDATE SKIP LOCKED; select eligible terminal/expired jobs, orphan uploads and deletion requests. Atomically tombstone/fence job and revoke media capability before I/O. Enumerate explicit object descendants and multipart uploads; delete current and all version IDs/delete markers where versioning exists (prefer ephemeral bucket versioning off); abort multipart uploads. Stop/revoke provider references if any. Verify absence, set purge_complete timestamp and redact object pointers. Failures retain tombstone and retry exponential backoff+jitter<=60s; alert if age>30s target or hardcutoff exceeded. Object lifecycle is backstop, not correctness mechanism.

Worker must inspect fence before input fetch and provider submission, and use conditional result attachment after output write. If attachment loses race or expires, delete that output immediately. Task outbox reconciliation and independent prefix inventory sweep catch process crashes/unregistered writes. Use per-job random prefix, bounded owner-scoped metadata grants and a deterministic descendant manifest. Daemon service identity can delete only ephemeral prefixes; it cannot read arbitrary user library data.

No public CDN cache. Private result gateway authenticates signed capability, owner/job/expiry/tombstone on every access; Cache-Control:no-store,max-age=0; disabled CDN caching/origin logs for portraits. URLs carry short media token rather than permanent object key; token expires<=15s and rotates via authenticated status endpoint. A direct S3 URL is a temporary bearer permission and cannot be revoked by changing DB alone; object removal/grant expiry must be honored. Saving a photo to the user's device is not server retention.

CPU buffer del/zeroing is best-effort: allocator/GPU/kernel copies may remain; secure erase on SSD/object storage is not guaranteed by overwriting arrays. For stronger processing isolation use per-job subprocess/pod with tmpfs, swap disabled, restricted dumps and teardown, with cost/latency measured. PyTorch empty_cache is not secure zeroization. Cloud GPU/provider memory policies must match the threat model. Do not claim cryptographically provable total erasure without supporting infrastructure.

## Compliance gates

Prepare documented processing purposes, Article6 basis and Article9 biometric identification analysis, processor contracts/regions/transfers, DPIA assessment, DSAR/delete workflow, secure processing and truthful policy. BIPA may cover geometry scans even though statutory photographs have an exclusion; validate applicability/consent/public retention policy for actual operations and jurisdiction. Do not claim automatic GDPR/BIPA certification from this repository. Retain necessary consent/audit/billing metadata under a separate reviewed policy, without portrait/face vectors.

Primary sources: [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), [BIPA15](https://www.ilga.gov/legislation/ilcs/fulltext?DocName=074000140K15). Engineering release tests: delete during upload/finalize/enqueue/inference/output write/result download; duplicate/late tasks; versioned objects/multipart; provider failure; restore from metadata backup; logs and dead-letter redaction; orphan sweep. Report exact physical deletion lag and remaining provider constraints.
