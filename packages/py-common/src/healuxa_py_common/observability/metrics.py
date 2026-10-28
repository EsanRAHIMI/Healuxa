from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

REQUEST_COUNT = Counter(
    "healuxa_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

OUTBOX_PUBLISHED = Counter("healuxa_outbox_published_total", "Outbox events published to JetStream", ["subject"])
OUTBOX_PUBLISH_FAILURES = Counter(
    "healuxa_outbox_publish_failures_total", "Outbox publish attempts that failed and were rescheduled", ["subject"]
)
EVENTS_CONSUMED = Counter(
    "healuxa_events_consumed_total", "Events handled by durable consumers", ["consumer", "outcome"]
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
