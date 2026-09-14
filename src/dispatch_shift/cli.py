from __future__ import annotations

import argparse
from pathlib import Path

from .ingest import apply_events, fetch_api_events, load_packet_events
from .planner import audit, plan
from .state import dump_json, empty_state, load_json


def cmd_init(args: argparse.Namespace) -> int:
    packet = Path(args.packet)
    state = empty_state(str(packet))
    fleet = packet / "static" / "fleet.json"
    if fleet.exists():
        state["static"] = load_json(fleet)
    dump_json(Path(args.state), state)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    events = fetch_api_events(args.until)
    if events is None:
        packet = Path(args.events) if args.events else Path(state["packet"])
        events = load_packet_events(packet)
    apply_events(state, events, args.until)
    dump_json(Path(args.state), state)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    dump_json(Path(args.out), plan(state))
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    plan_doc = load_json(Path(args.plan))
    for row in plan_doc.get("requests", []):
        if row.get("status") != "accepted":
            continue
        state["commitments"][row["request_id"]] = {
            "active": True,
            "supplier_id": row["supplier_id"],
            "vehicle_id": row["vehicle_id"],
            "driver_id": row["driver_id"],
            "dispatch_time": row["dispatch_time"],
            "complete_time": row["complete_time"],
            "contribution_margin_usd": row["contribution_margin_usd"],
            "committed_until": args.until,
        }
    dump_json(Path(args.state), state)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state))
    plan_doc = load_json(Path(args.plan))
    dump_json(Path(args.out), audit(state, plan_doc, args.plan))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("--packet", required=True)
    init.add_argument("--state", required=True)
    init.set_defaults(func=cmd_init)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--state", required=True)
    ingest.add_argument("--until", required=True)
    ingest.add_argument("--events")
    ingest.set_defaults(func=cmd_ingest)

    plan_p = sub.add_parser("plan")
    plan_p.add_argument("--state", required=True)
    plan_p.add_argument("--out", required=True)
    plan_p.set_defaults(func=cmd_plan)

    commit = sub.add_parser("commit")
    commit.add_argument("--state", required=True)
    commit.add_argument("--plan", required=True)
    commit.add_argument("--until", required=True)
    commit.set_defaults(func=cmd_commit)

    aud = sub.add_parser("audit")
    aud.add_argument("--state", required=True)
    aud.add_argument("--plan", required=True)
    aud.add_argument("--out", required=True)
    aud.set_defaults(func=cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
