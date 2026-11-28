"""Every records route is in profile.openapi.yaml with the same method and operationId (and vice versa)."""

from __future__ import annotations

from pathlib import Path

import yaml

from profile_service.main import app

CONTRACT = Path(__file__).resolve().parents[3] / "packages/api-contracts/openapi/profile.openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def test_routes_match_contract() -> None:
    spec = yaml.safe_load(CONTRACT.read_text())
    contract = {
        (method.upper(), "/v1" + path, op["operationId"])
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method in METHODS
    }
    generated = app.openapi()["paths"]
    served = {
        (method.upper(), path.replace("{user_id}", "{userId}"), op["operationId"])
        for path, item in generated.items()
        if path.startswith("/v1/")
        for method, op in item.items()
        if method in METHODS
    }
    assert served == contract
