from healuxa_py_common.errors import ApiError, error_response
from healuxa_py_common.observability.tracing import get_trace_id


def test_error_response_shape() -> None:
    body = error_response(
        status=422,
        code="validation_error",
        title="Validation failed",
        trace_id="trace-123",
        detail="field invalid",
    )
    assert body["code"] == "validation_error"
    assert body["status"] == 422
    assert body["trace_id"] == "trace-123"


def test_api_error_attributes() -> None:
    err = ApiError(status=404, code="not_found", title="Not found")
    assert err.status == 404
    assert err.code == "not_found"
    assert get_trace_id()
