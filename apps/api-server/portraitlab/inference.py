"""Inference integration points. Only registry-approved artifacts are loaded; nothing is simulated.

The default deployment has no approved detector, parser or generative route, so
`detector_from_registry` returns None and `RegistryExecutor.available_filters()` is empty.
Uploads then fail closed with DETECTOR_UNAVAILABLE and transforms with FILTER_UNAVAILABLE.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence
import json
import sys
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class FaceBox:
    bbox: tuple[float, float, float, float]
    landmarks5: tuple[tuple[float, float], ...]
    score: float


class FaceDetector(Protocol):
    def detect(self, rgb: Image.Image) -> Sequence[FaceBox]: ...


class ExecutionFailed(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ExecutionRequest:
    filter_type: str
    intensity: float
    face_ordinal: int
    preserve_background: bool
    options: dict


class Executor(Protocol):
    def available_filters(self) -> frozenset[str]: ...

    def run(self, source_png: bytes, request: ExecutionRequest, canceled) -> bytes: ...


def _approved(entry: dict | None) -> bool:
    return bool(entry and entry.get("path") and entry.get("sha256") and entry.get("commercial_approval_ref"))


def _pipeline_module(root: Path):
    path = str(root / "apps/inference-engine")
    if path not in sys.path:
        sys.path.insert(0, path)
    import inference_pipeline

    return inference_pipeline


def detector_from_registry(registry_path: Path, repo_root: Path) -> FaceDetector | None:
    registry = json.loads(registry_path.read_text())
    entry = registry.get("detector")
    if not _approved(entry):
        return None
    ip = _pipeline_module(repo_root)
    model = ip.InsightFaceDetector(Path(entry["path"]), entry["sha256"], cuda=False)

    class _Adapter:
        def detect(self, rgb: Image.Image) -> Sequence[FaceBox]:
            bgr = np.ascontiguousarray(np.asarray(rgb, dtype=np.uint8)[:, :, ::-1])
            return [
                FaceBox(tuple(map(float, d.bbox)), tuple(tuple(map(float, p)) for p in d.landmarks5), float(d.score))
                for d in model.detect(bgr)
            ]

    return _Adapter()


class RegistryExecutor:
    """Runs only routes whose detector, parser and generative artifact are all approved."""

    def __init__(self, registry_path: Path, filters_path: Path):
        self.registry = json.loads(registry_path.read_text())
        self.filters = {f["id"]: f for f in json.loads(filters_path.read_text())}

    def available_filters(self) -> frozenset[str]:
        if not (_approved(self.registry.get("detector")) and _approved(self.registry.get("parser"))):
            return frozenset()
        routes = self.registry.get("generative_routes", {})
        return frozenset(
            fid
            for fid, f in self.filters.items()
            if _approved(routes.get(f["model_route"]["adapter_key"]))
            and routes[f["model_route"]["adapter_key"]].get("ready") is True
        )

    def run(self, source_png: bytes, request: ExecutionRequest, canceled) -> bytes:
        # No approved route exists in this build; an approved one must add its adapter here.
        raise ExecutionFailed("FILTER_UNAVAILABLE")
