"""Syntax and linked-asset checks; not a native/GPU/DB integration test."""

from pathlib import Path
import ast
import json
import xml.etree.ElementTree as ET
import yaml

R = Path(__file__).resolve().parents[1]
for f in R.rglob("*.py"):
    if ".venv" not in f.parts and "node_modules" not in f.parts:
        ast.parse(f.read_text(), filename=str(f))
for f in R.rglob("*.json"):
    if "node_modules" not in f.parts:
        json.loads(f.read_text())
filters = json.loads((R / "assets/filters.json").read_text())
assert len(filters) == 12 and len({x["id"] for x in filters}) == 12
for x in filters:
    assert 0 <= x["intensity_default"] <= 1
    assert (R / x["icon_reference"]).is_file()
for f in (R / "assets").rglob("*.svg"):
    ET.parse(f)
openapi = json.loads((R / "docs/openapi.json").read_text())
assert openapi["openapi"] == "3.1.0"
assert yaml.safe_load((R / "docs/openapi.yaml").read_text()) == openapi
compose = yaml.safe_load((R / "docker-compose.yml").read_text())
assert set(compose["services"]) == {"postgres", "redis", "s3", "migrate", "api", "worker", "daemons"}
# Executable migration copy must match the documented raw-constraint source.
doc_sql = (R / "docs/migration_constraints.sql").read_text().splitlines()[1:]
migration_sql = (R / "db/migrations/0002_constraints.sql").read_text().splitlines()[1:]
assert doc_sql == migration_sql, "db/migrations/0002_constraints.sql drifted from docs/migration_constraints.sql"
for f in (R / "assets/luts").glob("*.cube"):
    rows = f.read_text().splitlines()
    size = int(next(line.split()[1] for line in rows if line.startswith("LUT_3D_SIZE")))
    values = [[float(x) for x in line.split()] for line in rows if line and line[0].isdigit()]
    assert len(values) == size**3
    assert all(len(row) == 3 and all(0 <= v <= 1 for v in row) for row in values)
print("Python syntax, JSON/YAML, SVG, LUTs, 12 filter references, OpenAPI equivalence and migration copy passed.")
