# Primary-source research ledger — checked 2026-10-10

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
