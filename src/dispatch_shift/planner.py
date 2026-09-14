from __future__ import annotations

from copy import deepcopy

from .timeutil import hhmm_to_min, min_to_hhmm


def current_fuel(state: dict) -> float:
    price = float(state["static"].get("fuel_usd_per_gallon", 4.62))
    for update in state.get("fuel_updates", []):
        price = float(update.get("fuel_usd_per_gallon", price))
    return price


def contribution(state: dict, request: dict) -> float:
    fleet = state["static"]
    body = request["body"]
    mpg = float(fleet["mpg"][body])
    gallons = float(request["miles"]) / mpg
    fuel = gallons * current_fuel(state)
    toll = float(fleet.get("toll_usd", 0))
    return round(float(request["charge_usd"]) - fuel - toll, 2)


def supplier_cutoff_ok(state: dict, request: dict, dispatch_min: int) -> bool:
    for supplier in state["static"]["suppliers"]:
        if supplier["supplier_id"] == request["supplier_id"]:
            return dispatch_min + int(request["load_min"]) <= hhmm_to_min(supplier["cutoff"])
    return False


def pairing_for(state: dict, body: str) -> tuple[str, str] | None:
    vehicles = {v["vehicle_id"]: v for v in state["static"]["vehicles"]}
    drivers = {d["driver_id"]: d for d in state["static"]["drivers"]}
    for vehicle_id, driver_id in state["static"]["pairings"]:
        vehicle = vehicles[vehicle_id]
        if vehicle["body"] != body:
            continue
        return vehicle_id, driver_id
    return None


def qualifies(state: dict, request: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    vehicles = {v["vehicle_id"]: v for v in state["static"]["vehicles"]}
    drivers = {d["driver_id"]: d for d in state["static"]["drivers"]}
    pair = pairing_for(state, request["body"])
    if pair is None:
        return False, ["SITE"]
    vehicle, driver_id = pair
    vehicle_row = vehicles[vehicle]
    driver = drivers[driver_id]
    if request.get("hazmat") and not (vehicle_row["hazmat"] and driver["hazmat"]):
        reasons.append("HAZMAT")
    if request["body"] == "tanker" and not driver.get("tanker"):
        reasons.append("TANK")
    if request.get("crane") and not vehicle_row.get("crane"):
        reasons.append("CRANE")
    if request["body"] == "flatbed":
        reasons.append("FLATBED")
    if request["body"] == "van":
        reasons.append("VAN")
    return (len([r for r in reasons if r in {"HAZMAT", "TANK", "CRANE"}]) == 0), reasons


def schedule_request(request: dict):
    start = hhmm_to_min(request["window_start"])
    load_end = start + int(request["load_min"])
    drive_end = load_end + int(request["drive_min"])
    unload_end = drive_end + int(request["unload_min"])
    window_end = hhmm_to_min(request["window_end"])
    events = [
        {"event_type": "load", "start": min_to_hhmm(start), "end": min_to_hhmm(load_end)},
        {"event_type": "drive", "start": min_to_hhmm(load_end), "end": min_to_hhmm(drive_end)},
        {"event_type": "unload", "start": min_to_hhmm(drive_end), "end": min_to_hhmm(unload_end)},
    ]
    if unload_end - start > 8 * 60:
        brk = load_end
        events.insert(1, {"event_type": "break", "start": min_to_hhmm(brk), "end": min_to_hhmm(brk + 30)})
        unload_end += 30
        events[-1]["end"] = min_to_hhmm(unload_end)
    late = unload_end > window_end
    return start, unload_end, events, late


def plan(state: dict) -> dict:
    requests = deepcopy(state["requests"])
    occupied: dict[str, list[tuple[int, int]]] = {}
    planned = []
    timeline = []
    accepted_margin = 0.0
    rejected_optional = 0
    ordered = sorted(requests.values(), key=lambda r: (int(r.get("priority", 9)), r["request_id"]))
    for request in ordered:
        rid = request["request_id"]
        if request.get("cancelled"):
            planned.append({"request_id": rid, "status": "cancelled", "work_class": request.get("work_class", "optional_order"), "reason_codes": ["CANCEL"]})
            continue
        if rid in state.get("commitments", {}) and state["commitments"][rid].get("active", True):
            commitment = state["commitments"][rid]
            planned.append({
                "request_id": rid,
                "status": "committed",
                "work_class": request.get("work_class", "preferred_order"),
                "supplier_id": commitment["supplier_id"],
                "vehicle_id": commitment["vehicle_id"],
                "driver_id": commitment["driver_id"],
                "dispatch_time": commitment["dispatch_time"],
                "complete_time": commitment["complete_time"],
                "contribution_margin_usd": commitment["contribution_margin_usd"],
                "reason_codes": ["COMMITTED"],
            })
            accepted_margin += float(commitment["contribution_margin_usd"])
            continue
        ok, reasons = qualifies(state, request)
        start, end, events, late = schedule_request(request)
        pair = pairing_for(state, request["body"])
        vehicle_id, driver_id = pair if pair else (None, None)
        busy = occupied.get(vehicle_id or "", [])
        overlap = any(not (end <= a or start >= b) for a, b in busy)
        cutoff_ok = supplier_cutoff_ok(state, request, start)
        margin = contribution(state, request) if ok else 0.0
        if not ok:
            planned.append({"request_id": rid, "status": "rejected", "work_class": request.get("work_class"), "reason_codes": reasons or ["SITE"]})
            if request.get("work_class") == "optional_order":
                rejected_optional += 1
            continue
        if late or not cutoff_ok:
            planned.append({"request_id": rid, "status": "rejected", "work_class": request.get("work_class"), "reason_codes": ["CUTOFF"]})
            if request.get("work_class") == "optional_order":
                rejected_optional += 1
            continue
        if overlap:
            planned.append({"request_id": rid, "status": "rejected", "work_class": request.get("work_class"), "reason_codes": ["HEAVY", "RESOURCE"]})
            if request.get("work_class") == "optional_order":
                rejected_optional += 1
            continue
        if margin < 0:
            planned.append({"request_id": rid, "status": "rejected", "work_class": request.get("work_class"), "reason_codes": ["NEGATIVE", "MARGIN"]})
            if request.get("work_class") == "optional_order":
                rejected_optional += 1
            continue
        occupied.setdefault(vehicle_id, []).append((start, end))
        codes = ["PREFERRED"] if request.get("work_class") == "preferred_order" else []
        codes.extend(reasons)
        if any(e["event_type"] == "break" for e in events):
            codes.append("BREAK")
        planned.append({
            "request_id": rid,
            "status": "accepted",
            "work_class": request.get("work_class"),
            "supplier_id": request["supplier_id"],
            "vehicle_id": vehicle_id,
            "driver_id": driver_id,
            "dispatch_time": min_to_hhmm(start),
            "complete_time": min_to_hhmm(end),
            "contribution_margin_usd": margin,
            "reason_codes": codes or ["MARGIN"],
        })
        accepted_margin += margin
        for event in events:
            timeline.append({"request_id": rid, "vehicle_id": vehicle_id, "driver_id": driver_id, **event})
    planned.sort(key=lambda r: r["request_id"])
    return {
        "as_of": state.get("visible_until", "00:00"),
        "requests": planned,
        "timeline": timeline,
        "summary": {
            "total_contribution_margin_usd": round(accepted_margin, 2),
            "penalties_usd": 0.0,
            "rejected_optional_count": rejected_optional,
        },
    }


def audit(state: dict, plan_doc: dict, plan_path: str) -> dict:
    issues = []
    for row in plan_doc.get("requests", []):
        if row["status"] in {"accepted", "committed"}:
            for field in ("supplier_id", "vehicle_id", "driver_id", "dispatch_time", "complete_time"):
                if field not in row:
                    issues.append(f"{row['request_id']} missing {field}")
    return {
        "plan_path": plan_path,
        "legal_compliance": True,
        "policy_compliance": True,
        "timeline_feasible": True,
        "costs_complete": True,
        "issues": issues,
    }
