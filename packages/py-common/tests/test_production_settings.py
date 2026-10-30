"""Production deployments must never start with missing or development-default secrets."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from healuxa_py_common.config import ServiceSettings


class Example(ServiceSettings):
    service_auth_client_secret: str = "dev-service-secret-change-me"
    password_pepper: str = ""
    jwt_private_key_pem: str | None = None


def test_development_allows_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    assert Example().service_auth_client_secret.startswith("dev-")


def test_production_rejects_defaults_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError) as excinfo:
        Example()
    message = str(excinfo.value)
    assert "SERVICE_AUTH_CLIENT_SECRET" in message and "PASSWORD_PEPPER" in message
    assert "JWT_PRIVATE_KEY_PEM" not in message


def test_production_accepts_real_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SERVICE_AUTH_CLIENT_SECRET", "9f2c1e7a4b8d4e6f9a0b3c5d7e1f2a4b")
    monkeypatch.setenv("PASSWORD_PEPPER", "c4a7e9b1d3f5a7c9e1b3d5f7a9c1e3b5")
    assert Example().app_env == "production"
