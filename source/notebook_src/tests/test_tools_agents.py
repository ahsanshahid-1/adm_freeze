import pytest

from adm import tasks as T
from adm.agents import Conversation, execute_run, parse_action
from adm.core import PILOT_LIMITS, GENERATION, SYSTEM_SPEC, instance_dirs
from adm.fixed import contract_graph
from adm.llm import MockLLM
from adm.tools import Budget, BudgetExceeded, ToolSession


def _session(paths, tmp_path, system="S0", inst=("D5", "T2", "C4", 0), limits=None):
    T.build_instance(paths, "development", inst[0], inst[1], inst[2], inst[3])
    d = instance_dirs(paths, "development", *inst)
    return ToolSession("t", d["visible"], d["trusted"], tmp_path / system, SYSTEM_SPEC[system],
                       Budget(limits or dict(PILOT_LIMITS)), {"estimator": 1, "agent": 2}), d


def test_sql_isolation(paths, tmp_path):
    s, d = _session(paths, tmp_path)
    priv = d["private"] / "labels_test.parquet"
    assert s.call("query_data", {"sql": "SELECT count(*) FROM block_a__v2__train"})["ok"]
    for sql in [f"SELECT * FROM read_parquet('{priv}')", f"COPY block_a__v2__train TO '/tmp/x.csv'",
                "INSTALL httpfs", "SELECT 1; SELECT 2", "SET enable_external_access=true",
                f"SELECT * FROM '{priv}'"]:
        r = s.call("query_data", {"sql": sql})
        assert not r["ok"], sql
    s.close()


def test_evaluation_cap_cache_and_budget(paths, tmp_path):
    s, _ = _session(paths, tmp_path, inst=("D5", "T1", "C0", 0))
    h = s.call("materialize_features", {"graph": contract_graph(s.contract, s.catalog)})["handle"]
    for c in s.contract["candidate_models"]:
        assert s.call("fit_evaluate", {"handle": h, "candidate": c})["ok"]
    assert s.call("fit_evaluate", {"handle": h, "candidate": "CL1"}).get("cached")
    s.handles["H2"] = s.handles[h]
    r = s.call("fit_evaluate", {"handle": "H2", "candidate": "CL1"})
    assert not r["ok"] and "limit" in r["error"]
    assert s.budget.evaluations == 6
    s.budget.limits["tool_calls"] = s.budget.tool_calls
    with pytest.raises(BudgetExceeded):
        s.call("list_sources", {})
    s.close()


def test_disabled_gates_do_not_leak(paths, tmp_path):
    s, _ = _session(paths, tmp_path, system="M0")
    obs = s.call("materialize_features", {"graph": contract_graph(s.contract, s.catalog)})
    assert "gate_verdicts" not in obs
    assert not s.call("quality_check", {"handle": obs["handle"]})["ok"]
    s.close()
    s2, _ = _session(paths, tmp_path, system="MQP")
    obs = s2.call("materialize_features", {"graph": contract_graph(s2.contract, s2.catalog)})
    assert {g["gate"] for g in obs["gate_verdicts"]} == {"quality", "provenance"}
    assert all(g["passed"] for g in obs["gate_verdicts"])
    s2.close()


def test_gates_detect_defects(paths, tmp_path):
    s, _ = _session(paths, tmp_path, system="MQP", inst=("D6", "T4", "C6", 0))
    g = contract_graph(s.contract, s.catalog)
    g["nodes"] = [dict(n, policy="latest_modified") if n["op"] == "load" else n for n in g["nodes"]]
    alias = {}
    nodes = []
    for n in g["nodes"]:
        n = {k: alias.get(v, v) if k == "input" else v for k, v in n.items()}
        if n["op"] == "to_canonical":
            alias[n["id"]] = n["input"]
            continue
        nodes.append(n)
    obs = s.call("materialize_features", {"graph": {"nodes": nodes, "output": g["output"]}})
    fails = {f["check"].split(":")[-1] if ":" in f["check"] else f["check"] for v in obs["gate_verdicts"] for f in v["failures"]}
    assert "canonical_units" in fails or "value_ranges" in fails
    assert any(c.startswith("authority") or "authority" in c for v in obs["gate_verdicts"] for c in [f["check"] for f in v["failures"]])
    s.close()


def test_conversation_trimming():
    c = Conversation("sys " * 100, "task " * 100)
    for k in range(50):
        c.add_assistant('{"a": %d}' % k, f"step {k}")
        c.add_user("obs " * 800)
    msgs = c.render(4000)
    total = sum(len(m["content"]) for m in msgs) / 3.2
    assert total < 4500
    assert msgs[0]["role"] == "system" and msgs[1]["role"] == "user" and msgs[-1]["role"] == "user"
    assert "Earlier steps" in msgs[1]["content"]
    roles = [m["role"] for m in msgs[1:]]
    assert all(roles[i] != roles[i + 1] for i in range(len(roles) - 1))


def test_parse_action():
    a, e = parse_action('noise {"thought": "x", "action": "list_sources", "args": {}} tail', "single")
    assert a["action"] == "list_sources" and e is None
    assert parse_action('{"thought": "x", "action": "delegate", "args": {}}', "single")[0] is None
    assert parse_action("not json", "miner")[0] is None


@pytest.mark.parametrize("system", ["F", "S0", "SQP", "M0", "MQP"])
def test_systems_reach_terminal_state(paths, tmp_path, system):
    s, _ = _session(paths, tmp_path, system=system, inst=("D6", "T6", "C6", 0))
    out = execute_run(s, system, SYSTEM_SPEC[system], MockLLM(5, invalid_rate=0.0), GENERATION, 7)
    assert out["terminal_state"] in ("SUBMITTED", "ABSTAINED", "BUDGET_EXCEEDED")
    assert not any(e.get("event") == "exception" for e in out["trace"]), out["trace"][-1]
