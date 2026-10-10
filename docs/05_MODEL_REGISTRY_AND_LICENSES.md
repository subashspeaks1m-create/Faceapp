# Model registry and license gate

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
