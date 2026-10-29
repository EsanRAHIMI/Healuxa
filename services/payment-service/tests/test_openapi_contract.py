"""The generated OpenAPI must expose exactly the operations of payment.openapi.yaml (under /v1)."""

from __future__ import annotations

import re
from pathlib import Path

from payment_service.main import app

CONTRACT = Path(__file__).resolve().parents[3] / "packages/api-contracts/openapi/payment.openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def contract_operations() -> set[tuple[str, str]]:
    ops: set[tuple[str, str]] = set()
    path = None
    in_paths = False
    for line in CONTRACT.read_text().splitlines():
        if line.startswith("paths:"):
            in_paths = True
            continue
        if in_paths and re.match(r"^\S", line):
            break
        if m := re.match(r"^  (/\S+):\s*$", line):
            path = re.sub(r"\{[^}]+\}", "{}", m.group(1))
        elif (m := re.match(r"^    (\w+):", line)) and m.group(1) in METHODS and path:
            ops.add((m.group(1), "/v1" + path))
    return ops


def app_operations() -> set[tuple[str, str]]:
    ops = set()
    for path, item in app.openapi()["paths"].items():
        if not path.startswith("/v1/"):
            continue
        for method in item:
            if method in METHODS:
                ops.add((method, re.sub(r"\{[^}]+\}", "{}", path)))
    return ops


def test_generated_paths_match_the_contract() -> None:
    contract, implemented = contract_operations(), app_operations()
    assert len(contract) >= 20
    assert implemented - contract == set(), "implemented but not in contract"
    assert contract - implemented == set(), "in contract but not implemented"
