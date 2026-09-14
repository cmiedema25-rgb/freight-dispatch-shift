from pathlib import Path
import json

from dispatch_shift.cli import main

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "packet"


def test_shift_lifecycle(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    early = tmp_path / "early.json"
    late = tmp_path / "late.json"
    audit = tmp_path / "audit.json"

    assert main(["init", "--packet", str(PACKET), "--state", str(state)]) == 0
    assert main(["ingest", "--state", str(state), "--until", "06:30"]) == 0
    assert main(["plan", "--state", str(state), "--out", str(early)]) == 0
    assert main(["commit", "--state", str(state), "--plan", str(early), "--until", "07:00"]) == 0
    assert main(["ingest", "--state", str(state), "--until", "11:30"]) == 0
    assert main(["plan", "--state", str(state), "--out", str(late)]) == 0
    assert main(["audit", "--state", str(state), "--plan", str(late), "--out", str(audit)]) == 0

    early_doc = json.loads(early.read_text())
    late_doc = json.loads(late.read_text())
    ids_early = {r["request_id"] for r in early_doc["requests"]}
    assert {"R01", "R02", "R03", "R04"}.issubset(ids_early)
    assert "R06" not in ids_early
    statuses = {r["request_id"]: r["status"] for r in late_doc["requests"]}
    assert statuses["R01"] in {"accepted", "committed"}
    assert statuses["R02"] in {"accepted", "committed"}
    assert statuses["R03"] in {"accepted", "committed"}
    assert statuses["R05"] == "cancelled"
    assert statuses["R06"] == "rejected"
    assert late_doc["summary"]["penalties_usd"] == 0.0
    assert json.loads(audit.read_text())["issues"] == []
