# Freight Dispatch Shift

[![CI](https://github.com/cmiedema25-rgb/freight-dispatch-shift/actions/workflows/ci.yml/badge.svg)](https://github.com/cmiedema25-rgb/freight-dispatch-shift/actions/workflows/ci.yml)

Stateful construction-materials dispatch CLI for a regional desk. Same command shape as the Harbor / Terminal-Bench `freight-dispatch-shift` task (`init` / `ingest` / `plan` / `commit` / `audit`), rewritten as an Inland Empire packet instead of the EU ADR bench.

This is **not** a copy of the Terminal-Bench oracle. Packet, units, and policy are original: USD, California construction yards, hazmat/tanker/flatbed/van constraints, supplier cutoffs, and a contribution-margin check after fuel bulletin updates.

**Not a legality or ELD product.** Hours and hazmat flags are planning aids.

## Why it exists

The bench problem is the real one: you cannot plan a shift from a single static file. Requests, corrections, cancellations, and fuel prices arrive on a cutoff clock. Committed work has to stay frozen unless a later visible record cancels it. Optional work loses to preferred work when the only dump truck is already spoken for.

This repo is the working version of that desk for Northline-style ops, next to [LoadWatch](https://github.com/cmiedema25-rgb/loadwatch-shipment-exceptions) and [semi-truck-trip-planner](https://github.com/cmiedema25-rgb/semi-truck-trip-planner).

## Quick start

```bash
git clone https://github.com/cmiedema25-rgb/freight-dispatch-shift.git
cd freight-dispatch-shift
python -m pip install -e ".[dev]"
make verify
make demo
```

## CLI

```bash
dispatch init   --packet ./packet --state ./state.json
dispatch ingest --state ./state.json --until 06:30
dispatch plan   --state ./state.json --out ./plans/morning.json
dispatch commit --state ./state.json --plan ./plans/morning.json --until 07:00
dispatch ingest --state ./state.json --until 11:30
dispatch plan   --state ./state.json --out ./plans/midday.json
dispatch audit  --state ./state.json --plan ./plans/midday.json --out ./audit.json
```

If `DISPATCH_EVENT_API_URL` and `DISPATCH_EVENT_API_TOKEN` are set, `ingest` pulls from that feed. Otherwise it reads `packet/events/*.json` filtered by `visible_at`.

## Sample shift (2026-09-14)

| Request | Visible | What happens |
| --- | --- | --- |
| R01 Hemet base rock | 05:30 | Dump V01 / Reyes — preferred, accepted then committed |
| R02 Riverside steel | 05:45 | Flatbed + crane V02 / Nguyen — committed; window stretch at 09:15 |
| R03 Colton asphalt | 06:00 | Tanker + hazmat V03 / Hale |
| R04 Ontario van | 06:20 | Small van V04 / Ortiz |
| R05 Menifee extra dump | 07:10 | Rejected while V01 is on R01; cancelled at 11:05 |
| Fuel bulletin | 08:00 | $4.62 → $4.89/gal, margins recompute |
| R06 late Perris rock | 10:40 | Rejected `CUTOFF` — yard closed 15:30 |

## Policy (short)

1. Keep commitments unless a later event cancels them.
2. Preferred / committed work before optional.
3. Pair body type + hazmat/tanker/crane flags. No illegal unit.
4. Honor supplier load cutoffs and site windows.
5. One vehicle cannot overlap two live jobs.
6. Drop negative-margin optional work after the current fuel price.

## Layout

```text
src/dispatch_shift/   CLI, ingest, planner
packet/static/        fleet, drivers, yards
packet/events/        cutoff-scoped request and fuel records
tests/                full init→ingest→plan→commit→ingest→audit path
```

## License

MIT © Charles Miedema

Inspired by the public Terminal-Bench task description at
https://github.com/harbor-framework/terminal-bench/tree/main/tasks/freight-dispatch-shift
(Apache-2.0). This repository does not include Harbor packet files, oracle code, or verifier tests.
