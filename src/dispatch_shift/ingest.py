from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from .timeutil import hhmm_to_min


def load_packet_events(packet: Path) -> list[dict]:
    events_dir = packet / "events"
    rows = []
    if not events_dir.exists():
        return rows
    for path in sorted(events_dir.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def fetch_api_events(until: str) -> list[dict] | None:
    url = os.environ.get("DISPATCH_EVENT_API_URL")
    token = os.environ.get("DISPATCH_EVENT_API_TOKEN")
    if not url or not token:
        return None
    req = urllib.request.Request(
        f"{url.rstrip('/')}/events?until={until}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("events", [])


def apply_events(state: dict, events: list[dict], until: str) -> dict:
    cutoff = hhmm_to_min(until)
    seen = set(state["ingested_event_ids"])
    for event in events:
        if hhmm_to_min(event["visible_at"]) > cutoff:
            continue
        event_id = event["event_id"]
        if event_id in seen:
            continue
        seen.add(event_id)
        kind = event.get("event_type") or event.get("record_type")
        record = event.get("record", event)
        if kind == "fuel_update":
            state["fuel_updates"].append(record)
            continue
        request_id = event.get("request_id") or record.get("request_id")
        if not request_id:
            continue
        current = state["requests"].get(request_id, {})
        if kind == "request_update":
            current.update(record)
            if record.get("cancelled") and request_id in state["commitments"]:
                state["commitments"].pop(request_id, None)
        else:
            current.update(record)
            current.setdefault("request_id", request_id)
        state["requests"][request_id] = current
    state["ingested_event_ids"] = sorted(seen)
    state["visible_until"] = until
    return state
