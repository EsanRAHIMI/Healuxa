"""Coarse client description for the access log: enough to recognise an access, not to track a person."""

from __future__ import annotations

import ipaddress

from fastapi import Request

_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)


def coarse_network(host: str | None) -> str | None:
    """IPv4 truncated to /24 and IPv6 to /48 — never the full address."""
    if not host:
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{address}/{prefix}", strict=False))


def coarse_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    if "Healuxa" in user_agent and ("Expo" in user_agent or "okhttp" in user_agent or "CFNetwork" in user_agent):
        return "Healuxa app"
    browser = next((name for token, name in _BROWSERS if token in user_agent), None)
    system = next((name for token, name in _SYSTEMS if token in user_agent), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Other"


def client_info(request: Request) -> dict[str, str | None]:
    # The web tier forwards the browser's address; uvicorn applies it only from trusted proxies.
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else None)
    return {"network": coarse_network(host), "agent": coarse_agent(request.headers.get("user-agent"))}
