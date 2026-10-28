"""Injected identity headers must never be trusted without proof that the edge set them."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from healuxa_py_common.middleware.auth import EDGE_SECRET_ENV, EDGE_SECRET_HEADER, Principal, get_principal

FORGED = {"X-Healuxa-User": "victim", "X-Healuxa-Perms": "admin:all"}


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(principal: Principal | None = Depends(get_principal)) -> dict:
        return {"user": principal.user_id if principal else None}

    return TestClient(app)


def test_headers_ignored_when_no_edge_secret_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(EDGE_SECRET_ENV, raising=False)
    assert _client().get("/whoami", headers={**FORGED, EDGE_SECRET_HEADER: "anything"}).json() == {"user": None}


def test_headers_ignored_without_or_with_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EDGE_SECRET_ENV, "s3cret-edge")
    client = _client()
    assert client.get("/whoami", headers=FORGED).json() == {"user": None}
    assert client.get("/whoami", headers={**FORGED, EDGE_SECRET_HEADER: "guess"}).json() == {"user": None}


def test_headers_trusted_with_matching_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(EDGE_SECRET_ENV, "s3cret-edge")
    response = _client().get("/whoami", headers={**FORGED, EDGE_SECRET_HEADER: "s3cret-edge"})
    assert response.json() == {"user": "victim"}
