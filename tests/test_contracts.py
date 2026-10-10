import json
import sys
import unittest
import importlib.util
from pathlib import Path
from uuid import UUID
from pydantic import ValidationError
from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "packages/shared-types"))
from schemas import TransformRequest, UploadRequest, JobPayload  # noqa: E402 — local standalone module path is configured above

spec = importlib.util.spec_from_file_location("api_for_test", R / "apps/api-server/main.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
A = "00000000-0000-4000-8000-000000000001"
B = "00000000-0000-4000-8000-000000000002"


def request():
    return dict(
        asset_id=A,
        face_id=B,
        filter_type="age_50s",
        intensity=0.35,
        preserve_background=True,
        source_revision=0,
        candidate_revision=1,
    )


def job():
    return dict(
        job_id=A,
        asset_id=A,
        face_id=B,
        source_revision=0,
        candidate_revision=1,
        status="running",
        stage="transform",
        event_revision=2,
        progress_percent=None,
        progress_source="indeterminate",
        created_at="2026-10-10T00:00:00Z",
        updated_at="2026-10-10T00:00:01Z",
    )


class AuthOnlyTestRuntime:
    async def authenticate(self, token):
        return UUID(A)


class ContractTests(unittest.TestCase):
    def tearDown(self):
        api.app.state.runtime = None

    def test_valid_request_and_exported_schema(self):
        body = request()
        model = TransformRequest.model_validate(body)
        Draft202012Validator(TransformRequest.model_json_schema()).validate(model.model_dump(mode="json"))

    def test_invalid_strength_and_types(self):
        for value in (-0.1, 1.01, float("nan"), True, "0.5"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                TransformRequest.model_validate({**request(), "intensity": value})

    def test_boolean_and_revision_strict(self):
        for changes in ({"preserve_background": "true"}, {"candidate_revision": True}, {"source_revision": -1}):
            with self.assertRaises(ValidationError):
                TransformRequest.model_validate({**request(), **changes})

    def test_unknown_keys_filters_options_rejected(self):
        for changes in (
            {"filter_type": "made_up"},
            {"url": "https://arbitrary.invalid"},
            {"options": {"color_hex": "#AABBCC"}},
        ):
            with self.assertRaises(ValidationError):
                TransformRequest.model_validate({**request(), **changes})

    def test_upload_caps(self):
        base = dict(mime_type="image/jpeg", byte_length=100, checksum_sha256="a" * 64, consent_receipt_id=A)
        UploadRequest.model_validate(base)
        for changes in (
            {"byte_length": 10485761},
            {"byte_length": True},
            {"mime_type": "image/svg+xml"},
            {"checksum_sha256": "bad"},
        ):
            with self.assertRaises(ValidationError):
                UploadRequest.model_validate({**base, **changes})

    def test_result_and_progress_constraints(self):
        JobPayload.model_validate(job())
        for changes in (
            {"result_cdn_url": "https://private.invalid/result"},
            {"progress_percent": 25.0},
            {"progress_source": "complete", "progress_percent": 99.0},
        ):
            with self.assertRaises(ValidationError):
                JobPayload.model_validate({**job(), **changes})

    def test_openapi_covers_required_routes_and_auth(self):
        doc = api.app.openapi()
        self.assertEqual(doc["openapi"], "3.1.0")
        for path, method in [
            ("/api/v1/faces/upload-url", "post"),
            ("/api/v1/faces/transform", "post"),
            ("/api/v1/faces/jobs/{job_id}", "get"),
        ]:
            operation = doc["paths"][path][method]
            self.assertIn("security", operation)
            self.assertIn("422", operation["responses"])
        params = doc["paths"]["/api/v1/faces/transform"]["post"]["parameters"]
        self.assertTrue(any(p["name"] == "Idempotency-Key" and p["required"] for p in params))

    def test_shell_fails_closed_and_no_store(self):
        with TestClient(api.app) as client:
            self.assertFalse(client.get("/health").json()["runtime_configured"])
            r = client.post(
                "/api/v1/faces/transform",
                json=request(),
                headers={"Authorization": "Bearer test", "Idempotency-Key": "test-key-00000001"},
            )
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["code"], "SERVICE_NOT_CONFIGURED")
            self.assertEqual(r.headers["cache-control"], "no-store")

    def test_missing_auth_401(self):
        with TestClient(api.app) as client:
            self.assertEqual(client.get(f"/api/v1/faces/jobs/{A}").status_code, 401)

    def test_validation_errors_do_not_echo_inputs(self):
        api.app.state.runtime = AuthOnlyTestRuntime()
        with TestClient(api.app) as client:
            r = client.post(
                "/api/v1/faces/transform",
                json={**request(), "intensity": "SECRET_SENTINEL"},
                headers={"Authorization": "Bearer test", "Idempotency-Key": "test-key-00000001"},
            )
            self.assertEqual(r.status_code, 422)
            self.assertEqual(r.json()["code"], "VALIDATION_ERROR")
            self.assertNotIn("SECRET_SENTINEL", r.text)

    def test_filter_inventory_and_json_schema_validity(self):
        entries = json.loads((R / "assets/filters.json").read_text())
        ids = {x["id"] for x in entries}
        enum = set(TransformRequest.model_json_schema()["properties"]["filter_type"]["enum"])
        self.assertEqual(ids, enum)
        self.assertEqual(len(entries), 12)
        for file in (R / "packages/shared-types/json-schema").glob("*.json"):
            Draft202012Validator.check_schema(json.loads(file.read_text()))


if __name__ == "__main__":
    unittest.main()
