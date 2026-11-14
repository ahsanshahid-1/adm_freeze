"""Pre-freeze diagnostics on pilot traces (read-only). Answers the review questions:
(a) why gated systems exhaust the token budget on X2 (gate-verdict size, check-tool calls, context growth);
(b) what preceded MQ's use of authoritative_verified on X4;
(c) whether budget-exhausted runs were close to finishing (censoring of the limit rule).
Usage: python3 trace_diagnostics.py STATE_DIR OUT_JSON"""
import collections, glob, gzip, json, os, statistics, sys

STATE, OUT = os.path.expanduser(sys.argv[1]), os.path.expanduser(sys.argv[2])


def events(rec):
    p = os.path.join(STATE, rec.get("trace_path") or "")
    if not rec.get("trace_path") or not os.path.exists(p):
        return []
    out = []
    with gzip.open(p, "rt") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def gate_chars(obs):
    if isinstance(obs, dict):
        return len(json.dumps(obs.get("gate_verdicts"))) if obs.get("gate_verdicts") else 0
    if isinstance(obs, str) and "gate_verdicts" in obs:
        return len(obs) - obs.index("gate_verdicts")
    return 0


def obs_chars(obs):
    return len(obs) if isinstance(obs, str) else len(json.dumps(obs))


rows = []
for p in sorted(glob.glob(f"{STATE}/outputs/runs/E0X2/*.json")) + sorted(glob.glob(f"{STATE}/outputs/runs/E0/*.json")) \
        + sorted(glob.glob(f"{STATE}/outputs/runs/E0S/*.json")):
    r = json.load(open(p))
    if r["system_id"] == "F":
        continue
    ev = events(r)
    models = [e for e in ev if e.get("event") == "model"]
    tools = [e for e in ev if e.get("event") == "tool"]
    tc = collections.Counter(e.get("tool") for e in tools)
    inp = [m.get("input_tokens") or 0 for m in models]
    first_av = next((i for i, e in enumerate(tools) if e.get("tool") == "materialize_features" and any(
        isinstance(n, dict) and n.get("op") == "load" and n.get("policy") == "authoritative_verified"
        for n in (((e.get("args") or {}).get("graph") or {}).get("nodes") or []))), None)
    pre_fail = []
    if first_av is not None:
        for e in tools[:first_av]:
            o = e.get("obs")
            if isinstance(o, dict):
                for g in o.get("gate_verdicts") or []:
                    pre_fail += [f["check"].split(":")[-1] if ":" in f["check"] and f["check"].split(":")[0] in ("train", "validation") else f["check"].split(":")[0]
                                 for f in g.get("failures", [])]
    rows.append({
        "exp": r["experiment_id"], "cond": r["condition_id"], "defect": r["condition_id"][:2], "sys": r["system_id"],
        "term": r["terminal_state"], "V": int(r.get("verified_completion") or 0), "tokens": r.get("aggregate_tokens") or 0,
        "calls": len(models), "mean_in": statistics.mean(inp) if inp else 0, "last_in": inp[-1] if inp else 0,
        "tool_calls": len(tools), "materialize": tc.get("materialize_features", 0), "fit": tc.get("fit_evaluate", 0),
        "check_tools": tc.get("quality_check", 0) + tc.get("provenance_check", 0),
        "profile_query": tc.get("profile_data", 0) + tc.get("query_data", 0) + tc.get("inspect_schema", 0) + tc.get("list_sources", 0),
        "delegate": sum(1 for e in ev if e.get("event") == "delegate"),
        "gate_chars": sum(gate_chars(e.get("obs")) for e in tools), "obs_chars": sum(obs_chars(e.get("obs")) for e in tools),
        "submitted_ever": int(any(e.get("tool") == "submit" for e in tools)),
        "fit_ok_before_end": int(tc.get("fit_evaluate", 0) > 0),
        "pre_av_failures": pre_fail, "used_av": first_av is not None, "repairs": r.get("repair_cycles") or 0,
    })


def agg(rs):
    if not rs:
        return None
    m = lambda k: round(statistics.mean([x[k] for x in rs]), 1)
    return {"n": len(rs), "V": sum(x["V"] for x in rs), "budget": sum(x["term"] == "BUDGET_EXCEEDED" for x in rs),
            "tokens": m("tokens"), "calls": m("calls"), "mean_in_per_call": m("mean_in"), "last_in": m("last_in"),
            "tool_calls": m("tool_calls"), "materialize": m("materialize"), "fit": m("fit"), "check_tools": m("check_tools"),
            "explore_tools": m("profile_query"), "delegations": m("delegate"), "gate_chars": m("gate_chars"),
            "obs_chars": m("obs_chars"), "repairs": m("repairs"),
            "budget_runs_with_fit": sum(1 for x in rs if x["term"] == "BUDGET_EXCEEDED" and x["fit"] > 0),
            "budget_runs_fit6": sum(1 for x in rs if x["term"] == "BUDGET_EXCEEDED" and x["fit"] >= 6)}


res = {"by_defect_system": {}, "tier1_by_system": {}, "budget_runs_by_defect_system": {}, "mq_x4": {}}
x2 = [x for x in rows if x["exp"] == "E0X2"]
for d in ("X2", "X3", "X4"):
    for s in ("S0", "M0", "MQ", "MP", "SQP", "MQP"):
        rs = [x for x in x2 if x["defect"] == d and x["sys"] == s]
        res["by_defect_system"][f"{d}/{s}"] = agg(rs)
        res["budget_runs_by_defect_system"][f"{d}/{s}"] = agg([x for x in rs if x["term"] == "BUDGET_EXCEEDED"])
t1 = [x for x in rows if x["exp"] in ("E0", "E0S")]
for s in ("S0", "M0", "MQ", "MP", "SQP", "MQP"):
    res["tier1_by_system"][s] = agg([x for x in t1 if x["sys"] == s])
mq = [x for x in x2 if x["defect"] == "X4" and x["sys"] == "MQ"]
res["mq_x4"] = {"runs": len(mq), "used_av": sum(x["used_av"] for x in mq),
                "verified": sum(x["V"] for x in mq), "verified_and_used_av": sum(1 for x in mq if x["V"] and x["used_av"]),
                "gate_failures_before_first_av": dict(collections.Counter(f for x in mq if x["used_av"] for f in set(x["pre_av_failures"]))),
                "av_runs_with_no_prior_gate_failure": sum(1 for x in mq if x["used_av"] and not x["pre_av_failures"])}
for s in ("M0", "S0"):
    rs = [x for x in x2 if x["defect"] == "X4" and x["sys"] == s]
    res[f"{s.lower()}_x4"] = {"runs": len(rs), "used_av": sum(x["used_av"] for x in rs), "verified": sum(x["V"] for x in rs)}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(res, open(OUT, "w"), indent=1)
for k in ("by_defect_system", "budget_runs_by_defect_system"):
    print("==", k)
    for kk, v in res[k].items():
        print(kk, v)
print("== tier1"); [print(k, v) for k, v in res["tier1_by_system"].items()]
print("== mq_x4", res["mq_x4"]); print("m0_x4", res["m0_x4"], "s0_x4", res["s0_x4"])
