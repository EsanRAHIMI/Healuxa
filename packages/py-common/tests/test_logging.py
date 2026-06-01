from __future__ import annotations

import logging

from healuxa_py_common.observability.tracing import TraceIdFilter, configure_logging


def test_trace_id_filter_defaults_missing_trace_id() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request started",
        args=(),
        exc_info=None,
    )
    assert not hasattr(record, "trace_id")
    assert TraceIdFilter().filter(record) is True
    assert record.trace_id == "-"
    assert "%(trace_id)s" % record.__dict__ == "-"


def test_configure_logging_formats_third_party_record() -> None:
    configure_logging("test-service", "INFO")
    logger = logging.getLogger("httpx")
    # Must not raise KeyError / ValueError during formatting.
    logger.info("smoke log line")
