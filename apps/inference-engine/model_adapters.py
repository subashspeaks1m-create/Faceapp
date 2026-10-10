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
