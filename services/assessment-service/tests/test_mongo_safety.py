"""MongoDB destructive-op safety guards."""

from __future__ import annotations

import pytest

from assessment_service.infra.mongo_safety import assert_test_database_for_destructive_ops


def test_assert_test_database_for_destructive_ops_rejects_non_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGODB_DATABASE", "healuxa_assessment_prod")
    from assessment_service import config

    config.settings = config.Settings()
    with pytest.raises(RuntimeError, match="must contain 'test'"):
        assert_test_database_for_destructive_ops()


def test_assert_test_database_for_destructive_ops_allows_test_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGODB_DATABASE", "healuxa_assessment_test")
    from assessment_service import config

    config.settings = config.Settings()
    assert_test_database_for_destructive_ops()
