"""Generate OpenAPI 3.1 JSON and JSON Schemas from executable source."""

from pathlib import Path
import importlib.util
import json
import sys
import yaml

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "packages/shared-types"))
from schemas import (  # noqa: E402 — local standalone module path is configured above
    UploadRequest,
    UploadGrant,
    UploadComplete,
    AssetReceipt,
    TransformRequest,
    JobPayload,
    SafeError,
    DeletionReceipt,
)

spec = importlib.util.spec_from_file_location("face_api", R / "apps/api-server/main.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
doc = module.app.openapi()
doc["servers"] = [
    {"url": "http://localhost:8000", "description": "Local development"},
    {"url": "https://api.example.invalid", "description": "Replace with deployed TLS API"},
]
(R / "docs/openapi.json").write_text(json.dumps(doc, indent=2) + "\n")
(R / "docs/openapi.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
for model in (
    UploadRequest,
    UploadGrant,
    UploadComplete,
    AssetReceipt,
    TransformRequest,
    JobPayload,
    SafeError,
    DeletionReceipt,
):
    path = R / "packages/shared-types/json-schema" / f"{model.__name__}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
print("Generated OpenAPI 3.1 and eight JSON Schema contracts.")
