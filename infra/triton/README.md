# Optional Triton deployment

Put an approved, checksummed ONNX parser in `models/face_parser/1/model.onnx` outside source control. This sample config requires tensor names `input`/`logits` and fixed19-class512 output. Adapt to the actual export; direct Python ONNX adapter is canonical for Phase1. No Triton model is runnable without weights. Explicit-load approved versions, warm each GPU execution instance, and admit requests only after readiness + measured warmup. Pin an NVIDIA Triton image digest compatible with the ORT/CUDA/cuDNN stack after testing; do not infer compatibility from “CUDA12” alone.

Never enable default unbounded dynamic batching. Queue delay2ms is a candidate to benchmark alongside p95 latency and peakVRAM. Triton is optional; keep orchestration/ownership/deletion checks in gateway/worker. Modal/RunPod are deployment alternatives using the same adapter contract, not three simultaneously required inference layers.

Source: [Triton model configuration](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html).
