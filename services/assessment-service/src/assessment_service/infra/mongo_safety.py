from __future__ import annotations

from assessment_service import config


def assert_test_database_for_destructive_ops() -> None:
    """Refuse destructive cleanup unless the configured database name contains 'test'."""
    name = config.settings.mongodb_database
    if "test" not in name.lower():
        raise RuntimeError(
            f"Refusing destructive MongoDB cleanup: MONGODB_DATABASE={name!r} "
            "must contain 'test' (e.g. healuxa_assessment_test)"
        )
