# FaceApp-like AI Portrait Editor: Production Project Specification & Asset Bundle

Prepared2026-10-10. Independent working product name: PortraitLab. This document embeds full editable source/config/contract/assets in seven requested sections. It is a production-oriented specification and verified scaffold, not a completed FaceApp replica or measured GPU service. Generative weights are absent and routes fail closed until approved implementations are supplied. README.md and VALIDATION_REPORT.md define exact implementation boundaries.

# 1. Product Requirements Document (PRD) & Feature Spec



### Scope and launch inventory

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

### User flow and editor invariants

Pick/capture → orientation/ICC normalize → select face → explicit ephemeral-processing disclosure → upload/finalize → preview request → compare → Apply → save original-resolution result. Candidate changes do not silently commit. Cancel invalidates candidate token and requests job cancellation; a billed CUDA call may finish anyway. Undo restores prior committed graph without automatically incurring inference. Bind output to asset + source revision + face ID + candidate revision; a late result cannot replace current intent.

Original never overwritten; local drafts independent of remote expiry. Local brightness/crop previews use Skia/native pixel operations and exported pixels must match. Warm inference result uses one selected 512 crop, source frame max24 MP, ingress <=10 MiB, on-wire normalized preview <=1 MiB for the target latency benchmark. Multiple faces are selectable; untargeted faces protected. Full-hair extensions may need an expanded crop outside the fast 512 face path and a different latency tier.

### Performance contract — target, not measured guarantee

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

### Acceptance and reliability

Zero critical identity replacement or non-target face modification in release evaluation. Review >=100 permitted samples per generative family as planning minimum, with diverse capture conditions, hair/skin/pose/occlusion. >=95% continuity and >=90% acceptable edit are initial gates, not achieved measurements. Refine threshold using sample sizes and severe-failure review. Crash-free>=99.5% and export success>=99% are proposals. Measure system under burst/concurrency, not one warm demo. Required tests cover masks, inversion, zero-strength identity, missing modules, quota/idempotency/deletion races and true output dimensions.

### Ephemeral processing and biometric requirements

No archival portrait retention or training reuse. Originals/masks/crops/embeddings expire immediately after required processing; initial source purge target <=30s after the last dependent terminal job or cancellation. Result delivery window <=5min, delete on acknowledged save, hard absolute cutoff <=10min after initial upload. Orphan uploads expire <=2min. No portrait bytes in logs, Redis, dead-letter jobs, backups, public CDN or crash reports. Working buffers, result delivery and audit/financial metadata are separate retention classes; do not market literal zero bytes retained while offering a downloadable result.

GDPR engineering tasks: choose Article6 basis; classify whether processing is biometric identification under Article9; minimize data, support access/withdrawal/erasure, assess DPIA need, processor agreements/transfer mechanism, security and privacy by design. A photo is not automatically Article9 biometric identification data. BIPA assessment must consider derived face-geometry scans even where photographs are excluded; where applicable establish public retention/destruction policy, informed written notice/release before collection, restricted disclosure and secure handling. Its retention limit is not permission to keep data longer than this product purpose requires. These are deployment gates requiring actual jurisdiction/provider review, not a code-generated compliance certification.

Primary legal references: [GDPR official text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), [BIPA §15](https://www.ilga.gov/legislation/ilcs/fulltext?DocName=074000140K15). Technical purge details: docs/04_PRIVACY_PURGE.md.


## Detailed ephemeral purge daemon specification



### Retention modes

“Zero archival retention” means no saved portrait history on servers; working processing and delivery bytes still exist briefly. Source/crop/mask/embedding deletion target<=30s after the last dependent terminal completion/cancel; result<=5min delivery and delete immediately after authenticated save acknowledgment; all descendants hard access cutoff<=10min from initial upload; orphan uploads<=2min. Hard cutoff is enforced on reads/grants immediately, not by eventual lifecycle rules. Privacy text must disclose delivery window. No backups of image bucket. Optional identity vectors live only in the job process, never database or logs.

### Daemon contract

Run every5s. Claim metadata using SELECT FOR UPDATE SKIP LOCKED; select eligible terminal/expired jobs, orphan uploads and deletion requests. Atomically tombstone/fence job and revoke media capability before I/O. Enumerate explicit object descendants and multipart uploads; delete current and all version IDs/delete markers where versioning exists (prefer ephemeral bucket versioning off); abort multipart uploads. Stop/revoke provider references if any. Verify absence, set purge_complete timestamp and redact object pointers. Failures retain tombstone and retry exponential backoff+jitter<=60s; alert if age>30s target or hardcutoff exceeded. Object lifecycle is backstop, not correctness mechanism.

Worker must inspect fence before input fetch and provider submission, and use conditional result attachment after output write. If attachment loses race or expires, delete that output immediately. Task outbox reconciliation and independent prefix inventory sweep catch process crashes/unregistered writes. Use per-job random prefix, bounded owner-scoped metadata grants and a deterministic descendant manifest. Daemon service identity can delete only ephemeral prefixes; it cannot read arbitrary user library data.

No public CDN cache. Private result gateway authenticates signed capability, owner/job/expiry/tombstone on every access; Cache-Control:no-store,max-age=0; disabled CDN caching/origin logs for portraits. URLs carry short media token rather than permanent object key; token expires<=15s and rotates via authenticated status endpoint. A direct S3 URL is a temporary bearer permission and cannot be revoked by changing DB alone; object removal/grant expiry must be honored. Saving a photo to the user's device is not server retention.

CPU buffer del/zeroing is best-effort: allocator/GPU/kernel copies may remain; secure erase on SSD/object storage is not guaranteed by overwriting arrays. For stronger processing isolation use per-job subprocess/pod with tmpfs, swap disabled, restricted dumps and teardown, with cost/latency measured. PyTorch empty_cache is not secure zeroization. Cloud GPU/provider memory policies must match the threat model. Do not claim cryptographically provable total erasure without supporting infrastructure.

### Compliance gates

Prepare documented processing purposes, Article6 basis and Article9 biometric identification analysis, processor contracts/regions/transfers, DPIA assessment, DSAR/delete workflow, secure processing and truthful policy. BIPA may cover geometry scans even though statutory photographs have an exclusion; validate applicability/consent/public retention policy for actual operations and jurisdiction. Do not claim automatic GDPR/BIPA certification from this repository. Retain necessary consent/audit/billing metadata under a separate reviewed policy, without portrait/face vectors.

Primary sources: [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng), [BIPA15](https://www.ilga.gov/legislation/ilcs/fulltext?DocName=074000140K15). Engineering release tests: delete during upload/finalize/enqueue/inference/output write/result download; duplicate/late tasks; versioned objects/multipart; provider failure; restore from metadata backup; logs and dead-letter redaction; orphan sweep. Report exact physical deletion lag and remaining provider constraints.

# 2. Full-Stack System Architecture & Tech Stack



### Canonical stack and alternatives

React Native/Expo custom development builds, TypeScript strict, Reanimated3 compatibility track, Skia preview canvas, VisionCamera capture; system photo picker for import. Next.js admin/preview uses OIDC + role checks and metadata only; no routine portrait browsing. Python FastAPI gateway + Pydantic; PostgreSQL + Prisma schema/migration tooling (Python accesses via Psycopg/SQLAlchemy, not Prisma client); Celery durable work + Redis broker (IDs only); S3/MinIO private byte store. Triton serves pinned ONNX/TensorRT small models; Python PyTorch/CUDA worker orchestrates generative modules. Modal/RunPod are deployment alternatives to the GPU worker, not extra overlapping queues. NestJS/BullMQ is an alternative gateway/queue pair requiring a deliberate port of contracts; do not run both stacks without reason.

Reanimated3 is an explicit requested compatibility constraint, not the newest default. Proposed legacy baseline Expo53/RN0.79/React19 + Reanimated3.17.5 (minimum patch supporting RN0.79 per official table). Verify exact Expo patch, Skia/VisionCamera native dependencies and lockfile before building. Reanimated3 is no longer actively maintained; upgrading later requires an ADR and matching native package changes. No claim this legacy baseline passes current store target-SDK requirements. CUDA12/cudNN compatibility is pinned per deployment; ONNX Runtime and PyTorch must share compatible CUDA/cuDNN majors. Docker GPU runtime/driver compatibility must be tested on deployment hardware.

Architecture: selected file → owner-bound PUT grant → complete/byte validation → DB transaction(authorize, reserve, job, outbox) → dispatcher → Celery worker slot → detector/parser/transformer → blend/export → private result object → signed media gateway. Client long-polls job metadata; result URL is short-lived/private. Worker writes are fenced by job state/tombstone/absolute expiry. Original metadata graph lives locally; server never keeps historical portraits beyond ephemeral cutoff.

### 2.1 Detection and alignment

SCRFD/RetinaFace detection commonly provides five 2D keypoints (eyes, nose, mouth corners), not an assumed 68-point mesh. Add a separately licensed dense-landmark model if required for lips/eyelids/geometry constraints. Do not invoke a recognition model merely to detect a face. Detector contract: boxes[N,4], scores[N], kps[N,5,2], normalized-source pixel coordinates; finite checks, face-size/confidence/pose rejection, stable ordering/session-bound face IDs.

Let source keypoints p_i and canonical targets q_i in R². Minimize Σ||sRp_i+t−q_i||² over s>0, R in SO(2). Center P/Q; C=(1/n)Q_c^T P_c=UΣV^T; D=diag(1,sign(det(UV^T))); R=UDV^T; s=tr(ΣD)/((1/n)Σ||p_i−p_bar||²); t=q_bar−sRp_bar. M=[sR|t], source→aligned; crop(u)=source(M^-1u). Use similarity rather than unconstrained affine shear. Standard five-point 128-canvas centering is scaled to512; retain exact M and inverse. Reject degenerate points and excessive residual. Code implements these equations with NumPy/OpenCV.

Alignment preserves pose/framing baseline; it does not mathematically guarantee generative identity. 512 face alignment can omit long hair; structural hairstyle uses a separately validated larger ROI or portrait model. Source alpha/EXIF/ICC normalization precedes alignment. Back-transform masks/outputs with identical matrices.

### 2.2 Segmentation

BiSeNet/FaceParsing adapter exports ONNX NCHW RGB,512², float32 normalized with registry-defined mean/std; output logits[1,C,H,W], nearest-resized argmax labels. Class IDs are model-specific. Example19-class mapping records skin1, eyes4/5, nose10, mouth11, lips12/13, hair17, background0; do not use this mapping for arbitrary weights without verification. Mask for region C: m(x)=1[label(x)∈C]. Erode sensitive borders, feather with finite Gaussian kernel, multiply source validity mask, protect other face regions. Wider structural hair mask may include newly occluded background; preserve_background means outside the approved change support remains unchanged.

### 2.3 Model routes

Fast controllable model: invert image to latent w*=argmin_w(L_reconstruction+λ_id L_id+λ_lpips L_perceptual), then w'=w*+αd_f. Directions d_f need actual trained artifacts and calibration. Age/expression/gender directions are not supplied by vanilla StyleGAN3; inversion, identity constraints and conditional controls are additional models. NVIDIA licensing must be reviewed.

Diffusion: encode z0=E(crop); z_t=sqrt(alpha_bar_t)z0+sqrt(1−alpha_bar_t)ε; predict conditioned noise or model-specific velocity, apply scheduler steps. SDXL supports an appropriate inpaint pipeline; FLUX uses its own flow-matching/scheduler contracts, not this DDPM equation blindly. Conditioning can include geometry ControlNet and licensed identity adapter. FaceID embedding introduces separate biometric/license review; default production path must not silently adopt research-only weights. Learned identity loss is generally 1−cos(e_source,e_result); minimizing it is not a proof of unchanged identity.

Job intensity α∈[0,1]. Local modules multiply color/retouch delta. Structural modules use calibrated strength tiers/model controls; source/result opacity mixing of changed mouths or hair causes ghosting and is rejected. Force α=0 to exact original output. Validate target-versus-untargeted landmark displacement, identity continuity, locality and skin-tone preservation separately. `assets/filters.json` pins adapter keys/parameters; unknown weight/checksum blocks readiness.

### 2.4 Restoration and blending

CodeFormer/GFPGAN are optional artifact restoration adapters, disabled by default because restoration can alter identity or undo intended texture/age. Record weight/runtime licenses and use bounded fidelity settings, then re-evaluate output. No blind double-restoration. GFPGAN repo code license alone does not approve all downloaded dependencies/weights; CodeFormer uses its own license.

Blend delta in linear light to retain untouched source detail: L_s=decode_sRGB(I_s), Δ=L(edited_crop)−L(original_aligned_crop), Δ_s=warp(M^-1,m·Δ); output=encode_sRGB(clamp(L_s+Δ_s)). This avoids replacing a high-resolution face with a resampled unedited crop at zero intensity. Gaussian support is bounded; outside support restore exact source bytes. Untargeted face protection multiplies Δ_s by0. Validity removes reflected out-of-frame crop pixels.

Poisson option solves min_f ∫_Ω||∇f−v||², with f|∂Ω=source|∂Ω; Euler condition Δf=div(v). Use cv2.seamlessClone for valid interior ROI and mask; source center must match warped mask bounds. Restrict outside-Ω pixels to source afterward. Poisson can change intended colors/texture, so alpha/delta is default. Quantify seams and reject edge ROI rather than silently paste wrong coordinates.

### Lifecycle and production invariants

Admission controls GPU concurrency, queue age and deadline. At-least-once work is deduplicated; Celery task ID is not a billing idempotency mechanism. Store job+reservation+outbox transactionally. Before read/submit/write and after write, check fence/tombstone/expiry. Purge race deletes any newly written object. Reconcile ambiguous billed submissions before retry; cancellation may not interrupt current CUDA work. Public portrait caches/automatic model downloads are prohibited. Readiness includes pinned weights/license approvals, warmup and expected providers—not just process liveness.

References: [InsightFace alignment source](https://github.com/deepinsight/insightface/blob/master/python-package/insightface/utils/face_align.py), [Reanimated3 compatibility](https://docs.swmansion.com/react-native-reanimated/docs/3.x/guides/compatibility/), [CUDA EP](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html), [OpenCV Poisson clone](https://docs.opencv.org/4.x/df/da0/group__photo__clone.html).

### Concrete control and training contracts

Age condition for a custom trained conditional export: `[target_age/100, intensity]`, with target_age=25/17/55/75. Expression conditioning is a versioned categorical one-hot over subtle/tooth/laugh plus calibrated strength; presentation is a versioned feminine/masculine one-hot plus strength. These vectors describe the proposed custom export, not a pretrained checkpoint's existing API. Hair RGB can be converted from the chosen hex using the model's documented color space; beard effective density=intensity; beauty effective smoothing=intensity×(options.skin_smoothing or manifest default0.4), makeup=intensity×(options.makeup or default0.2), using explicit null/missing checks so a user-supplied zero remains zero. Never use truthiness to replace numeric zero with defaults.

Normalized candidate objective for training/inversion: `L = L1(I,G(w)) + 0.8 LPIPS(I,G(w)) + 2(1−cos(eI,eG)) + 10 L_untargeted_landmarks + 20 L_outside_mask`. Normalize pixel/coordinate terms to[0,1]; landmarks use frame-normalized coordinates and exclude intentionally edited mouth/cheek targets. Coefficients are starting experiment settings, not validated release settings. Encoder/checkpoint licenses and identity-vector consent must be approved; do not compute eI by default merely to satisfy a loss formula. Evaluate texture/identity/locality independently because weighted scalar loss hides severe failures.

SDXL ControlNet is spatial conditioning; IP-Adapter FaceID is identity conditioning and is a different component. In masked denoising, preserve unedited latent regions at each step with `z_t = m_latent*z_t_candidate + (1−m_latent)*noise_scheduler(z_original,t,seed)`, respecting the actual inpaint pipeline's latent mask contract; final pixel compositing still enforces exact source outside the allowed mask. FLUX flow-matching needs its own scheduler/noise equations. CodeFormer fidelity setting0.8 is an optional starting benchmark candidate, disabled until licensed and tested; restoration must not change intended age texture. No extra face detection/registration is performed during blending.

Fast-preview Python stage budget is1.35s including optional0.1s restoration, matching the PRD stage allocation. Full-resolution blending is a distinct lane with a measured larger budget. The API does not magically reconstruct high-resolution source pixels from a small upload: a low-resolution preview asset returns that asset's resolution. Final original-resolution render requires uploading the full normalized source as a new owner-bound asset/job, binding newly detected face IDs and revisions while preserving chosen settings. Crop reuse across the two resolutions requires an explicit verified transform map and still-valid ephemeral data; otherwise rerun the approved model. This avoids claiming original-resolution exports from thumbnail-only requests.


## Model licenses and readiness



Register each deployed artifact with local path, SHA256, tensor layout, preprocess/class map, CUDA/ORT/Torch version, source URL, code license, weight license, commercial approval record, permitted purpose, VRAM and benchmark p95. `model-registry.json` deliberately starts without approved weights. There is no auto-download or random pretrained commercial authorization.

InsightFace code is MIT, but public pretrained packages generally require separate authorization for commercial deployment. The public IP-Adapter-FaceID model card identifies research-only use due to its dependencies. StyleGAN3 uses NVIDIA's source license; CodeFormer has NTU S-Lab terms. Thus these are research candidates until exact artifacts/dependencies are approved. FLUX licenses differ by model/version; do not treat “open weights” as sufficient. GFPGAN code/license and its dependencies/pretrained weights are separately checked. A licensed API is an alternative, but policy/retention/latency still require measurement.

| Candidate | Production default | Required evidence |
|---|---|---|
| SCRFD/RetinaFace detector | No weights enabled | Detector weight commercial approval, checksum, input/output tensor contract |
| BiSeNet face parser | No weights enabled | Parser/source dataset/model rights,19-class mapping and tensor verification |
| StyleGAN3 directions | Disabled | Inverter/directions exist, per-style training rights, license and quality |
| SDXL ControlNet + FaceID | Disabled | Every weight dependency licensed; research FaceID not auto-approved |
| FLUX inpaint | Disabled | Exact commercial artifact/service terms, supported conditioning/latency |
| CodeFormer/GFPGAN | Optional, disabled | Restoration fidelity/identity benchmark, model/dependency terms |
| Deterministic skin smoothing | Included internal module | Segmentation validated; boundary/texture quality review |

Primary references: [InsightFace licensing](https://www.insightface.ai/), [FaceID card](https://huggingface.co/h94/IP-Adapter-FaceID), [StyleGAN3](https://github.com/NVlabs/stylegan3), [CodeFormer](https://github.com/sczhou/CodeFormer), [GFPGAN](https://github.com/TencentARC/GFPGAN). These notes are a deployment gate, not a blanket legal conclusion about all possible licenses or an implemented model.


### `model-registry.json` — complete file

````json
{
  "version": 1,
  "status": "no production weights approved",
  "detector": {
    "path": null,
    "sha256": null,
    "commercial_approval_ref": null,
    "landmarks": 5
  },
  "parser": {
    "path": null,
    "sha256": null,
    "commercial_approval_ref": null,
    "input": "NCHW RGB ImageNet512",
    "classes": {
      "background": 0,
      "skin": 1,
      "eyes": [
        4,
        5
      ],
      "nose": 10,
      "mouth": 11,
      "lips": [
        12,
        13
      ],
      "hair": 17
    }
  },
  "generative_routes": {
    "age.onnx": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    },
    "expression.onnx": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    },
    "presentation.onnx": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    },
    "hair.onnx": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    },
    "beard.onnx": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    },
    "beauty.compose": {
      "path": null,
      "sha256": null,
      "commercial_approval_ref": null,
      "benchmarked_p95_ms": null,
      "ready": false
    }
  }
}

````


### `apps/inference-engine/requirements-gpu.txt` — complete file

````text
# Candidate bootstrap bounds; freeze on actual CUDA12/cuDNN-compatible GPU image.
numpy>=2.0,<2.3
opencv-python-headless==4.12.0.88
onnxruntime-gpu>=1.21,<2
torch>=2.6,<3
insightface==0.7.3
diffusers>=0.32,<1
transformers>=4.49,<5
accelerate>=1.4,<2
safetensors>=0.5,<1
Pillow>=11,<13

````


### `infra/triton/models/face_parser/config.pbtxt` — complete file

````protobuf
name: "face_parser"
platform: "onnxruntime_onnx"
max_batch_size: 4
input [{ name: "input" data_type: TYPE_FP32 dims: [3, 512, 512] }]
output [{ name: "logits" data_type: TYPE_FP32 dims: [19, 512, 512] }]
instance_group [{ count: 1 kind: KIND_GPU }]
dynamic_batching { preferred_batch_size: [1, 2, 4] max_queue_delay_microseconds: 2000 }
model_warmup [{ name: "parser_warmup" batch_size: 1
  inputs { key: "input" value { data_type: TYPE_FP32 dims: [3, 512, 512] zero_data: true } }
}]

````



Put an approved, checksummed ONNX parser in `models/face_parser/1/model.onnx` outside source control. This sample config requires tensor names `input`/`logits` and fixed19-class512 output. Adapt to the actual export; direct Python ONNX adapter is canonical for Phase1. No Triton model is runnable without weights. Explicit-load approved versions, warm each GPU execution instance, and admit requests only after readiness + measured warmup. Pin an NVIDIA Triton image digest compatible with the ORT/CUDA/cuDNN stack after testing; do not infer compatibility from “CUDA12” alone.

Never enable default unbounded dynamic batching. Queue delay2ms is a candidate to benchmark alongside p95 latency and peakVRAM. Triton is optional; keep orchestration/ownership/deletion checks in gateway/worker. Modal/RunPod are deployment alternatives using the same adapter contract, not three simultaneously required inference layers.

Source: [Triton model configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html).

# 3. Complete Directory Structure



```text
FaceApp-Production-Spec-v2/
|-- apps/
|   |-- api-server/
|   |   |-- Dockerfile
|   |   |-- celery_config.py
|   |   |-- main.py
|   |   +-- requirements.txt
|   |-- inference-engine/
|   |   |-- inference_pipeline.py
|   |   |-- model_adapters.py
|   |   +-- requirements-gpu.txt
|   |-- mobile/
|   |   |-- src/
|   |   |   +-- editor-binding.ts
|   |   |-- App.tsx
|   |   |-- app.json
|   |   |-- babel.config.cjs
|   |   |-- package.json
|   |   +-- tsconfig.json
|   +-- web-admin/
|       |-- app/
|       |   |-- layout.tsx
|       |   +-- page.tsx
|       |-- next-env.d.ts
|       |-- package.json
|       +-- tsconfig.json
|-- assets/
|   |-- backgrounds/
|   |   |-- cool-sky.svg
|   |   |-- cream.svg
|   |   |-- forest.svg
|   |   |-- midnight.svg
|   |   |-- rose-mist.svg
|   |   |-- studio-slate.svg
|   |   |-- studio-violet.svg
|   |   +-- warm-sand.svg
|   |-- brand/
|   |   |-- EXPORT_RECIPE.md
|   |   |-- app-icon-source.svg
|   |   |-- mark.svg
|   |   +-- wordmark.svg
|   |-- demo/
|   |   |-- PROVENANCE.md
|   |   +-- portrait-original.png
|   |-- fonts/
|   |   |-- Inter-variable.ttf
|   |   +-- OFL.txt
|   |-- icons/
|   |   |-- age.svg
|   |   |-- back.svg
|   |   |-- background.svg
|   |   |-- beard.svg
|   |   |-- blur.svg
|   |   |-- brightness.svg
|   |   |-- brush.svg
|   |   |-- camera.svg
|   |   |-- check-circle.svg
|   |   |-- check.svg
|   |   |-- chevron-right.svg
|   |   |-- close.svg
|   |   |-- cloud.svg
|   |   |-- compare.svg
|   |   |-- contrast.svg
|   |   |-- crop.svg
|   |   |-- crown.svg
|   |   |-- dots.svg
|   |   |-- download.svg
|   |   |-- eraser.svg
|   |   |-- eye.svg
|   |   |-- face.svg
|   |   |-- faces.svg
|   |   |-- flip.svg
|   |   |-- folder.svg
|   |   |-- glasses.svg
|   |   |-- hair-color.svg
|   |   |-- hair-volume.svg
|   |   |-- hair.svg
|   |   |-- heart.svg
|   |   |-- help.svg
|   |   |-- history.svg
|   |   |-- image.svg
|   |   |-- info.svg
|   |   |-- layers.svg
|   |   |-- lips.svg
|   |   |-- lock.svg
|   |   |-- magic-wand.svg
|   |   |-- makeup.svg
|   |   |-- menu.svg
|   |   |-- minus.svg
|   |   |-- offline.svg
|   |   |-- plus.svg
|   |   |-- preset.svg
|   |   |-- redo.svg
|   |   |-- refresh.svg
|   |   |-- rotate.svg
|   |   |-- saturation.svg
|   |   |-- save.svg
|   |   |-- settings.svg
|   |   |-- share.svg
|   |   |-- shield.svg
|   |   |-- skin.svg
|   |   |-- sliders.svg
|   |   |-- smile.svg
|   |   |-- sparkle.svg
|   |   |-- star.svg
|   |   |-- temperature.svg
|   |   |-- trash.svg
|   |   |-- undo.svg
|   |   |-- warning.svg
|   |   +-- zoom.svg
|   |-- luts/
|   |   |-- README.md
|   |   |-- balanced-mono.cube
|   |   |-- cool-clean.cube
|   |   |-- muted-film.cube
|   |   +-- soft-warm.cube
|   |-- ASSET_LICENSES.md
|   |-- design-tokens.json
|   +-- filters.json
|-- docs/
|   |-- 01_PRD.md
|   |-- 02_ARCHITECTURE_AND_MATH.md
|   |-- 03_API_AND_DATABASE.md
|   |-- 04_PRIVACY_PURGE.md
|   |-- 05_MODEL_REGISTRY_AND_LICENSES.md
|   |-- 06_ASSETS_AND_UX.md
|   |-- 07_RESEARCH_SOURCES.md
|   |-- DIRECTORY_TREE.md
|   |-- migration_constraints.sql
|   |-- openapi.json
|   |-- openapi.yaml
|   +-- schema.prisma
|-- infra/
|   +-- triton/
|       |-- models/
|       |   +-- face_parser/
|       |       |-- 1/
|       |       |   +-- README.md
|       |       +-- config.pbtxt
|       +-- README.md
|-- packages/
|   +-- shared-types/
|       |-- json-schema/
|       |   |-- AssetReceipt.json
|       |   |-- DeletionReceipt.json
|       |   |-- JobPayload.json
|       |   |-- SafeError.json
|       |   |-- TransformRequest.json
|       |   |-- UploadComplete.json
|       |   |-- UploadGrant.json
|       |   +-- UploadRequest.json
|       |-- index.ts
|       |-- package.json
|       |-- schemas.py
|       +-- tsconfig.json
|-- scripts/
|   |-- generate_contracts.py
|   |-- package_project.py
|   +-- static_check.py
|-- tests/
|   |-- test_contracts.py
|   +-- test_pipeline.py
|-- .env.example
|-- .gitignore
|-- CHATGPT_COLLECTION_PROMPT.md
|-- CLAUDE.md
|-- MANIFEST.json
|-- Makefile
|-- PROJECT_SPECIFICATION.md
|-- README.md
|-- VALIDATION_REPORT.md
|-- docker-compose.yml
|-- model-registry.json
|-- package.json
|-- pyproject.toml
|-- requirements-dev.txt
+-- tsconfig.base.json
```

No model weights are bundled. Native UI/backend integrations are implementation phases; this tree lists real supplied files. Transient dependencies/caches are excluded.


### `docker-compose.yml` — complete file

````yaml
# Local development only. Production uses secret manager, private network/TLS,
# pinned image digests, approved models and implemented Runtime/worker/purge.
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: portraitlab
      POSTGRES_USER: portraitlab
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set development database password}
    ports: ["127.0.0.1:5432:5432"]
    volumes: ["pg_metadata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U portraitlab -d portraitlab"]
      interval: 5s
      timeout: 3s
      retries: 10
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["127.0.0.1:6379:6379"]
    volumes: ["redis_metadata:/data"]
  minio:
    image: minio/minio:RELEASE.2025-04-22T22-12-26Z
    command: server /data --console-address :9001
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY:?Set development storage user}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY:?Set development storage secret}
    ports: ["127.0.0.1:9000:9000", "127.0.0.1:9001:9001"]
    # Ephemeral images on tmpfs; no backup/history. Does not replace per-job purge.
    tmpfs: ["/data:size=512m"]
  api:
    build:
      context: .
      dockerfile: apps/api-server/Dockerfile
    ports: ["127.0.0.1:8000:8000"]
    environment:
      DATABASE_URL: postgresql://portraitlab:${POSTGRES_PASSWORD}@postgres:5432/portraitlab
      REDIS_URL: redis://redis:6379/0
      S3_INTERNAL_ENDPOINT: http://minio:9000
      S3_PUBLIC_ENDPOINT: http://localhost:9000
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_started}
      minio: {condition: service_started}
volumes:
  pg_metadata:
  redis_metadata:

````


### `.env.example` — complete file

````dotenv
APP_ENV=development
API_PORT=8000
DATABASE_URL=postgresql://portraitlab:dev_only_change_me@localhost:5432/portraitlab
REDIS_URL=redis://localhost:6379/0
S3_INTERNAL_ENDPOINT=http://minio:9000
S3_PUBLIC_ENDPOINT=http://localhost:9000
S3_BUCKET=portraitlab-ephemeral
S3_ACCESS_KEY=dev_only_change_me
S3_SECRET_KEY=dev_only_change_me_long_secret
JWT_ISSUER=
JWT_AUDIENCE=
JWT_JWKS_URL=
MODEL_REGISTRY_PATH=/models/model-registry.json
CUDA_VISIBLE_DEVICES=0
WARM_MIN_REPLICAS=1
MAX_UPLOAD_BYTES=10485760
MAX_DECODED_PIXELS=24000000
SOURCE_PURGE_TARGET_SECONDS=30
RESULT_DELIVERY_SECONDS=300
ABSOLUTE_IMAGE_TTL_SECONDS=600
PURGE_INTERVAL_SECONDS=5
PUBLIC_API_BASE_URL=http://localhost:8000
# Production keys/identities must come from secret manager, not this template.
POSTGRES_PASSWORD=dev_only_change_me

````


### `package.json` — complete file

````json
{
  "name": "portraitlab-production-scaffold",
  "private": true,
  "workspaces": [
    "apps/mobile",
    "apps/web-admin",
    "packages/shared-types"
  ],
  "scripts": {
    "build": "make build",
    "test": "make test",
    "dev": "make dev",
    "lint": "make lint",
    "docker:up": "make docker-up"
  }
}

````


### `Makefile` — complete file

````makefile
PYTHON ?= .venv/bin/python
SHARED := $(CURDIR)/packages/shared-types
.PHONY: build test dev lint docker-up dev-mobile dev-web contracts
build: contracts
	$(PYTHON) scripts/static_check.py
	npm run build --workspace=@portraitlab/shared-types
	npm run build --workspace=@portraitlab/mobile
	npm run build --workspace=@portraitlab/web-admin
test:
	PYTHONPATH=$(SHARED) $(PYTHON) -m unittest discover -s tests -v
dev:
	cd apps/api-server && PYTHONPATH=$(SHARED) ../../.venv/bin/python -m uvicorn main:app --reload --port 8000
dev-mobile:
	npm run dev --workspace=@portraitlab/mobile
dev-web:
	npm run dev --workspace=@portraitlab/web-admin
lint:
	$(PYTHON) -m ruff check apps/inference-engine apps/api-server packages/shared-types scripts tests
	npm run lint --workspaces
docker-up:
	docker compose --env-file .env up --build -d
contracts:
	PYTHONPATH=$(SHARED) $(PYTHON) scripts/generate_contracts.py

````


### `tsconfig.base.json` — complete file

````json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "target": "ES2022"
  }
}

````


### `apps/mobile/package.json` — complete file

````json
{
  "name": "@portraitlab/mobile",
  "private": true,
  "scripts": {
    "dev": "expo start --dev-client",
    "build": "tsc --noEmit",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "expo": "~53.0.0",
    "react": "19.0.0",
    "react-native": "0.79.5",
    "react-native-reanimated": "3.17.5",
    "@shopify/react-native-skia": "2.0.0",
    "react-native-vision-camera": "4.6.4",
    "expo-dev-client": "~5.2.0",
    "expo-image-picker": "~16.1.0",
    "expo-file-system": "~18.1.0",
    "expo-sharing": "~13.1.0"
  },
  "devDependencies": {
    "typescript": "~5.8.3",
    "@types/react": "~19.0.0"
  }
}

````


### `apps/mobile/app.json` — complete file

````json
{
  "expo": {
    "name": "PortraitLab",
    "slug": "portraitlab",
    "version": "0.1.0",
    "newArchEnabled": true,
    "ios": {
      "supportsTablet": false
    },
    "plugins": [
      [
        "react-native-vision-camera",
        {
          "cameraPermissionText": "Use your camera when you choose to take a portrait.",
          "enableMicrophonePermission": false
        }
      ],
      [
        "expo-image-picker",
        {
          "photosPermission": "Choose a photo to edit.",
          "microphonePermission": false
        }
      ]
    ]
  }
}

````


### `apps/mobile/babel.config.cjs` — complete file

````javascript
module.exports = function(api){api.cache(true);return {presets:['babel-preset-expo'],plugins:['react-native-reanimated/plugin']};};

````


### `apps/web-admin/package.json` — complete file

````json
{
  "name": "@portraitlab/web-admin",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "next": "^16.4.0",
    "react": "^19.3.0",
    "react-dom": "^19.3.0"
  },
  "devDependencies": {
    "typescript": "~5.8.3",
    "@types/react": "~19.0.0",
    "@types/react-dom": "~19.0.0",
    "@types/node": "^22.0.0"
  }
}

````


### `apps/api-server/Dockerfile` — complete file

````dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY apps/api-server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/shared-types /app/shared-types
COPY apps/api-server /app
ENV PYTHONPATH=/app/shared-types
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

````

# 4. API Contract & Database Schema



`openapi.json` is a complete OpenAPI3.1 document generated from the FastAPI source and Pydantic2 models. JSON is accepted directly by Swagger/OpenAPI tools. All portrait routes require Bearer JWT; issuer/audience/signature/expiration verification belongs to the Runtime implementation. `result_cdn_url` retains the requested field name but means a short-lived authenticated private media grant with no shared cache. No public CDN portraits.

### Upload and transform

1. POST `/api/v1/faces/upload-url`: verify current owner-bound consent; allocate a random server-owned asset prefix and absolute10min deadline. Accept JPEG/PNG/HEIC up to10MiB; source decoded limit24MP. Return201 with a PUT URL valid60sec and exact required checksum/content-type headers. Enforce provider-supported signed content-length or final HEAD/stream validation and promptly delete oversized uploads; browser fetch cannot set forbidden Content-Length headers.
2. PUT bytes directly to the given URL. Never use client-supplied arbitrary object keys or remote image URLs. Bind expected SHA256 through S3 checksum signing; hex request hash converts to provider base64 checksum. An ETag is not SHA256. MinIO compatibility is an integration test.
3. POST `/uploads/{asset_id}/complete` after PUT: ownership check, HEAD/stream actual byte/type/hash verification, hardened decoder, EXIF orientation, ICC conversion to sRGB, EXIF/GPS stripping, pixel limit, detection. Return opaque face IDs bound to this asset/detection revision; IDs never identify people. Keep spatial metadata in expiring secured runtime storage, not permanent recognition profiles. No uploaded asset is usable before finalizedAt.
4. POST `/transform` with `Idempotency-Key`. Pydantic rejects unknown fields, NaN, booleans masquerading as numeric strength, unsupported presets and incompatible options. Server rejects missing/expired/non-owned face/asset/consent and blocked model. Source/candidate revisions prevent stale display; they are not authorization.
5. GET `/jobs/{job_id}?wait_seconds=25&after_revision=3`: return immediately if current event_revision>3 or terminal, otherwise wait up to25sec without holding a database connection/transaction. Return latest snapshot on timeout200. Token expiry/disconnection cancels waiter, not the job. UI uses jittered backoff and one pending poll/job. Optional WebSocket messages use exactly JobPayload plus monotonic event_revision; WebSocket transport is not implemented here.
6. Cancel returns202 cancel_requested when executing. Deletion202 means accepted; keep checking status until complete. Tombstone/revoke reads before asynchronous byte deletion; unavailable storage yields partial_failure, never an invented complete receipt.

### Representative transform request

```json
{"asset_id":"00000000-0000-4000-8000-000000000001","face_id":"00000000-0000-4000-8000-000000000002","filter_type":"age_50s","intensity":0.35,"preserve_background":true,"source_revision":0,"candidate_revision":1,"options":{}}
```

### State machine and safe errors

QUEUED→RUNNING→SUCCEEDED|FAILED; QUEUED/RUNNING→CANCEL_REQUESTED→CANCELED; live/terminal states→EXPIRED/PURGED when due. A tombstoned/purged job can never return to live state. Every change increments event_revision in the same transaction. `progress_percent=null` + indeterminate is honest unknown progress; measured_steps can expose actual denoising iteration count, not fabricated wall-time percentages. Only completed processing uses100. All response snapshots bind job_id,asset_id,face_id,source_revision,candidate_revision.

Errors:401 unauthenticated; owner-mismatched IDs return404;403 policy denied;409 request key/body conflict or stale source;410 asset expired/purged;422 bad input/no face/unsupported pose;429 insufficient admission quota;503 worker cold/filter unavailable. Safe envelope code/message/retryable/request_id; never expose model stack traces, object keys, tokens, input bytes or presigned URLs in logs. Insufficient credits uses402 with CREDIT_REQUIRED; add this to routes when paid Runtime is enabled. Rate limits begin at5 grants/min/user,2 pending transforms/user,20 status requests/min/user; tune after load testing.

### PostgreSQL / Prisma

`schema.prisma` uses explicitly versioned Prisma6 syntax (Prisma7 configuration differs). Core requested User/ImageJob/FilterPreset/CreditTransaction/AuditLog are joined by ConsentReceipt/UploadAsset/CreditWallet/OutboxEvent to close consent/ownership/billing races. `migration_constraints.sql` adds raw CHECKs, composite owner FKs and partial indexes Prisma does not express. Apply it after generated base migration. Never rely only on application enum/number constraints. Final production migrations must be reviewed/tested on PostgreSQL16.

Wallet balance is spendable total, reserved is in-flight encumbrance, available=balance-reserved. GRANT amount=+units; RESERVE/RELEASE amount=0; SETTLE amount=-units; REFUND amount=+units. Append ledger; don't mutate historical credit transactions. Monetary purchase receipts are separate store records before granting units. No portrait bytes/landmarks/recognition vectors in AuditLog; metadata allowlist={safe_code,manifest_version,worker_version,duration_bucket,deletion_status}.

### Atomic creation and credit reservation

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

### Implementation status

API source is an executable contract/health shell. Runtime auth/storage/repository/queue/billing/purge integrations deliberately return503 until implemented. It is not a finished production backend. User/job examples and generated schemas are real contracts; no payment processor credentials or commercial AI weights are supplied.


### `docs/openapi.yaml` — complete file

````yaml
openapi: 3.1.0
info:
  title: PortraitLab Faces API
  description: Production design contract; service Runtime repositories are not implemented
    in this scaffold.
  version: 2.0.0
paths:
  /health:
    get:
      tags:
      - health
      summary: Health
      operationId: health_health_get
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema: {}
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
  /api/v1/faces/upload-url:
    post:
      tags:
      - faces
      summary: Upload Url
      operationId: upload_url_api_v1_faces_upload_url_post
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UploadRequest'
        required: true
      responses:
        '201':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UploadGrant'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
      security:
      - HTTPBearer: []
  /api/v1/faces/uploads/{asset_id}/complete:
    post:
      tags:
      - faces
      summary: Complete Upload
      operationId: complete_upload_api_v1_faces_uploads__asset_id__complete_post
      security:
      - HTTPBearer: []
      parameters:
      - name: asset_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
          title: Asset Id
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UploadComplete'
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssetReceipt'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
  /api/v1/faces/transform:
    post:
      tags:
      - faces
      summary: Transform
      operationId: transform_api_v1_faces_transform_post
      security:
      - HTTPBearer: []
      parameters:
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          type: string
          minLength: 16
          maxLength: 128
          title: Idempotency-Key
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TransformRequest'
      responses:
        '202':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobPayload'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
  /api/v1/faces/jobs/{job_id}:
    get:
      tags:
      - faces
      summary: Job Status
      operationId: job_status_api_v1_faces_jobs__job_id__get
      security:
      - HTTPBearer: []
      parameters:
      - name: job_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
          title: Job Id
      - name: wait_seconds
        in: query
        required: false
        schema:
          type: integer
          maximum: 25
          minimum: 0
          default: 0
          title: Wait Seconds
      - name: after_revision
        in: query
        required: false
        schema:
          type: integer
          minimum: 0
          default: 0
          title: After Revision
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobPayload'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
  /api/v1/faces/jobs/{job_id}/cancel:
    post:
      tags:
      - faces
      summary: Cancel Job
      operationId: cancel_job_api_v1_faces_jobs__job_id__cancel_post
      security:
      - HTTPBearer: []
      parameters:
      - name: job_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
          title: Job Id
      responses:
        '202':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobPayload'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
  /api/v1/faces/jobs/{job_id}/data:
    delete:
      tags:
      - faces
      summary: Delete Job Data
      operationId: delete_job_data_api_v1_faces_jobs__job_id__data_delete
      security:
      - HTTPBearer: []
      parameters:
      - name: job_id
        in: path
        required: true
        schema:
          type: string
          format: uuid
          title: Job Id
      responses:
        '202':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeletionReceipt'
        '401':
          description: Authentication required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '402':
          description: Credits required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '403':
          description: Permission denied
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '404':
          description: Resource not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '409':
          description: Conflict or idempotency mismatch
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '410':
          description: Expired or purged
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '422':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '429':
          description: Admission limit
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '500':
          description: Internal error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
        '503':
          description: Service or filter unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SafeError'
components:
  schemas:
    AssetReceipt:
      properties:
        asset_id:
          type: string
          format: uuid
          title: Asset Id
        normalized_width:
          type: integer
          maximum: 24000.0
          minimum: 1.0
          title: Normalized Width
        normalized_height:
          type: integer
          maximum: 24000.0
          minimum: 1.0
          title: Normalized Height
        faces:
          items:
            type: string
            format: uuid
          type: array
          maxItems: 8
          title: Faces
        expires_at:
          type: string
          format: date-time
          title: Expires At
      additionalProperties: false
      type: object
      required:
      - asset_id
      - normalized_width
      - normalized_height
      - faces
      - expires_at
      title: AssetReceipt
    DeletionReceipt:
      properties:
        job_id:
          type: string
          format: uuid
          title: Job Id
        status:
          type: string
          enum:
          - requested
          - deleting
          - complete
          - partial_failure
          title: Status
        requested_at:
          type: string
          format: date-time
          title: Requested At
      additionalProperties: false
      type: object
      required:
      - job_id
      - status
      - requested_at
      title: DeletionReceipt
    JobPayload:
      properties:
        job_id:
          type: string
          format: uuid
          title: Job Id
        asset_id:
          type: string
          format: uuid
          title: Asset Id
        face_id:
          type: string
          format: uuid
          title: Face Id
        source_revision:
          type: integer
          minimum: 0.0
          title: Source Revision
        candidate_revision:
          type: integer
          minimum: 0.0
          title: Candidate Revision
        status:
          type: string
          enum:
          - queued
          - running
          - succeeded
          - failed
          - cancel_requested
          - canceled
          - expired
          - purged
          title: Status
        stage:
          type: string
          enum:
          - queued
          - decode
          - detect
          - align
          - parse
          - transform
          - restore
          - blend
          - encode
          - deliver
          - done
          title: Stage
        event_revision:
          type: integer
          minimum: 0.0
          title: Event Revision
        progress_percent:
          anyOf:
          - type: number
            maximum: 100.0
            minimum: 0.0
          - type: 'null'
          title: Progress Percent
        progress_source:
          type: string
          enum:
          - indeterminate
          - measured_steps
          - complete
          title: Progress Source
          default: indeterminate
        result_cdn_url:
          anyOf:
          - type: string
          - type: 'null'
          title: Result Cdn Url
        result_expires_at:
          anyOf:
          - type: string
            format: date-time
          - type: 'null'
          title: Result Expires At
        error:
          anyOf:
          - $ref: '#/components/schemas/SafeError'
          - type: 'null'
        created_at:
          type: string
          format: date-time
          title: Created At
        updated_at:
          type: string
          format: date-time
          title: Updated At
      additionalProperties: false
      type: object
      required:
      - job_id
      - asset_id
      - face_id
      - source_revision
      - candidate_revision
      - status
      - stage
      - event_revision
      - created_at
      - updated_at
      title: JobPayload
    Options:
      properties:
        color_hex:
          anyOf:
          - type: string
            pattern: ^#[0-9a-fA-F]{6}$
          - type: 'null'
          title: Color Hex
        skin_smoothing:
          anyOf:
          - type: number
            maximum: 1.0
            minimum: 0.0
          - type: 'null'
          title: Skin Smoothing
        makeup:
          anyOf:
          - type: number
            maximum: 1.0
            minimum: 0.0
          - type: 'null'
          title: Makeup
      additionalProperties: false
      type: object
      title: Options
    SafeError:
      properties:
        code:
          type: string
          title: Code
        message:
          type: string
          title: Message
        retryable:
          type: boolean
          title: Retryable
        request_id:
          type: string
          format: uuid
          title: Request Id
      additionalProperties: false
      type: object
      required:
      - code
      - message
      - retryable
      - request_id
      title: SafeError
    TransformRequest:
      properties:
        asset_id:
          type: string
          format: uuid
          title: Asset Id
        face_id:
          type: string
          format: uuid
          title: Face Id
        filter_type:
          type: string
          enum:
          - age_young
          - age_teen
          - age_50s
          - age_70s
          - smile_subtle
          - smile_tooth
          - laugh
          - gender_feminine
          - gender_masculine
          - hair_color
          - beard_density
          - beauty_retouch
          title: Filter Type
        intensity:
          type: number
          maximum: 1.0
          minimum: 0.0
          title: Intensity
        preserve_background:
          type: boolean
          title: Preserve Background
          default: true
        source_revision:
          type: integer
          minimum: 0.0
          title: Source Revision
        candidate_revision:
          type: integer
          minimum: 0.0
          title: Candidate Revision
        options:
          $ref: '#/components/schemas/Options'
      additionalProperties: false
      type: object
      required:
      - asset_id
      - face_id
      - filter_type
      - intensity
      - source_revision
      - candidate_revision
      title: TransformRequest
    UploadComplete:
      properties:
        checksum_sha256:
          type: string
          pattern: ^[0-9a-f]{64}$
          title: Checksum Sha256
      additionalProperties: false
      type: object
      required:
      - checksum_sha256
      title: UploadComplete
    UploadGrant:
      properties:
        asset_id:
          type: string
          format: uuid
          title: Asset Id
        upload_url:
          type: string
          title: Upload Url
        method:
          type: string
          const: PUT
          title: Method
          default: PUT
        required_headers:
          additionalProperties:
            type: string
          type: object
          title: Required Headers
        expires_at:
          type: string
          format: date-time
          title: Expires At
        absolute_purge_at:
          type: string
          format: date-time
          title: Absolute Purge At
      additionalProperties: false
      type: object
      required:
      - asset_id
      - upload_url
      - required_headers
      - expires_at
      - absolute_purge_at
      title: UploadGrant
    UploadRequest:
      properties:
        mime_type:
          type: string
          enum:
          - image/jpeg
          - image/png
          - image/heic
          title: Mime Type
        byte_length:
          type: integer
          maximum: 10485760.0
          minimum: 1.0
          title: Byte Length
        checksum_sha256:
          type: string
          pattern: ^[0-9a-f]{64}$
          title: Checksum Sha256
        consent_receipt_id:
          type: string
          format: uuid
          title: Consent Receipt Id
      additionalProperties: false
      type: object
      required:
      - mime_type
      - byte_length
      - checksum_sha256
      - consent_receipt_id
      title: UploadRequest
  securitySchemes:
    HTTPBearer:
      type: http
      scheme: bearer
servers:
- url: http://localhost:8000
  description: Local development
- url: https://api.example.invalid
  description: Replace with deployed TLS API

````


### `packages/shared-types/schemas.py` — complete file

````python
"""Authoritative wire schemas; runtime ownership/billing checks remain mandatory."""

from __future__ import annotations
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, AwareDatetime, model_validator

FilterId = Literal[
    "age_young",
    "age_teen",
    "age_50s",
    "age_70s",
    "smile_subtle",
    "smile_tooth",
    "laugh",
    "gender_feminine",
    "gender_masculine",
    "hair_color",
    "beard_density",
    "beauty_retouch",
]
JobState = Literal["queued", "running", "succeeded", "failed", "cancel_requested", "canceled", "expired", "purged"]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Options(WireModel):
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    skin_smoothing: StrictFloat | None = Field(default=None, ge=0, le=1)
    makeup: StrictFloat | None = Field(default=None, ge=0, le=1)


class UploadRequest(WireModel):
    mime_type: Literal["image/jpeg", "image/png", "image/heic"]
    byte_length: StrictInt = Field(ge=1, le=10_485_760)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consent_receipt_id: UUID


class UploadGrant(WireModel):
    asset_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: AwareDatetime
    absolute_purge_at: AwareDatetime


class UploadComplete(WireModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssetReceipt(WireModel):
    asset_id: UUID
    normalized_width: StrictInt = Field(ge=1, le=24000)
    normalized_height: StrictInt = Field(ge=1, le=24000)
    faces: list[UUID] = Field(max_length=8)
    expires_at: AwareDatetime


class TransformRequest(WireModel):
    asset_id: UUID
    face_id: UUID
    filter_type: FilterId
    intensity: StrictFloat = Field(ge=0, le=1)
    preserve_background: StrictBool = True
    source_revision: StrictInt = Field(ge=0)
    candidate_revision: StrictInt = Field(ge=0)
    options: Options = Field(default_factory=Options)

    @model_validator(mode="after")
    def check_options(self):
        if self.options.color_hex is not None and self.filter_type != "hair_color":
            raise ValueError("color_hex only applies to hair_color")
        if (
            self.options.makeup is not None or self.options.skin_smoothing is not None
        ) and self.filter_type != "beauty_retouch":
            raise ValueError("beauty parameters only apply to beauty_retouch")
        return self


class SafeError(WireModel):
    code: str
    message: str
    retryable: StrictBool
    request_id: UUID


class JobPayload(WireModel):
    job_id: UUID
    asset_id: UUID
    face_id: UUID
    source_revision: StrictInt = Field(ge=0)
    candidate_revision: StrictInt = Field(ge=0)
    status: JobState
    stage: Literal[
        "queued", "decode", "detect", "align", "parse", "transform", "restore", "blend", "encode", "deliver", "done"
    ]
    event_revision: StrictInt = Field(ge=0)
    progress_percent: StrictFloat | None = Field(default=None, ge=0, le=100)
    progress_source: Literal["indeterminate", "measured_steps", "complete"] = "indeterminate"
    result_cdn_url: str | None = None
    result_expires_at: AwareDatetime | None = None
    error: SafeError | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def check_result_and_progress(self):
        if self.result_cdn_url is not None and self.status != "succeeded":
            raise ValueError("Only succeeded jobs may have a result grant")
        if (self.result_cdn_url is None) != (self.result_expires_at is None):
            raise ValueError("Result URL and expiration must occur together")
        if self.progress_source == "indeterminate" and self.progress_percent is not None:
            raise ValueError("Unknown progress must be null")
        if self.progress_source == "complete" and self.progress_percent != 100.0:
            raise ValueError("Complete progress must be 100")
        return self


class DeletionReceipt(WireModel):
    job_id: UUID
    status: Literal["requested", "deleting", "complete", "partial_failure"]
    requested_at: AwareDatetime

````


### `packages/shared-types/index.ts` — complete file

````typescript
// Wire declarations. JSON Schema/Pydantic remains runtime validation authority.
export type FilterId = 'age_young'|'age_teen'|'age_50s'|'age_70s'|'smile_subtle'|'smile_tooth'|'laugh'|'gender_feminine'|'gender_masculine'|'hair_color'|'beard_density'|'beauty_retouch';
export type JobState = 'queued'|'running'|'succeeded'|'failed'|'cancel_requested'|'canceled'|'expired'|'purged';
export interface Options { color_hex?: string|null; skin_smoothing?: number|null; makeup?: number|null; }
export interface TransformRequest { asset_id:string; face_id:string; filter_type:FilterId; intensity:number; preserve_background?:boolean; source_revision:number; candidate_revision:number; options?:Options; }
export interface UploadRequest { mime_type:'image/jpeg'|'image/png'|'image/heic'; byte_length:number; checksum_sha256:string; consent_receipt_id:string; }
export interface UploadGrant { asset_id:string; upload_url:string; method:'PUT'; required_headers:Record<string,string>; expires_at:string; absolute_purge_at:string; }
export interface UploadComplete {checksum_sha256:string}
export interface AssetReceipt {asset_id:string; normalized_width:number; normalized_height:number; faces:string[]; expires_at:string}
export interface SafeError {code:string; message:string; retryable:boolean; request_id:string}
export interface JobPayload {job_id:string; asset_id:string; face_id:string; source_revision:number; candidate_revision:number; status:JobState; stage:'queued'|'decode'|'detect'|'align'|'parse'|'transform'|'restore'|'blend'|'encode'|'deliver'|'done'; event_revision:number; progress_percent?:number|null; progress_source?:'indeterminate'|'measured_steps'|'complete'; result_cdn_url?:string|null; result_expires_at?:string|null; error?:SafeError|null; created_at:string; updated_at:string}
export interface DeletionReceipt {job_id:string;status:'requested'|'deleting'|'complete'|'partial_failure';requested_at:string}
// Runtime cross-field constraints (options compatibility, result grants, progress) are
// enforced by Pydantic. Generate schema-derived TS types before expanding this API.

````


### `docs/schema.prisma` — complete file

````prisma
// Prisma v6 schema syntax. Use CLI v6 for this file; v7+ config differs.
// Python gateway uses database adapters; Prisma is migration/schema tooling here.
generator client {
  provider = "prisma-client-js"
}
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
enum JobStatus {
  QUEUED
  RUNNING
  SUCCEEDED
  FAILED
  CANCEL_REQUESTED
  CANCELED
  EXPIRED
  PURGED
}
enum CreditKind {
  GRANT
  RESERVE
  SETTLE
  RELEASE
  REFUND
}
model User {
  id                 String              @id @default(uuid()) @db.Uuid
  externalSubject    String              @unique @db.VarChar(255)
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  deletedAt          DateTime?           @db.Timestamptz(6)
  jobs               ImageJob[]
  presets            FilterPreset[]
  credits            CreditTransaction[]
  audits             AuditLog[]
  uploads            UploadAsset[]
  consents           ConsentReceipt[]
  wallet             CreditWallet?
}
model ConsentReceipt {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String              @db.Uuid
  policyVersion      String              @db.VarChar(64)
  processorRegion    String              @db.VarChar(64)
  purpose            String              @db.VarChar(64)
  acceptedAt         DateTime            @db.Timestamptz(6)
  withdrawnAt        DateTime?           @db.Timestamptz(6)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
  uploads            UploadAsset[]
  @@unique([id,userId])
  @@index([userId,acceptedAt])
}
model UploadAsset {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String              @db.Uuid
  consentReceiptId   String              @db.Uuid
  objectPrefix       String?             @unique
  mimeType           String              @db.VarChar(32)
  byteLength         BigInt
  checksumSha256     String?             @db.Char(64)
  finalizedAt        DateTime?           @db.Timestamptz(6)
  expiresAt          DateTime            @db.Timestamptz(6)
  purgedAt           DateTime?           @db.Timestamptz(6)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
  consent            ConsentReceipt      @relation(fields:[consentReceiptId], references:[id], onDelete:Restrict)
  jobs               ImageJob[]
  @@unique([id,userId])
  @@index([expiresAt,purgedAt])
}
model ImageJob {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String              @db.Uuid
  assetId            String              @db.Uuid
  faceId             String              @db.Uuid
  filterType         String              @db.VarChar(48)
  intensity          Float
  preserveBackground Boolean             @default(true)
  parameters         Json
  sourceRevision     Int
  candidateRevision  Int
  eventRevision      Int                 @default(0)
  status             JobStatus           @default(QUEUED)
  idempotencyKey     String              @db.VarChar(128)
  requestHash        String              @db.Char(64)
  modelVersion       String?             @db.VarChar(128)
  reservedUnits      Int
  fence              Int                 @default(0)
  attemptCount       Int                 @default(0)
  leaseExpiresAt     DateTime?           @db.Timestamptz(6)
  resultObjectKey    String?
  resultExpiresAt    DateTime?           @db.Timestamptz(6)
  safeErrorCode      String?             @db.VarChar(64)
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  startedAt          DateTime?           @db.Timestamptz(6)
  completedAt        DateTime?           @db.Timestamptz(6)
  expiresAt          DateTime            @db.Timestamptz(6)
  tombstonedAt       DateTime?           @db.Timestamptz(6)
  deleteRequestedAt  DateTime?           @db.Timestamptz(6)
  purgeAttemptCount  Int                 @default(0)
  nextPurgeAt        DateTime?           @db.Timestamptz(6)
  purgedAt           DateTime?           @db.Timestamptz(6)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
  asset              UploadAsset         @relation(fields:[assetId], references:[id], onDelete:Restrict)
  credits            CreditTransaction[]
  audits             AuditLog[]
  @@unique([id,userId])
  @@unique([userId,idempotencyKey])
  @@index([userId,createdAt])
  @@index([status,expiresAt])
  @@index([tombstonedAt,purgedAt])
  @@index([leaseExpiresAt,status])
  @@index([nextPurgeAt,purgedAt])
}
model FilterPreset {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String              @db.Uuid
  name               String              @db.VarChar(80)
  manifestVersion    String              @db.VarChar(32)
  parameters         Json
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  updatedAt          DateTime            @updatedAt @db.Timestamptz(6)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
  @@unique([userId,name])
}
model CreditWallet {
  userId             String              @id @db.Uuid
  balance            Int                 @default(0)
  reserved           Int                 @default(0)
  version            Int                 @default(0)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
}
model CreditTransaction {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String              @db.Uuid
  jobId              String?             @db.Uuid
  kind               CreditKind
  amount             Int
  units              Int
  deduplicationKey   String              @unique @db.VarChar(160)
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  user               User                @relation(fields:[userId], references:[id], onDelete:Restrict)
  job                ImageJob?           @relation(fields:[jobId], references:[id], onDelete:Restrict)
  @@unique([jobId,kind])
  @@index([userId,createdAt])
}
model AuditLog {
  id                 String              @id @default(uuid()) @db.Uuid
  userId             String?             @db.Uuid
  jobId              String?             @db.Uuid
  action             String              @db.VarChar(64)
  requestId          String              @db.Uuid
  // Allowlisted safe metadata only; never image bytes, vectors, signed URLs or EXIF.
  safeMetadata       Json
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  user               User?               @relation(fields:[userId], references:[id], onDelete:Restrict)
  job                ImageJob?           @relation(fields:[jobId], references:[id], onDelete:Restrict)
  @@index([jobId,createdAt])
  @@index([userId,createdAt])
}
model OutboxEvent {
  id                 String              @id @default(uuid()) @db.Uuid
  aggregateId        String              @db.Uuid
  eventType          String              @db.VarChar(64)
  payload            Json
  createdAt          DateTime            @default(now()) @db.Timestamptz(6)
  dispatchedAt       DateTime?           @db.Timestamptz(6)
  @@index([dispatchedAt,createdAt])
}

````


### `docs/migration_constraints.sql` — complete file

````sql
-- Run AFTER a Prisma v6-generated baseline migration; not executed in this task.
ALTER TABLE "ImageJob" ADD CONSTRAINT job_intensity CHECK ("intensity" >= 0 AND "intensity" <= 1 AND "intensity" <> 'NaN'::float8);
ALTER TABLE "ImageJob" ADD CONSTRAINT job_revision CHECK ("sourceRevision" >= 0 AND "candidateRevision" >= 0 AND "eventRevision" >= 0 AND "fence" >= 0);
ALTER TABLE "ImageJob" ADD CONSTRAINT job_units CHECK ("reservedUnits" >= 0);
ALTER TABLE "CreditWallet" ADD CONSTRAINT wallet_nonnegative CHECK ("balance" >= 0 AND "reserved" >= 0 AND "reserved" <= "balance");
ALTER TABLE "CreditTransaction" ADD CONSTRAINT credit_units CHECK ("units" >= 0);
ALTER TABLE "CreditTransaction" ADD CONSTRAINT credit_sign CHECK (
  ("kind" IN ('GRANT','REFUND') AND "amount" = "units") OR
  ("kind" = 'SETTLE' AND "amount" = -"units") OR
  ("kind" IN ('RESERVE','RELEASE') AND "amount" = 0)
);
ALTER TABLE "UploadAsset" ADD CONSTRAINT upload_size CHECK ("byteLength" > 0 AND "byteLength" <= 10485760);
ALTER TABLE "ImageJob" ADD CONSTRAINT owned_source FOREIGN KEY ("assetId","userId") REFERENCES "UploadAsset"("id","userId");
ALTER TABLE "UploadAsset" ADD CONSTRAINT owned_consent FOREIGN KEY ("consentReceiptId","userId") REFERENCES "ConsentReceipt"("id","userId");
ALTER TABLE "CreditTransaction" ADD CONSTRAINT owned_credit_job FOREIGN KEY ("jobId","userId") REFERENCES "ImageJob"("id","userId");
ALTER TABLE "AuditLog" ADD CONSTRAINT owned_audit_job FOREIGN KEY ("jobId","userId") REFERENCES "ImageJob"("id","userId");
ALTER TABLE "ImageJob" ADD CONSTRAINT retry_counts CHECK ("attemptCount" >= 0 AND "purgeAttemptCount" >= 0);
ALTER TABLE "ImageJob" ADD CONSTRAINT known_filter CHECK ("filterType" IN ('age_young','age_teen','age_50s','age_70s','smile_subtle','smile_tooth','laugh','gender_feminine','gender_masculine','hair_color','beard_density','beauty_retouch'));
CREATE INDEX job_active_queue ON "ImageJob"("createdAt") WHERE "status" = 'QUEUED' AND "tombstonedAt" IS NULL;
CREATE INDEX outbox_undispatched ON "OutboxEvent"("createdAt") WHERE "dispatchedAt" IS NULL;
-- RLS policies or strict service-layer ownership remain required for every read.
-- AuditLog with userId=NULL is service audit, never a privileged photo data grant.

````


### `apps/api-server/main.py` — complete file

````python
"""Executable API contract shell. Inject an implemented Runtime to enable routes.

Default fails closed with503. No fake queue/database/auth/paid success is supplied.
"""

from __future__ import annotations
from typing import Annotated, Protocol
from uuid import UUID, uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from schemas import (
    UploadRequest,
    UploadGrant,
    UploadComplete,
    AssetReceipt,
    TransformRequest,
    JobPayload,
    SafeError,
    DeletionReceipt,
)


class Runtime(Protocol):
    async def authenticate(self, token: str) -> UUID: ...
    async def upload(self, owner: UUID, body: UploadRequest) -> UploadGrant: ...
    async def complete(self, owner: UUID, asset_id: UUID, body: UploadComplete) -> AssetReceipt: ...
    async def transform(self, owner: UUID, body: TransformRequest, idempotency_key: str) -> JobPayload: ...
    async def status(self, owner: UUID, job_id: UUID, wait_seconds: int, after_revision: int) -> JobPayload: ...
    async def cancel(self, owner: UUID, job_id: UUID) -> JobPayload: ...
    async def delete(self, owner: UUID, job_id: UUID) -> DeletionReceipt: ...


app = FastAPI(
    title="PortraitLab Faces API",
    version="2.0.0",
    openapi_version="3.1.0",
    description="Production design contract; service Runtime repositories are not implemented in this scaffold.",
)
app.state.runtime = None
security = HTTPBearer(auto_error=False)
app.router.responses.update(
    {
        code: {"model": SafeError, "description": description}
        for code, description in {
            401: "Authentication required",
            402: "Credits required",
            403: "Permission denied",
            404: "Resource not found",
            409: "Conflict or idempotency mismatch",
            410: "Expired or purged",
            422: "Invalid request",
            429: "Admission limit",
            500: "Internal error",
            503: "Service or filter unavailable",
        }.items()
    }
)


@app.middleware("http")
async def prevent_portrait_caching(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, error: RequestValidationError):
    # Do not echo input values, request bodies or framework error contexts.
    body = SafeError(
        code="VALIDATION_ERROR", message="Request parameters are invalid.", retryable=False, request_id=uuid4()
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


@app.exception_handler(ResponseValidationError)
@app.exception_handler(Exception)
async def safe_internal_error(request: Request, error: Exception):
    body = SafeError(
        code="INTERNAL_ERROR", message="Request could not be completed.", retryable=False, request_id=uuid4()
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"), headers={"Cache-Control": "no-store"})


def runtime(request: Request) -> Runtime:
    service = request.app.state.runtime
    if service is None:
        raise HTTPException(status_code=503, detail="SERVICE_NOT_CONFIGURED")
    return service


async def owner(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
) -> UUID:
    if credentials is None:
        raise HTTPException(status_code=401, detail="UNAUTHENTICATED")
    return await runtime(request).authenticate(credentials.credentials)


@app.exception_handler(HTTPException)
async def safe_http_error(request: Request, error: HTTPException):
    code = str(error.detail) if isinstance(error.detail, str) else "HTTP_ERROR"
    body = SafeError(
        code=code,
        message="Request could not be completed.",
        retryable=error.status_code in (429, 503, 504),
        request_id=uuid4(),
    )
    return JSONResponse(
        status_code=error.status_code, content=body.model_dump(mode="json"), headers={"Cache-Control": "no-store"}
    )


@app.get("/health", tags=["health"])
async def health():
    return {"status": "alive", "runtime_configured": app.state.runtime is not None}


@app.post("/api/v1/faces/upload-url", response_model=UploadGrant, status_code=201, tags=["faces"])
async def upload_url(body: UploadRequest, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).upload(who, body)


@app.post("/api/v1/faces/uploads/{asset_id}/complete", response_model=AssetReceipt, tags=["faces"])
async def complete_upload(asset_id: UUID, body: UploadComplete, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).complete(who, asset_id, body)


@app.post("/api/v1/faces/transform", response_model=JobPayload, status_code=202, tags=["faces"])
async def transform(
    body: TransformRequest,
    request: Request,
    who: Annotated[UUID, Depends(owner)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)],
):
    return await runtime(request).transform(who, body, idempotency_key)


@app.get("/api/v1/faces/jobs/{job_id}", response_model=JobPayload, tags=["faces"])
async def job_status(
    job_id: UUID,
    request: Request,
    who: Annotated[UUID, Depends(owner)],
    wait_seconds: Annotated[int, Query(ge=0, le=25)] = 0,
    after_revision: Annotated[int, Query(ge=0)] = 0,
):
    # Runtime must release DB connection while waiting and return on change/deadline.
    return await runtime(request).status(who, job_id, wait_seconds, after_revision)


@app.post("/api/v1/faces/jobs/{job_id}/cancel", response_model=JobPayload, status_code=202, tags=["faces"])
async def cancel_job(job_id: UUID, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).cancel(who, job_id)


@app.delete("/api/v1/faces/jobs/{job_id}/data", response_model=DeletionReceipt, status_code=202, tags=["faces"])
async def delete_job_data(job_id: UUID, request: Request, who: Annotated[UUID, Depends(owner)]):
    return await runtime(request).delete(who, job_id)

````


### `apps/api-server/celery_config.py` — complete file

````python
"""Worker transport policy; task/repository integration is Phase 1 work."""

import os

broker_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
result_backend = None  # PostgreSQL is authoritative; no portrait bytes/results in Redis.
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
task_ignore_result = True
task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1
worker_concurrency = 1  # One execution slot per GPU worker; tune only after profiling.
task_track_started = False
broker_transport_options = {"visibility_timeout": 60}
task_soft_time_limit = 40
task_time_limit = 45
# Queue payload: opaque job_id + fence only. Do not pass images, paths, tokens or URLs.
# Hard timeout means worker death and cleanup, not CUDA kernel preemption.
# Redelivery requires a DB lease/fence/idempotent settlement; this config alone is insufficient.

````

# 5. AI Inference Pipeline Boilerplate (Python)

The complete code below implements geometry, adapters, dispatch, deadline checks and blending. Approve local detector/parser/checksum artifacts first. The real smoothing primitive is an internal route; all12 launch presets require their full advertised capability before activation. ConditionalONNXFilter documents a custom-trained export signature, not an assertion that arbitrary pretrained models accept it. Optional diffusion/restoration models remain explicit adapters to implement and benchmark.


### `apps/inference-engine/inference_pipeline.py` — complete file

````python
"""Validated geometry/parsing/dispatch/blending scaffold; weights are not bundled.

Uses explicitly supplied, licensed detector/parser weights. Generative adapters must
be registered by deployment: missing adapters fail closed rather than fake an edit.
Input is EXIF-normalized, sRGB-coded uint8 BGR; output retains source dimensions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol
import hashlib
import threading
import time
import cv2
import numpy as np


class PipelineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Detection:
    bbox: np.ndarray
    landmarks5: np.ndarray
    score: float


@dataclass(frozen=True)
class Transform:
    filter_id: str
    intensity: float
    selected_face: int = 0
    preserve_background: bool = True
    options: Mapping[str, str | float] = field(default_factory=dict)
    # Structural backends must return the same 512x512 coordinate system.


@dataclass(frozen=True)
class EditedCrop:
    image_bgr: np.ndarray
    blend_mask: np.ndarray


@dataclass(frozen=True)
class PipelineResult:
    image_bgr: np.ndarray
    timings_ms: Mapping[str, float]


class Detector(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[Detection]: ...


class Parser(Protocol):
    def parse(self, crop_bgr: np.ndarray) -> np.ndarray: ...


class FilterModule(Protocol):
    def apply(self, crop_bgr: np.ndarray, labels: np.ndarray, request: Transform, deadline: float) -> EditedCrop: ...


def verify_weight(path: Path, expected_sha256: str) -> Path:
    if not path.is_file():
        raise PipelineError("MODEL_MISSING", "Supply the approved local model file")
    if len(expected_sha256) != 64:
        raise PipelineError("MODEL_NOT_APPROVED", "A pinned model checksum is required")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_sha256.lower():
        raise PipelineError("MODEL_CHECKSUM", "Model checksum does not match registry")
    return path


class InsightFaceDetector:
    """SCRFD/RetinaFace-compatible ONNX adapter: detector yields FIVE keypoints.

    Model and dependent licenses must be approved separately from MIT code.
    Do not load FaceAnalysis recognition modules or auto-download packages.
    """

    def __init__(self, model_path: Path, sha256: str, *, cuda: bool = True):
        path = verify_weight(model_path, sha256)
        import onnxruntime as ort
        from insightface.model_zoo import get_model

        if cuda and "CUDAExecutionProvider" not in ort.get_available_providers():
            raise PipelineError("GPU_UNAVAILABLE", "CUDA execution provider is required")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if cuda else ["CPUExecutionProvider"]
        self.model = get_model(str(path), providers=providers)
        if self.model is None or not hasattr(self.model, "detect"):
            raise PipelineError("DETECTOR_INVALID", "Approved weight must be a detector")
        self.model.prepare(ctx_id=0 if cuda else -1, input_size=(640, 640), det_thresh=0.6)
        self.lock = threading.Lock()

    def detect(self, image_bgr: np.ndarray) -> list[Detection]:
        with self.lock:
            boxes, landmarks = self.model.detect(image_bgr, max_num=8, metric="default")
        if landmarks is None:
            raise PipelineError("LANDMARKS_MISSING", "Detector must return five landmarks")
        faces = [
            Detection(np.asarray(b[:4], np.float32), np.asarray(k, np.float32), float(b[4]))
            for b, k in zip(boxes, landmarks)
            if float(b[4]) >= 0.6
        ]
        for face in faces:
            if (
                not np.isfinite(face.bbox).all()
                or face.bbox.shape != (4,)
                or face.landmarks5.shape != (5, 2)
                or not np.isfinite(face.landmarks5).all()
            ):
                raise PipelineError("DETECTOR_OUTPUT", "Detector returned invalid geometry")
        faces = [face for face in faces if min(face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]) >= 80]
        # Canonical stable ordering; API assigns owner/session-bound face IDs to this result.
        return sorted(faces, key=lambda face: (float(face.bbox[0]), float(face.bbox[1])))


class ONNXFaceParser:
    """Explicit NCHW RGB/ImageNet normalized BiSeNet export contract.

    Reject exports with other layouts. Label IDs supplied by model registry.
    Export preprocessing and class map must match the actual trained model.
    """

    def __init__(self, model_path: Path, sha256: str, class_count: int = 19, *, cuda: bool = True):
        import onnxruntime as ort

        path = verify_weight(model_path, sha256)
        if cuda and "CUDAExecutionProvider" not in ort.get_available_providers():
            raise PipelineError("GPU_UNAVAILABLE", "CUDA parser provider unavailable")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if cuda else ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.class_count = class_count

    def parse(self, crop_bgr: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = (
            (rgb - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
        ).transpose(2, 0, 1)[None]
        logits = self.session.run(None, {self.input_name: tensor})[0]
        if (
            logits.ndim != 4
            or logits.shape[0] != 1
            or logits.shape[1] != self.class_count
            or not np.isfinite(logits).all()
        ):
            raise PipelineError("PARSER_OUTPUT", "Expected finite 1xCxHxW parser logits")
        labels = logits[0].argmax(axis=0).astype(np.uint8)
        return cv2.resize(labels, (512, 512), interpolation=cv2.INTER_NEAREST)


def canonical_landmarks(size: int = 512) -> np.ndarray:
    # Standard five-point ArcFace geometry, centered for 128-based canvas multiples.
    base = np.array(
        [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]],
        dtype=np.float64,
    )
    return (base + np.array([8.0, 0.0])) * (size / 128.0)


def similarity_matrix(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Least-squares non-reflecting similarity: x' = s R x + t (Umeyama)."""
    a, b = np.asarray(source, np.float64), np.asarray(target, np.float64)
    if a.shape != (5, 2) or b.shape != (5, 2) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise PipelineError("LANDMARKS_INVALID", "Expected five finite 2D landmarks")
    ma, mb = a.mean(axis=0), b.mean(axis=0)
    ac, bc = a - ma, b - mb
    variance = np.sum(ac * ac) / len(a)
    if variance < 1e-8:
        raise PipelineError("ALIGNMENT_DEGENERATE", "Landmarks have insufficient spread")
    u, singular, vt = np.linalg.svd((bc.T @ ac) / len(a))
    d = np.eye(2)
    if np.linalg.det(u @ vt) < 0:
        d[-1, -1] = -1
    rotation = u @ d @ vt
    scale = float(np.sum(singular * np.diag(d)) / variance)
    if scale <= 0 or not np.isfinite(scale):
        raise PipelineError("ALIGNMENT_DEGENERATE", "Invalid similarity scale")
    linear = scale * rotation
    return np.column_stack((linear, mb - linear @ ma)).astype(np.float32)


def align_face(image_bgr: np.ndarray, face: Detection) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = similarity_matrix(face.landmarks5, canonical_landmarks())
    projected = face.landmarks5 @ matrix[:, :2].T + matrix[:, 2]
    rmse = float(np.sqrt(np.mean(np.sum((projected - canonical_landmarks()) ** 2, axis=1))))
    if rmse > 20.0:
        raise PipelineError("POSE_UNSUPPORTED", "Landmark alignment residual is too large")
    crop = cv2.warpAffine(image_bgr, matrix, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    validity = cv2.warpAffine(
        np.ones(image_bgr.shape[:2], np.float32),
        matrix,
        (512, 512),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return crop, matrix, np.clip(validity, 0, 1)


def region_mask(labels: np.ndarray, classes: tuple[int, ...]) -> np.ndarray:
    if labels.shape != (512, 512):
        raise PipelineError("PARSER_OUTPUT", "Label geometry must be 512x512")
    return np.isin(labels, classes).astype(np.float32)


class SkinSmoothing:
    """Deterministic edge-preserving retouch; only parser-confirmed skin changes."""

    def __init__(self, skin_class: int = 1):
        self.skin_class = skin_class

    def apply(self, crop_bgr: np.ndarray, labels: np.ndarray, request: Transform, deadline: float) -> EditedCrop:
        if time.monotonic() >= deadline:
            raise PipelineError("DEADLINE_EXCEEDED", "Stage budget exceeded")
        smoothed = cv2.bilateralFilter(crop_bgr, 9, 12.0 + request.intensity * 18.0, 6.0)
        mask = region_mask(labels, (self.skin_class,))
        # Erode to protect eye/lip/skin boundaries; strength scales pixel delta.
        mask = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=1)
        output = np.clip(
            crop_bgr.astype(np.float32)
            + request.intensity * (smoothed.astype(np.float32) - crop_bgr.astype(np.float32)),
            0,
            255,
        ).astype(np.uint8)
        return EditedCrop(output, mask)


class FilterDispatcher:
    def __init__(self, modules: Mapping[str, FilterModule]):
        self.modules = dict(modules)

    def transform(self, crop: np.ndarray, labels: np.ndarray, request: Transform, deadline: float) -> EditedCrop:
        module = self.modules.get(request.filter_id)
        if module is None:
            raise PipelineError("FILTER_UNAVAILABLE", "No approved adapter registered for this filter")
        result = module.apply(crop, labels, request, deadline)
        if result.image_bgr.shape != (512, 512, 3) or result.image_bgr.dtype != np.uint8:
            raise PipelineError("MODEL_OUTPUT", "Adapter must preserve 512x512 BGR geometry")
        mask = result.blend_mask
        if mask.shape != (512, 512) or not np.isfinite(mask).all() or mask.min() < 0 or mask.max() > 1:
            raise PipelineError("MODEL_OUTPUT", "Adapter must return finite normalized blend mask")
        return result


def srgb_to_linear(v: np.ndarray) -> np.ndarray:
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, 12.92 * v, 1.055 * np.power(v, 1 / 2.4) - 0.055)


def seam_blend(
    source: np.ndarray,
    original_crop: np.ndarray,
    edited: EditedCrop,
    matrix: np.ndarray,
    validity: np.ndarray,
    *,
    method: str = "alpha",
    feather_px: float = 5.0,
    protect_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Warp a premultiplied *linear-light delta* back, preserving zero-change identity.

    Unlike replacing a downsampled crop, a zero delta keeps source pixels exact.
    Gaussian feather is truncated at 3 sigma so distant background stays bit-exact.
    Optional Poisson solve is restricted to validated interior ROI; outside it, source
    remains unchanged. Poisson is not universally better for color/style edits.
    """
    if method not in ("alpha", "poisson") or not 0 <= feather_px <= 32:
        raise PipelineError("BLEND_INVALID", "Unsupported blend method/feather")
    h, w = source.shape[:2]
    inverse = cv2.invertAffineTransform(matrix)
    mask = np.clip(edited.blend_mask.astype(np.float32) * validity, 0, 1)
    if feather_px > 0:
        radius = int(np.ceil(3 * feather_px))
        mask = cv2.GaussianBlur(mask, (2 * radius + 1, 2 * radius + 1), feather_px)
        mask *= validity
    source_linear = srgb_to_linear(source.astype(np.float32) / 255)
    delta = srgb_to_linear(edited.image_bgr.astype(np.float32) / 255) - srgb_to_linear(
        original_crop.astype(np.float32) / 255
    )
    warped_delta = cv2.warpAffine(
        delta * mask[..., None], inverse, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
    )
    support = cv2.warpAffine(mask, inverse, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    if protect_mask is not None:
        if protect_mask.shape != (h, w):
            raise PipelineError("BLEND_INVALID", "Protection mask dimensions differ")
        keep = 1 - np.clip(protect_mask, 0, 1)
        warped_delta *= keep[..., None]
        support *= keep
    candidate = np.rint(linear_to_srgb(source_linear + warped_delta) * 255).astype(np.uint8)
    candidate[support <= 1e-6] = source[support <= 1e-6]
    if method == "alpha" or np.array_equal(candidate, source):
        return candidate
    binary = (support > 0.02).astype(np.uint8) * 255
    coords = cv2.findNonZero(binary)
    if coords is None:
        return source.copy()
    x, y, rw, rh = cv2.boundingRect(coords)
    if rw < 3 or rh < 3 or x < 2 or y < 2 or x + rw > w - 2 or y + rh > h - 2:
        raise PipelineError("POISSON_BOUNDARY", "Poisson ROI needs a margin inside the source")
    # ROI is positioned by bounding-box center; mask is already in source coordinates.
    cloned = cv2.seamlessClone(
        candidate[y : y + rh, x : x + rw],
        source,
        binary[y : y + rh, x : x + rw],
        (x + rw // 2, y + rh // 2),
        cv2.NORMAL_CLONE,
    )
    cloned[binary == 0] = source[binary == 0]
    return cloned


class InferencePipeline:
    def __init__(
        self,
        detector: Detector,
        parser: Parser,
        dispatcher: FilterDispatcher,
        *,
        max_pixels: int = 24_000_000,
        inference_budget_s: float = 1.35,
    ):
        self.detector, self.parser, self.dispatcher = detector, parser, dispatcher
        self.max_pixels, self.inference_budget_s = max_pixels, inference_budget_s
        # One pipeline instance per execution slot; loaded once, not once per request.
        self.lock = threading.Lock()

    def run(
        self,
        source_bgr: np.ndarray,
        request: Transform,
        *,
        blend_method: str = "alpha",
        canceled: Callable[[], bool] = lambda: False,
    ) -> PipelineResult:
        if (
            not isinstance(source_bgr, np.ndarray)
            or source_bgr.ndim != 3
            or source_bgr.shape[2] != 3
            or source_bgr.dtype != np.uint8
            or source_bgr.size == 0
        ):
            raise PipelineError("IMAGE_INVALID", "Expected normalized uint8 BGR image")
        if source_bgr.shape[0] * source_bgr.shape[1] > self.max_pixels:
            raise PipelineError("IMAGE_TOO_LARGE", "Decoded image exceeds pixel budget")
        if not np.isfinite(request.intensity) or not 0 <= request.intensity <= 1 or request.selected_face < 0:
            raise PipelineError("PARAMETER_INVALID", "Intensity/face selection invalid")
        started = time.monotonic()
        deadline = started + self.inference_budget_s
        timings: dict[str, float] = {}

        def checkpoint(stage: str, previous: float) -> float:
            now = time.monotonic()
            timings[stage] = (now - previous) * 1000
            if canceled():
                raise PipelineError("JOB_CANCELED", "Job canceled or tombstoned")
            if now > deadline:
                raise PipelineError("DEADLINE_EXCEEDED", "Inference stage budget exceeded")
            return now

        # Lock contention belongs in queue/admission control, not hidden latency.
        if not self.lock.acquire(blocking=False):
            raise PipelineError("WORKER_BUSY", "Execution slot unavailable")
        try:
            if canceled():
                raise PipelineError("JOB_CANCELED", "Job canceled before execution")
            if request.filter_id not in self.dispatcher.modules:
                raise PipelineError("FILTER_UNAVAILABLE", "Filter has no approved module")
            if request.intensity == 0:
                return PipelineResult(source_bgr.copy(), {"total": (time.monotonic() - started) * 1000})
            faces = self.detector.detect(source_bgr)
            t = checkpoint("detect", started)
            if request.selected_face >= len(faces):
                raise PipelineError("FACE_NOT_FOUND", "Selected face was not detected")
            crop, matrix, validity = align_face(source_bgr, faces[request.selected_face])
            t = checkpoint("align", t)
            labels = self.parser.parse(crop)
            t = checkpoint("parse", t)
            edited = self.dispatcher.transform(crop, labels, request, deadline)
            t = checkpoint("transform", t)
            # Protect all untargeted face boxes, including overlap with selected edit.
            protection = np.zeros(source_bgr.shape[:2], np.float32)
            for i, face in enumerate(faces):
                if i == request.selected_face:
                    continue
                x0, y0, x1, y1 = face.bbox.astype(int)
                protection[max(0, y0) : min(source_bgr.shape[0], y1), max(0, x0) : min(source_bgr.shape[1], x1)] = 1
            if request.filter_id == "skin_smooth":
                # Skin smoothing never changes original background. Structural hair
                # adapters may include newly occluded background in their approved
                # blend support; preserve_background means outside that support.
                foreground = (labels == 1).astype(np.float32)
                edited = EditedCrop(edited.image_bgr, edited.blend_mask * foreground)
                background_in_source = cv2.warpAffine(
                    (labels != 1).astype(np.float32),
                    cv2.invertAffineTransform(matrix),
                    (source_bgr.shape[1], source_bgr.shape[0]),
                    flags=cv2.INTER_NEAREST,
                )
                protection = np.maximum(protection, background_in_source)
            result = seam_blend(
                source_bgr, crop, edited, matrix, validity, method=blend_method, protect_mask=protection
            )
            checkpoint("blend", t)
            timings["total"] = (time.monotonic() - started) * 1000
            return PipelineResult(result, timings)
        finally:
            self.lock.release()


# Example composition after deploying approved weights:
# detector = InsightFaceDetector(Path("/models/scrfd.onnx"), registry["detector_sha256"])
# parser = ONNXFaceParser(Path("/models/parser.onnx"), registry["parser_sha256"])
# modules = {"skin_smooth": SkinSmoothing()}
# Register licensed age/expression/style adapters explicitly. No auto-download occurs.
# pipeline = InferencePipeline(detector, parser, FilterDispatcher(modules))

````


### `apps/inference-engine/model_adapters.py` — complete file

````python
"""Concrete conditional ONNX adapter contract; no weights bundled or downloaded.

Custom export inputs: image float32[1,3,512,512] RGB in [-1,1],
mask float32[1,1,512,512], condition float32[1,K]. Output edited_rgb
float32[1,3,512,512] in [-1,1]. K and semantic slots are registry-versioned.
A third-party checkpoint generally needs its own export/adapter; do not pretend
all age/expression/diffusion models expose this signature.
"""

from pathlib import Path
from typing import Callable
import time
import cv2
import numpy as np
from inference_pipeline import EditedCrop, PipelineError, Transform, region_mask, verify_weight


class ConditionalONNXFilter:
    def __init__(
        self,
        path: Path,
        checksum: str,
        classes: tuple[int, ...],
        condition: Callable[[Transform], np.ndarray],
        *,
        cuda: bool = True,
    ):
        import onnxruntime as ort

        approved = verify_weight(path, checksum)
        if cuda and "CUDAExecutionProvider" not in ort.get_available_providers():
            raise PipelineError("GPU_UNAVAILABLE", "CUDA provider required")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if cuda else ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(approved), providers=providers)
        if {i.name for i in self.session.get_inputs()} != {"image", "mask", "condition"}:
            raise PipelineError("MODEL_CONTRACT", "Export does not match conditional ONNX contract")
        self.classes, self.condition = classes, condition

    def apply(self, crop_bgr: np.ndarray, labels: np.ndarray, request: Transform, deadline: float) -> EditedCrop:
        if time.monotonic() >= deadline:
            raise PipelineError("DEADLINE_EXCEEDED", "Model stage expired")
        mask = region_mask(labels, self.classes)
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 127.5 - 1
        cond = np.asarray(self.condition(request), dtype=np.float32).reshape(1, -1)
        if not np.isfinite(cond).all():
            raise PipelineError("MODEL_CONTRACT", "Condition is non-finite")
        output = self.session.run(
            ["edited_rgb"], {"image": rgb.transpose(2, 0, 1)[None], "mask": mask[None, None], "condition": cond}
        )[0]
        if (
            output.shape != (1, 3, 512, 512)
            or not np.isfinite(output).all()
            or output.min() < -1.001
            or output.max() > 1.001
        ):
            raise PipelineError("MODEL_OUTPUT", "Invalid conditional ONNX image")
        if time.monotonic() >= deadline:
            raise PipelineError("DEADLINE_EXCEEDED", "Model completed after deadline")
        image = np.rint(np.clip((output[0].transpose(1, 2, 0) + 1) * 127.5, 0, 255)).astype(np.uint8)
        return EditedCrop(cv2.cvtColor(image, cv2.COLOR_RGB2BGR), mask)


# Example condition layout for YOUR trained age export: [target_age/100,intensity].
# routes['age_50s']=ConditionalONNXFilter(path,hash,(1,2,3,4,5,6,7,10,11,12,13),
#    lambda r:np.array([.55,r.intensity],np.float32))
# For new hair/beard geometry, replace fixed mask with a validated model-proposed
# change mask; region mask alone cannot grow hair outside the existing silhouette.

````


### `apps/mobile/src/editor-binding.ts` — complete file

````typescript
export interface EditorBinding {assetId:string;revision:number;faceId:string;candidateRevision:number}
export function acceptsResult(active:EditorBinding, completed:EditorBinding):boolean {
 return active.assetId===completed.assetId && active.revision===completed.revision && active.faceId===completed.faceId && active.candidateRevision===completed.candidateRevision;
}
// Also check current job ID, cancellation/tombstone and expiry before displaying.

````

# 6. Asset Inventory & UI/UX Design Token Specifications



`assets/design-tokens.json` is the machine-readable source: dark canvas, elevated surfaces, primary violet, accent mint, high contrast text, Inter/system fonts,8-based space scale with4px steps,44pt iOS/48dp Android targets, restrained120–240ms motion and reduced-motion bypass. Measure contrast for every actual foreground/background pair; numeric token names don't prove WCAG compliance. Always label sliders with numeric value; magic icons have text labels. Compare gesture has accessible Before/After toggle, not just drag.

### Included assets

- Four required original vector SVGs, plus the supplementary icon set: magic-wand.svg, sliders.svg, compare.svg, download.svg. viewBox0 0 24 24, currentColor stroke, round caps/joins. Wrap with react-native-svg or use web directly; don't insert raw SVG markup as React Native views.
- Twelve filters in filters.json with stable IDs, categories, icon references, defaults and explicit model routes. Thirteen primitive capabilities are represented by12 launch tiles because makeup and smoothing share Beauty Retouch controls. All presets currently blocked pending approved weights/quality/latency, regardless of presence of preview assets.
- Inter variable font + SIL OFL license, reused from the prior kit. Prefer native system text if font load fails. Font is actual bundled TTF, not a link-only resource.
- Original synthetic adult portrait PNG1024x1536, provenance note. Development layout/demo fixture only; no real identity or release dataset. No model-generated before/after claim is implied. Prior kit contains additional original illustrations/thumbnail placeholders; The standalone v2 bundle also includes the original supplementary icons, brand vector sources,8 background SVGs and4 local color LUTs.

### States to implement

Onboarding/privacy consent, library/camera, selected-face picker, editor with filter tray/intensity/compare/apply/reset, processing with actual stages/cancel, offline/network/retry/permission/no-face/pose/filter-unavailable states, export/share, quota/purchase/restore, privacy deletion tracker, minimal metadata admin. Background upload, last-writer-wins candidate revision, cancellation and purge override late results. Preserve immutable source plus accepted edit history; a candidate does not mutate the source. Every export operates on selected committed result and retains source dimensions unless a documented export option says otherwise.

### Remaining production assets

Approved inference weights/dense-landmark artifact/model prompt versions, licensed evaluation set with participant consent, independently designed final brand/app icon variants, screenshots from actual devices, translations, real legal policy/support URLs, billing products and signing certificates. The bundle cannot manufacture commercial weight rights, processor agreements or credentials. These are enumerated resource gates, not hidden TODOs.


### `assets/design-tokens.json` — complete file

````json
{
  "colors": {
    "background": "#0B0D14",
    "surface": "#171B27",
    "raised": "#242A3A",
    "border": "#566078",
    "text": "#F7F8FC",
    "muted": "#BBC3D5",
    "accent": "#B5A5FF",
    "on_accent": "#151020",
    "success": "#79E2AC",
    "warning": "#FFD18B",
    "error": "#FFADB8"
  },
  "typography": {
    "family": "System / Inter",
    "h1": {
      "size": 28,
      "line_height": 34,
      "weight": 650
    },
    "h2": {
      "size": 22,
      "line_height": 28,
      "weight": 600
    },
    "body": {
      "size": 17,
      "line_height": 24,
      "weight": 400
    },
    "label": {
      "size": 15,
      "line_height": 20,
      "weight": 550
    },
    "caption": {
      "size": 13,
      "line_height": 18,
      "weight": 400
    }
  },
  "spacing": [
    4,
    8,
    12,
    16,
    24,
    32,
    48,
    64
  ],
  "radii": {
    "small": 8,
    "control": 12,
    "sheet": 24
  },
  "touch_min": {
    "ios": 44,
    "android": 48
  },
  "motion_ms": {
    "short": 120,
    "standard": 200,
    "reduced": 0
  }
}

````


### `assets/icons/magic-wand.svg` — complete file

````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 18 10-10 4 4L7 22zM11 10l4 4M18 2v4M16 4h4M5 3v4M3 5h4M20 17v4M18 19h4"/></svg>

````


### `assets/icons/sliders.svg` — complete file

````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h5M12 6h9M3 12h11M18 12h3M3 18h3M10 18h11"/><circle cx="10" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/></svg>

````


### `assets/icons/compare.svg` — complete file

````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M12 3v18M7 8v8M17 8v8"/></svg>

````


### `assets/icons/download.svg` — complete file

````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/></svg>

````


### `assets/filters.json` — complete file

````json
[
  {
    "id": "age_young",
    "display_name": "Young Adult",
    "category": "age",
    "icon_reference": "assets/icons/age.svg",
    "intensity_default": 0.35,
    "model_route": {
      "adapter_key": "age.onnx",
      "parameters": {
        "target_age": 25
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "age_teen",
    "display_name": "Teen",
    "category": "age",
    "icon_reference": "assets/icons/age.svg",
    "intensity_default": 0.35,
    "model_route": {
      "adapter_key": "age.onnx",
      "parameters": {
        "target_age": 17
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "age_50s",
    "display_name": "50s",
    "category": "age",
    "icon_reference": "assets/icons/age.svg",
    "intensity_default": 0.35,
    "model_route": {
      "adapter_key": "age.onnx",
      "parameters": {
        "target_age": 55
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "age_70s",
    "display_name": "70s",
    "category": "age",
    "icon_reference": "assets/icons/age.svg",
    "intensity_default": 0.35,
    "model_route": {
      "adapter_key": "age.onnx",
      "parameters": {
        "target_age": 75
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "smile_subtle",
    "display_name": "Subtle Smile",
    "category": "expression",
    "icon_reference": "assets/icons/smile.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "expression.onnx",
      "parameters": {
        "expression": "closed_lip_smile"
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "smile_tooth",
    "display_name": "Tooth Smile",
    "category": "expression",
    "icon_reference": "assets/icons/smile.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "expression.onnx",
      "parameters": {
        "expression": "tooth_smile"
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "laugh",
    "display_name": "Laugh",
    "category": "expression",
    "icon_reference": "assets/icons/smile.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "expression.onnx",
      "parameters": {
        "expression": "laugh"
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "gender_feminine",
    "display_name": "Feminine",
    "category": "presentation",
    "icon_reference": "assets/icons/face.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "presentation.onnx",
      "parameters": {
        "style": "feminine"
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "gender_masculine",
    "display_name": "Masculine",
    "category": "presentation",
    "icon_reference": "assets/icons/face.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "presentation.onnx",
      "parameters": {
        "style": "masculine"
      },
      "requires_license_approval": true,
      "mask_region": "face",
      "intensity_semantics": "validated_strength_tiers",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "hair_color",
    "display_name": "Hair Color",
    "category": "style",
    "icon_reference": "assets/icons/hair-color.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "hair.onnx",
      "parameters": {
        "color_hex": "#A15B39"
      },
      "requires_license_approval": true,
      "mask_region": "hair",
      "intensity_semantics": "validated_continuous",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "beard_density",
    "display_name": "Beard Density",
    "category": "style",
    "icon_reference": "assets/icons/beard.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "beard.onnx",
      "parameters": {
        "density": 0.3
      },
      "requires_license_approval": true,
      "mask_region": "lower_face",
      "intensity_semantics": "validated_continuous",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  },
  {
    "id": "beauty_retouch",
    "display_name": "Beauty Retouch",
    "category": "beauty",
    "icon_reference": "assets/icons/makeup.svg",
    "intensity_default": 0.3,
    "model_route": {
      "adapter_key": "beauty.compose",
      "parameters": {
        "skin_smoothing": 0.4,
        "makeup": 0.2
      },
      "requires_license_approval": true,
      "mask_region": "skin_and_makeup",
      "intensity_semantics": "validated_continuous",
      "checkpoint_sha256": null
    },
    "release_status": "blocked_pending_weights_and_benchmark"
  }
]

````



The SVG UI icons, brand sources, backgrounds and LUT tables were authored for this bundle. Permission is granted to use, copy, modify, distribute and sublicense those original files, with or without attribution. They contain no FaceApp marks. No trademark license or exclusivity is claimed.

Inter is distributed with its SIL Open Font License in fonts/OFL.txt. Keep that license with redistribution; review reserved-font-name rules if modifying the font. The synthetic portrait has the exact generation prompt and limitations in demo/PROVENANCE.md; generation-service terms apply. It is a layout fixture, not a licensed participant evaluation dataset.

All model files are absent. Null checksum/license approvals in model-registry.json mean disabled, not public-domain or freely commercial. Research sources are links, not an asset redistribution grant. Independently review every weight, training-data and dependency license before downloading or enabling a route.



Generated: 10 October 2026, using the built-in imagegen tool in default tool mode. One fictional adult studio portrait, inspected visually. Saved in this package as `portrait-original.png` (1024 × 1536 PNG). Original generation remains in the tool output directory; this package contains a copy.

This asset is a synthetic demonstration, not a real participant, FaceApp output, consented real-user benchmark, or evidence of app performance. Applicable generation-service terms govern use; no exclusive ownership or stock/model release is asserted.

### Exact generation prompt

Use case: photorealistic-natural. Asset type: synthetic demo portrait for an independent portrait photo editing application. Primary request: create a single realistic studio head-and-shoulders portrait of a fictional South Asian adult woman, approximately 30 years old, looking straight into the camera with a relaxed neutral expression and closed lips. Natural medium brown skin with visible pores and a few minor natural blemishes, dark brown shoulder-length gently wavy hair fully visible, brown eyes, no glasses, no makeup beyond ordinary minimal grooming, plain muted blue shirt. Clean warm gray studio background, soft even daylight lighting, both shoulders and top of head included with generous margin. Vertical portrait composition, 1024x1536 if possible. Crisp photographic detail, realistic anatomy and skin texture. No retouching or beautification, no jewelry obscuring face, no text, no logos, no watermarks, no famous or real person likeness. This is one original image, not a collage, not a before-and-after sheet.


# 7. CLAUDE.md Blueprint File


### `CLAUDE.md` — complete file

````markdown
# 7. Claude Code / Claude Projects implementation blueprint

## Project summary and goals

Build an independent FaceApp-like portrait modification product: iOS/Android React Native/Expo, Next.js admin/preview, FastAPI gateway/Celery/private storage, Python GPU pipeline. Twelve launch tiles include four age, three expression, two presentation, hair color, beard and combined beauty with makeup/skin controls. Preserve user source and selected-face continuity; do not misrepresent unimplemented/research-only routes. Read PROJECT_SPECIFICATION.md, schemas/OpenAPI, Prisma + migration constraints, privacy purge and model registry before implementing.

## Coding conventions

TypeScript strict, no implicit any, no unchecked indexed access; typed errors/unions; generated API types from source schemas; no provider secrets in client. Python3.12 type hints, Pydantic2 extra=forbid with strict numeric/bool fields, Ruff lint and focused unittest/pytest. No `except: pass`, swallowed model errors or success-shaped dummy response. Return stable safe code/message/retryable/request_id; log opaque job IDs/durations only. Validate bytes/pixels/EXIF/ICC, masks/tensor dimensions, finite values and asset ownership. UUID secrecy is not authorization.

Source images are immutable; candidate/committed/revision separate; crop geometry and masks use one documented transform chain. Unknown filter/model/version returns FILTER_UNAVAILABLE. Models require local approved path/checksum/licensing. No download during a request. InsightFace detection uses5 landmarks, dense68 is a separate optional adapter; do not load recognition embeddings by default. Pipeline output remains source resolution and untargeted pixels are protected.

## Commands

`npm run build`, `npm run test`, `npm run dev`, `npm run lint`, `npm run docker:up` delegate to Makefile. Prerequisite Python environment is `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements-dev.txt`; app packages use npm workspaces. `make dev` serves API; `make dev-mobile`/`make dev-web` run application packages. `make docker-up` starts private local infrastructure. Initial scaffold health/OpenAPI works after dependencies; production routes fail503 until Runtime repositories/auth/queue are implemented. Do not call that a full backend.

`make build` performs static Python/schema checks plus app TypeScript checks as configured; it does not create signed mobile binaries or build unimplemented screens. Create native builds with Expo prebuild/run/EAS and document actual platform tests. Freeze compatible JS/Python dependencies and container digests during Phase1; ranges/tags in this specification are bootstrap candidates, not a reviewed production lockfile. GPU optional dependencies need CUDA12/cuDNN major compatibility and deployment-hardware testing.

## Start building Phase 1 — exact order

1. Audit scaffold, identify actual versus interface-only code; record versions/decisions in PROGRESS.md. Resolve any contract changes in Pydantic, TS, OpenAPI and Prisma together.
2. Install and lock compatible dependencies. Keep requested Reanimated3 track only with compatible Expo/RN patches; no silent unsupported native package mix.
3. Implement Expo navigation, system picker/camera permission paths, original normalization, Skia local canvas, candidate/committed state, compare, undo and real edited export. No forced cloud call for local tools.
4. Implement safe authenticated Runtime interface: upload grants/finalize and owner/consent relations using PostgreSQL/private MinIO. Routes must not trust client object keys or remote URLs.
5. Apply migrations/constraints; implement atomic credit reservation, idempotency hash, job/outbox, task leases/fences and long-poll update notification.
6. Connect licensed detector/parser local artifacts, then a single real transformation. Missing generative weights stay unavailable, not simulated with color filters. Run geometry/zero-intensity/locality tests and permitted face benchmark.
7. Implement purge daemon and media gateway; test deletion concurrent with output writes/callbacks and orphan cleanup before expanding AI families.
8. Build minimal Next.js metadata admin/preview with role checks, feature/worker status and no public portrait listing.
9. Report runnable flow, actual tests/platforms, what remains scaffold-only, licensing/accounts missing, measured latency and next phase. Preserve prior build kit.

## Later phases

Phase2 approved age/expression/presentation/style modules and calibrated intensity; Phase3 live store billing, quota/restore/revocation, full editor polish; Phase4 real-device/GPU concurrency/privacy/accessibility/store deployment. Do not promise 2.5s cold-start diffusion; keep readiness/warm pool and measured fast/slow routes. No fake progress percentage: indeterminate or actual step callback. Private result delivery only, no public CDN portrait URLs.

## Production invariants

Credits reserved transactionally before paid work, settled once; request key reused with different body409; at-least-once Celery does not duplicate cost; deletion/tombstones override every task; no resurrection after purge; absolute expiry never sliding; no images/vectors/EXIF in Redis/logs/audit; restoration optional/benchmarked; teen effect illustrative and actual minor-use policy reviewed; policy claims match provider/storage reality. GDPR/BIPA review is a release gate, not a promise made by the scaffold.

## Completion evidence

PROGRESS.md lists commands, pass/fail, live vs mock, actual device/GPU/backend versions, model/checkpoint/prompt version, output dimensions/latency/cost, constraints and blockers. Continue reversible work without repetitive approvals. Secret names may be documented, secret values never pasted. Do not claim native/AI/billing tests passed when only package or geometry tests ran.

````


## Additional exhaustive ChatGPT collection prompt


### `CHATGPT_COLLECTION_PROMPT.md` — complete file

````markdown
# Reusable exhaustive research and collection prompt

You are a principal AI architect, mobile engineer, GPU inference engineer and product designer. Read this entire PortraitLab/FaceApp-like specification bundle. Produce concrete, runnable additions and primary-source research to finish an independently branded portrait editor. Cover the seven sections in PROJECT_SPECIFICATION.md without skipping API/database/privacy/model math/assets/Claude instructions. Preserve sources/ read-only and preserve existing bundle files unless updating contracts consistently.

First audit current implementation against README.md and VALIDATION_REPORT.md. Classify each requirement as implemented+verified, implemented+unverified, interface/spec-only, blocked by weight license/credentials, or out of current phase. Never claim the commercial age/smile/presentation pipelines exist because their filter manifest entries exist.

Research the current exact Expo/React Native/Reanimated/Skia/VisionCamera compatibility matrix and supported Next/React versions. Resolve the requested legacy Reanimated3 constraint transparently; pin hashes/lockfiles only after install/build. Recheck current security advisories. Use only primary official docs/model cards/repository licenses/papers/legal texts, record URL,date,claim and uncertainty. Do not invent licenses, download gated assets without granted rights, or promise zero biometric retention while images are still needed for editing.

For every AI artifact produce model route,input/output signatures,preprocessing,mask class map,resolution,weight URL/local path,SHA256,source+weight+dataset/dependency licenses,commercial approval state,VRAM and cold/warm measurements,identity/locality evaluation,known failures and fallback. Require owner-approved commercial artifacts for launch. Distinguish five detector keypoints from optional68 landmarks; do not treat IP-Adapter FaceID/StyleGAN3/GFPGAN/CodeFormer/FLUX as interchangeable plug-ins.

Implement one canonical architecture (FastAPI/Celery/PostgreSQL/privateS3 + Python GPU workers) rather than competing duplicate services. Supply generated OpenAPI3.1 JSON/YAML, authoritative Pydantic/TS types, Prisma6 migration schema+rawSQL checks, safe examples,error envelopes,JWT/ownership/consent/idempotency/fence/settlement/purge contracts. Implement deletion races,abortedupload cleanup,private no-store media,absolute expiry and transaction+outbox consistency before expanding transformations.

Supply real original reusable assets: SVGs,tokens,licensedfonts,synthetic fixtureprovenance,appicons/splash sizing,accessibility states and localization keys. Previews must be labeled simulated unless produced by actual approved inference. Package all text/code/configassets in a versioned folder and ZIP, create a file/hash/license manifest, check local references, and provide exact run/test commands plus measured limitations.

Work sequentially: audit+locks→nativeimport/localeditor→authenticatedupload/jobwallet→licensedonefilter→purge/raceevidence→all12filters→billing/admin/store. Each stage needs pass/fail evidence and truthful blockers. Ask only for information that prevents implementation; continue independent work. Do not purchase subscriptions, publish apps, or send messages without the user's authorization. Return the complete changed files and a concise handoff telling Claude to read CLAUDE.md and “Start building Phase 1.”

````


## Bootstrap and truthfully verified scope



Read [PROJECT_SPECIFICATION.md](PROJECT_SPECIFICATION.md) for the full seven-section deliverable, with complete API/schema/Python/SVG/manifest/Claude source blocks. Read [CLAUDE.md](CLAUDE.md), then tell Claude Code: **Start building Phase 1.** For Claude Projects, upload the Markdown/specification/contracts; use Claude Code/Cowork with access to this extracted folder for actual repository edits. A ZIP is the portable project bundle, not a proprietary Claude project format.

This is a production-oriented specification and tested scaffold, not a finished FaceApp replica. It uses independent working branding. Licensed generative weights and real backend integrations must be added before deployment; do not promise FaceApp's proprietary model quality. Presets are launch requirements and stay disabled until license/benchmark approval.

### Included and verified

- Complete PRD, mathematical architecture, retention/purge/race contracts and primary-source research ledger.
- Executable FastAPI/OpenAPI3.1 contract shell, Pydantic2/TypeScript types, Prisma6 schema + raw SQL constraints.
- Real five-landmark alignment, ONNX detector/parser adapters, dispatcher, deterministic smoothing and source-resolution alpha/Poisson blending. A custom conditional ONNX adapter signature is supplied; model files are not.
- Four required SVGs plus supplementary icons, brand vector sources,8 background SVGs,4 local LUTs, dark UI tokens,12 filter presets, Inter font/license and synthetic portrait/provenance.
- Expo/Next starter workspaces, local Docker infrastructure/config, test/contract-generation commands, master collection prompt and phased CLAUDE.md.

### Bootstrap

Use Python3.12 and a Node version supported by the selected web/Expo packages. Create a virtual environment, install requirements-dev.txt, then install JavaScript workspaces and freeze lockfiles only after compatibility checks:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm install
make contracts
npm run test
npm run lint
npm run build
cp .env.example .env
npm run docker:up
npm run dev
```

`make dev-mobile` uses a custom Expo development build; VisionCamera is not available merely by opening Expo Go. `make dev-web` starts Next. Set local-only credentials in .env; never commit real secrets. Docker starts PostgreSQL/Redis/MinIO/API shell, not a running commercial inference service. Initialize a private ephemeral bucket and implement Runtime/repositories/worker/purge before a real user flow. /health and /openapi.json are available; unconfigured portrait routes return503. See VALIDATION_REPORT.md for actual checks, not inferred passes.

Expo53/Reanimated3 is the requested legacy compatibility track. Web uses Next16.4/React19.3 bootstrap candidates researched2026-10-10. Recheck official security and store requirements, freeze supported versions and image digests, then run device/GPU/DB/deletion tests. None of those integration builds is claimed as verified here.

### Handoff

CHATGPT_COLLECTION_PROMPT.md is the exhaustive research/assets prompt. CLAUDE.md is the implementation instruction file. docs/ holds individual specifications and real contracts; apps/ and packages/ hold code; assets/ contains actual files. MANIFEST.json lists SHA256/bytes for every deliverable except its own manifest. Sources synced from the ChatGPT project were read-only and untouched.



### Passed on this computer

- 28 Python unittest cases: 11 API/schema cases and 17 image geometry/locality/error cases.
- Five-point scale/rotation/translation fit,512 crop/validity, exact zero-delta and zero-strength original, finite feather locality, other-face protection, sensitive eye/lip protection, zero-validity rejection and Poisson outside-region preservation.
- Missing filter/face, cancelled job, expired stage/unlocked worker slot, bad mask, oversized/empty image and nonfinite intensity checks.
- Pydantic strict fields/ranges/options/extra keys, uploaded size/checksum, progress/result consistency, OpenAPI3.1 routes/auth/idempotency, no-store responses, unconfigured 503, missing auth 401, validation input redaction and 12 manifest/schema ID agreement.
- Ruff0.11.13 check passed on all Python apps/packages/scripts/tests after formatting.
- Python AST, JSON/SVG parsing, asset references andschema draft2020-12 checks passed. OpenAPI generated from actual app; YAML/JSON equivalence checked during packaging.
- ZIP byte integrity and file/hash manifest checked during final packaging.

Local test runtime: Python 3.12, NumPy 2.3.5, OpenCV 4.12.0, Pydantic 2.13.5, FastAPI 0.115.12/Starlette 0.46.2, AnyIO 4.9.0, HTTPX 0.28.1, jsonschema 4.23.0. Libraries for validation were isolated in temporary directories. OpenCV bootstrap requirements prefer NumPy<2.3 according to its wheel dependency range; current host NumPy 2.3.5 loaded successfully for these tests, but that does not validate every production matrix. Install/freeze a consistent dependency set for deployment.

### Not run / not supplied

No actual InsightFace/BiSeNet/generative/restoration weights were loaded. GPU/CUDA/Triton/Modal/RunPod quality, identity and latency are unmeasured. ONNX adapters are code/contracts with no real checkpoint execution.28 tests do not demonstrate realistic age/smile/gender generation or 2.5-second service latency.

No JS dependencies installed/locked; no Expo native/device/Skia/VisionCamera/Next production build, TypeScript workspace check or signed store package was run here. Native/mobile andwebUI remain initial shells. No PostgreSQL/Prisma CLI migration execution, SQL integration, Docker startup, actual storage presign/purge or Celery queue/billing integration run. Auth/storage/job/wallet/purge Runtime remains interface-only and API routes fail closed with 503 until implemented. Prisma+rawSQL are concrete reviewed design files, not applied migrations.

No legal compliance certification, payment credentials, cloud accounts, model commercial rights, real user consents or app store products are manufactured by this bundle. Missing resources are listed in docs/05_MODEL_REGISTRY_AND_LICENSES.md and docs/06_ASSETS_AND_UX.md. Complete Phase 1 and document actual evidence before enabling filters.


## Primary research resources



Facts below informed the contracts; architecture/SLO/retention numbers are proposed requirements, not measured facts about FaceApp. No proprietary FaceApp model weights or internal architecture are known or bundled.

| Resource | Direct primary source | What to verify before implementation |
|---|---|---|
| InsightFace | https://www.insightface.ai/ | MIT code vs pretrained-model licensing; recognition dependencies |
| Five-point alignment | https://github.com/deepinsight/insightface/blob/master/python-package/insightface/utils/face_align.py | Template,128-based center offset, landmark order |
| InsightFace code/model zoo | https://github.com/deepinsight/insightface | Model entrypoints, no request-time downloads |
| Face parsing reference | https://github.com/zllrunning/face-parsing.PyTorch | Training-data/weight licenses and exact19-class mapping |
| SDXL Diffusers | https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/stable_diffusion_xl | Inpaint signature, resolution/strength tradeoffs |
| IP-Adapter FaceID | https://huggingface.co/h94/IP-Adapter-FaceID | Research-only statements and InsightFace dependency |
| FLUX.1 Fill | https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev | Checkpoint-specific license/commercial route; do not infer from brand |
| StyleGAN3 | https://github.com/NVlabs/stylegan3 | NVIDIA source/model/dataset terms, inversion and directions |
| CodeFormer | https://github.com/sczhou/CodeFormer | NTU S-Lab license and fidelity tradeoff |
| GFPGAN | https://github.com/TencentARC/GFPGAN | Source/dependency/checkpoint terms and identity changes |
| ORT CUDA | https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html | CUDA and cuDNN major compatibility |
| Triton model config | https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html | Warmup, shapes, bounded batching |
| OpenCV clone | https://docs.opencv.org/4.x/df/da0/group__photo__clone.html | Mask/type/ROI conventions |
| Reanimated3 compatibility | https://docs.swmansion.com/react-native-reanimated/docs/3.x/guides/compatibility/ | Legacy RN/Expo compatibility,3.17.5 patch support |
| Reanimated3 maintenance | https://docs.swmansion.com/react-native-reanimated/docs/3.x/fundamentals/getting-started/ | Deprecated track; upgrade plan |
| Expo | https://docs.expo.dev/ | Dev builds required for native libraries; SDK-specific matrix |
| VisionCamera | https://react-native-vision-camera.com/docs/guides | Capture/permission setup for chosen version |
| Next16.4 | https://nextjs.org/blog/next-16-4 | Released2026-10-06; React19.3 support |
| Next security notice | https://nextjs.org/blog/upcoming-nextjs-security-update-october-2026 | Announced patch due2026-10-14; recheck before any deployment |
| Pydantic2 | https://docs.pydantic.dev/latest/concepts/models/ | Runtime validation vs TS/static guarantees |
| FastAPI OpenAPI | https://fastapi.tiangolo.com/how-to/extending-openapi/ | Generated contract vs manual documentation drift |
| Celery config | https://docs.celeryq.dev/en/stable/userguide/configuration.html | Late ack/prefetch/visibility and redelivery behavior |
| Prisma CHECKs | https://www.prisma.io/docs/orm/more/help-and-troubleshooting/check-constraints | SQL migrations for checks; schema version choice |
| GDPR | https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng | Articles5/6/9/13/17/25/28/32/35,biometric purpose/legal basis |
| Illinois BIPA15 | https://www.ilga.gov/legislation/ilcs/documents/074000140K15.htm | Written release, disclosure and destruction schedule; applicability review |
| Inter license | https://github.com/rsms/inter/blob/master/LICENSE.txt | SIL OFL distribution requirements |

Dependency versions are bootstrap candidates. Freeze exact locks/hashes and container digests after installation and native/GPU integration tests. Expo53/Reanimated3 is an explicitly legacy compatibility track to satisfy the requested major version, not a claim that it is the latest Expo. Next16.4/React19.3 is separate web workspace; do not force its React version into the mobile package.
