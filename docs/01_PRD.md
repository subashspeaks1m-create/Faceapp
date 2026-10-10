# 1. Product Requirements Document & Feature Specification

## Scope and launch inventory

Independent portrait editor, iOS/Android native app; Next.js web admin and preview; Python GPU inference; FastAPI gateway. Preserve original and selected-face identity while applying user-selected creative appearance changes. No face identification/search or automatic sensitive-attribute classification. “Gender” filter IDs implement explicit feminine/masculine appearance choices; they do not determine a person's gender. Age effects are illustrative, not future predictions. Teen is an appearance transform; account eligibility and consent for actual minor source subjects are a separate launch policy decision.

The request implies 13 primitive effects (four age + three expression + two presentation + four cosmetics). To supply exactly 12 launch tiles without dropping a cosmetic capability, **Beauty Retouch combines skin smoothing and makeup** with independent bounded subparameters. The manifest therefore has 12 filters and 13 underlying capabilities.

| ID | Effect | Method / acceptance |
|---|---|---|
| age_young | Young adult, target style 25 | Licensed age model; same recognizable face, pose, iris, skin tone |
| age_teen | Teen, target style 17 | Controlled illustrative regression; no automatic age inference |
| age_50s | 50s, target style 55 | Age-related texture; no wholesale identity replacement |
| age_70s | 70s, target style 75 | Plausible age texture/hair; geometry continuity benchmark |
| smile_subtle | Closed-lip subtle smile | Selected mouth/cheek expression, no new teeth |
| smile_tooth | Tooth smile | Anatomically coherent teeth/lips, same framing |
| laugh | Laugh | Larger expression with eye/cheek/mouth coherence |
| gender_feminine | Feminine presentation | User-selected feature shifts bounded by continuity rubric |
| gender_masculine | Masculine presentation | User-selected feature shifts; no gender classification |
| hair_color | Hair hue | Parser hair region and luminance-preserving recolor |
| beard_density | Beard density | Lower-face texture and hair direction; protected lips/eyes |
| beauty_retouch | Makeup + skin smoothing | Independent substrengths, boundary and texture preservation |

All 12 manifest entries are launch intentions, not enabled production adapters. Age/expression/presentation routes need licensed trained weights; deterministic smoothing is provided as a real internal module. Geometry preservation cannot mean zero movement of landmarks for expression/gender changes: constrain untargeted geometry and recognizable identity, and measure allowed target deformation separately.

## User flow and editor invariants

Pick/capture → orientation/ICC normalize → select face → explicit ephemeral-processing disclosure → upload/finalize → preview request → compare → Apply → save original-resolution result. Candidate changes do not silently commit. Cancel invalidates candidate token and requests job cancellation; a billed CUDA call may finish anyway. Undo restores prior committed graph without automatically incurring inference. Bind output to asset + source revision + face ID + candidate revision; a late result cannot replace current intent.

Original never overwritten; local drafts independent of remote expiry. Local brightness/crop previews use Skia/native pixel operations and exported pixels must match. Warm inference result uses one selected 512 crop, source frame max24 MP, ingress <=10 MiB, on-wire normalized preview <=1 MiB for the target latency benchmark. Multiple faces are selectable; untargeted faces protected. Full-hair extensions may need an expanded crop outside the fast 512 face path and a different latency tier.

## Performance contract — target, not measured guarantee

Reference fast-preview SLO: p95 end-to-end <=2,500 ms and p99 <=4,000 ms, from tapping Preview through first usable displayed result, including selected-photo upload, queue, inference, retrieval and decode. Reference conditions: <=1 MiB preview transfer, >=40 Mbps usable uplink/downlink, RTT<=50ms, warm pinned model on measured GPU class, one face, queue admission cap. A 10 MiB upload at 10 Mbps takes about 8.4 seconds before inference and cannot meet this SLO. Mobile networks and high-resolution final renders need separate budgets.

| Warm stage | p95 engineering budget (ms) |
|---|---:|
| Client encoding + upload | 300 |
| Auth/finalization/admission/queue | 100 |
| Decode + detection + alignment | 120 |
| Segmentation | 80 |
| Transformation | 900 |
| Optional restoration | 100 |
| Blend + encode | 150 |
| Result delivery + client decode | 300 |
| Margin | 450 |
| Total | 2,500 |

Cold worker initialization: proposed maximum 30 seconds, boot/download-independent local mounted weights; initialize/warm and become ready before admission. Cold first request <=35 seconds in explicit slow tier. Model downloads are deployment work, never request work. A universal <2.5s cold-start target for large diffusion weights is not promised. Keep min warm replicas>=1 per enabled fast route; if none ready, reject/defer transparently rather than quietly breach fast-tier SLO. CUDA inference is non-preemptible in many setups: enforce soft checkpoints plus worker/process deadlines and purge fencing.

Fast route selection requires measured per-filter p95, VRAM and quality evidence. Standard SDXL/FLUX many-step diffusion may not fit 900ms; use benchmarked distillation/compiled models or reclassify to slow tier. Triton batching queue delay capped at 2ms initially and measured; throughput improvements cannot destroy interactive latency. Final 12/24 MP blend/encode needs a separate measured SLO (initial target p95<=6s, same generated crop reused when quality permits).

## Acceptance and reliability

Zero critical identity replacement or non-target face modification in release evaluation. Review >=100 permitted samples per generative family as planning minimum, with diverse capture conditions, hair/skin/pose/occlusion. >=95% continuity and >=90% acceptable edit are initial gates, not achieved measurements. Refine threshold using sample sizes and severe-failure review. Crash-free>=99.5% and export success>=99% are proposals. Measure system under burst/concurrency, not one warm demo. Required tests cover masks, inversion, zero-strength identity, missing modules, quota/idempotency/deletion races and true output dimensions.

## Ephemeral processing and biometric requirements

No archival portrait retention or training reuse. Originals/masks/crops/embeddings expire immediately after required processing; initial source purge target <=30s after the last dependent terminal job or cancellation. Result delivery window <=5min, delete on acknowledged save, hard absolute cutoff <=10min after initial upload. Orphan uploads expire <=2min. No portrait bytes in logs, Redis, dead-letter jobs, backups, public CDN or crash reports. Working buffers, result delivery and audit/financial metadata are separate retention classes; do not market literal zero bytes retained while offering a downloadable result.

GDPR engineering tasks: choose Article6 basis; classify whether processing is biometric identification under Article9; minimize data, support access/withdrawal/erasure, assess DPIA need, processor agreements/transfer mechanism, security and privacy by design. A photo is not automatically Article9 biometric identification data. BIPA assessment must consider derived face-geometry scans even where photographs are excluded; where applicable establish public retention/destruction policy, informed written notice/release before collection, restricted disclosure and secure handling. Its retention limit is not permission to keep data longer than this product purpose requires. These are deployment gates requiring actual jurisdiction/provider review, not a code-generated compliance certification.

Primary legal references: [GDPR official text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), [BIPA §15](https://www.ilga.gov/legislation/ilcs/fulltext?DocName=074000140K15). Technical purge details: docs/04_PRIVACY_PURGE.md.
