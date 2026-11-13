import json
from pathlib import Path

import jsonschema

from adm import runner as R
from adm import tasks as T
from adm.core import GENERATION, PILOT_LIMITS, SessionClock, instance_dirs, read_json

SCHEMAS = Path(R.__file__).parent / "schemas"


def test_contract_matches_schema(paths):
    schema = json.loads((SCHEMAS / "task.schema.json").read_text())
    for tmpl in ["T1", "T3", "T6"]:
        T.build_instance(paths, "development", "D5", tmpl, "C1", 0)
        jsonschema.validate(read_json(instance_dirs(paths, "development", "D5", tmpl, "C1", 0)["visible"] / "contract.json"), schema)


def test_run_counts():
    assert len(R.experiment_runs("E0", [0, 1])) == 336
    assert len(R.experiment_runs("E1", [0, 1, 2])) == 5292
    assert len(R.experiment_runs("E4", [0, 1, 2])) == 378
    assert len(R.experiment_runs("E5", [0, 1, 2])) == 252
    assert len(R.experiment_runs("E7", [0, 1, 2])) == 216
    assert len(R.experiment_runs("E0X", [0])) == 756
    e0x2 = R.experiment_runs("E0X2", [1, 2])
    assert len(e0x2) == 1512 and len({r["run_id"] for r in e0x2}) == 1512
    assert {r["condition"] for r in e0x2} == {"X2a", "X2b", "X2c", "X3a", "X3b", "X3c", "X4a", "X4b", "X4c"}
    assert len(R.experiment_runs("E0S", [0, 1])) == 840 and len(R.experiment_runs("E0SB", [0, 1])) == 504
    e1 = R.experiment_runs("E1", [0])
    assert len({r["run_id"] for r in e1}) == len(e1)
    blocks = {}
    for r in e1:
        blocks.setdefault(r["block"], []).append(r["system"])
    assert all(sorted(v) == sorted(["F", "S0", "M0", "MQ", "MP", "SQP", "MQP"]) for v in blocks.values())


def test_runner_resume_and_record_schema(paths):
    """Interrupt with a tiny session clock, resume, and check there are no duplicates or gaps."""
    schema = json.loads((SCHEMAS / "result.schema.json").read_text())
    runs = [r for r in R.experiment_runs("E0", [0]) if r["template"] == "T1" and r["family"] == "D6"][:7]
    keys = {(r["suite"], r["family"], r["template"], r["condition"], r["repetition"]) for r in runs}
    T.ensure_instances(paths, list(keys))
    cfg = {"limits": PILOT_LIMITS, "generation": GENERATION, "llm": {"mode": "mock", "invalid_rate": 0.0}, "fit_slots": 2}
    clock = SessionClock(stop_new_h=0.0)  # nothing may start
    st = R.Runner(paths, cfg, clock).execute(runs, concurrency=2)
    assert st["stopped_for_time"] and not R.load_records(paths, "E0")
    st = R.Runner(paths, cfg, SessionClock()).execute(runs, concurrency=4)
    recs = R.load_records(paths, "E0")
    assert sorted(r["run_id"] for r in recs) == sorted(r["run_id"] for r in runs)
    for rec in recs:
        jsonschema.validate(rec, schema)
        assert rec["exception_events"] == 0
    st = R.Runner(paths, cfg, SessionClock()).execute(runs, concurrency=4)
    assert st["pending_at_start"] == 0
