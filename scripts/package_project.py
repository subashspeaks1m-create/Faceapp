"""Package an immutable portable snapshot; do not include runtime secrets/cache."""

from pathlib import Path
import hashlib
import json
import zipfile

R = Path(__file__).resolve().parents[1]
OMIT = {"node_modules", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".git"}


def include(p: Path) -> bool:
    return (
        p.is_file() and not any(x in OMIT for x in p.relative_to(R).parts) and p.name != ".env" and p.suffix != ".pyc"
    )


files = sorted(p for p in R.rglob("*") if include(p) and p.name != "MANIFEST.json")
entries = [
    {"path": str(p.relative_to(R)), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in files
]
manifest = R / "MANIFEST.json"
manifest.write_text(
    json.dumps({"version": 2, "date": "2026-10-10", "model_weights_bundled": False, "files": entries}, indent=2) + "\n"
)
archive = R.parent / "FaceApp-Production-Spec-v2.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for p in [*files, manifest]:
        z.write(p, str(Path("FaceApp-Production-Spec-v2") / p.relative_to(R)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for e in entries:
        raw = z.read("FaceApp-Production-Spec-v2/" + e["path"])
        assert len(raw) == e["bytes"] and hashlib.sha256(raw).hexdigest() == e["sha256"]
print(json.dumps({"archive": str(archive), "file_count": len(entries) + 1, "bytes": archive.stat().st_size}))
