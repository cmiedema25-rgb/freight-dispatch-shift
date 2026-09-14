.PHONY: verify demo

verify:
	python -m pip install -e ".[dev]" -q
	pytest -q

demo:
	rm -rf /tmp/northline-shift && mkdir -p /tmp/northline-shift/plans
	dispatch init --packet packet --state /tmp/northline-shift/state.json
	dispatch ingest --state /tmp/northline-shift/state.json --until 06:30
	dispatch plan --state /tmp/northline-shift/state.json --out /tmp/northline-shift/plans/morning.json
	dispatch commit --state /tmp/northline-shift/state.json --plan /tmp/northline-shift/plans/morning.json --until 07:00
	dispatch ingest --state /tmp/northline-shift/state.json --until 11:30
	dispatch plan --state /tmp/northline-shift/state.json --out /tmp/northline-shift/plans/midday.json
	dispatch audit --state /tmp/northline-shift/state.json --plan /tmp/northline-shift/plans/midday.json --out /tmp/northline-shift/audit.json
	python -c "import json; p=json.load(open('/tmp/northline-shift/plans/midday.json')); print(p['as_of'], p['summary'])"
