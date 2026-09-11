"""Evidence workflow and localization API surface for RF Finder."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from app.evidence_api import investigation_report, localization_payload


def evidence_routes(handler: BaseHTTPRequestHandler, service, api_auth, investigation_store):
    """Handle evidence/localization routes from an existing RF Finder handler."""
    path = urlparse(handler.path).path
    if path.startswith("/api/investigations/") and path.endswith("/report"):
        api_auth.require(handler.headers.get("Authorization"), "investigation.read")
        iid = int(path.split("/")[3])
        payload = investigation_report(investigation_store, service.store, iid)
        return payload, 200 if payload else 404
    if path.startswith("/api/investigations/") and path.endswith("/observations"):
        api_auth.require(handler.headers.get("Authorization"), "investigation.write")
        iid = int(path.split("/")[3])
        length = int(handler.headers.get("Content-Length", "0"))
        data = json.loads(handler.rfile.read(length)) if length else {}
        if not investigation_store.attach_observation(iid, int(data["observation_id"])):
            return {"error": "investigation not found"}, 404
        return investigation_store.get(iid), 200
    if path == "/api/localization/heatmap":
        api_auth.require(handler.headers.get("Authorization"), "rf.read")
        return localization_payload(service.store)["heatmap"], 200
    if path == "/api/localization/tracks":
        api_auth.require(handler.headers.get("Authorization"), "rf.read")
        return {"tracks": localization_payload(service.store)["tracks"]}, 200
    return None
