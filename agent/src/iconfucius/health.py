"""Shared AI provider health check via Statuspage.io."""

import logging
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

_log = logging.getLogger(__name__)

# Statuspage.io component names per provider
_STATUS_COMPONENTS = {
    "Anthropic": "Claude API (api.anthropic.com)",
}


def fetch_provider_health(provider: str, status_url: str) -> dict:
    """Fetch component status from a Statuspage.io summary API.

    Args:
        provider: AI provider name (e.g. "Anthropic").
        status_url: Base URL of the status page (e.g. "https://status.claude.com/").

    Returns:
        {"ok": True/False/None, "status_detail": "operational"/.../"unknown"}
    """
    try:
        summary_url = f"{status_url}api/v2/summary.json"
        req = Request(summary_url, headers={"User-Agent": "iconfucius"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        component_name = _STATUS_COMPONENTS.get(provider, "")
        component_status = None
        for comp in data.get("components", []):
            if comp.get("name") == component_name:
                component_status = comp.get("status", "unknown")
                break

        ok = component_status == "operational" if component_status else None
        return {"ok": ok, "status_detail": component_status or "unknown"}
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        _log.debug("Health check failed for %s: %s", provider, exc)
        return {"ok": None, "status_detail": "unknown"}
