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
