from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_state(packet: str) -> dict:
    return {
        "packet": packet,
        "visible_until": "00:00",
        "ingested_event_ids": [],
        "requests": {},
        "fuel_updates": [],
        "commitments": {},
        "static": {},
    }
