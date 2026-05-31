from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

REQUEST_COUNT = Counter(
    "healuxa_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
