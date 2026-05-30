"""Generate Pydantic v2 models from the event JSON Schemas.

Usage: python scripts/generate_python.py
Requires: pip install datamodel-code-generator
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
OUT = ROOT / "generated" / "healuxa_event_contracts"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "__init__.py").write_text(
        '"""AUTO-GENERATED Pydantic models. Do not edit."""\n', encoding="utf-8"
    )
    cmd = [
        sys.executable, "-m", "datamodel_code_generator",
        "--input", str(SCHEMAS),
        "--input-file-type", "jsonschema",
        "--output", str(OUT),
        "--output-model-type", "pydantic_v2.BaseModel",
        "--use-standard-collections",
        "--use-union-operator",
        "--field-constraints",
        "--enum-field-as-literal", "all",
        "--use-schema-description",
        "--disable-timestamp",
    ]
    print("running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
