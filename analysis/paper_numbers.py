"""Compute every pilot number cited in the draft paper from the raw run records (runs on the CRC server).

Read-only: it never modifies the state directory. Output: paper_numbers.json and paper_numbers.md in OUT_DIR.
Usage: python3 paper_numbers.py STATE_DIR ARCHIVE_DIR OUT_DIR
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import math
import os
import statistics
import sys

STATE, ARCHIVE, OUT = (os.path.expanduser(a) for a in sys.argv[1:4])
SYSTEMS = ["F", "S0", "M0", "MQ", "MP", "SQP", "MQP"]
TIER1 = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
FROZEN_T2 = ["X2b", "X3a", "X4b"]
TIER2_OPS = ("normalize_key", "infer_representation", "authoritative_verified", "dedupe_key")


def load_runs(pattern: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(pattern)):
        with open(p) as fh:
            r = json.load(fh)
        r["_path"] = p
        out.append(r)
    return out


def pct(values, q):
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def summarize(runs: list[dict]) -> dict:
    n = len(runs)
    ver = sum(int(r.get("verified_completion") or 0) for r in runs)
    term = collections.Counter(r.get("terminal_state") for r in runs)
    fail = collections.Counter(r.get("first_failure") for r in runs if r.get("first_failure"))
    agentic = [r for r in runs if r.get("system_id") != "F"]
    tok = [r.get("aggregate_tokens") or 0 for r in agentic]
    act = [r.get("active_seconds") or 0 for r in runs]
    sub = term.get("SUBMITTED", 0)
    invalid = sum(1 for r in runs if r.get("terminal_state") == "SUBMITTED" and not r.get("verified_completion"))
    return {"n": n, "verified": ver, "vcr": round(ver / n, 4) if n else None,
            "terminal": dict(term), "first_failure": dict(fail),
            "invalid_submission_rate": round(invalid / n, 4) if n else None,
            "submission_error_rate": round(invalid / sub, 4) if sub else None,
            "tokens_mean": round(statistics.mean(tok), 1) if tok else None,
            "tokens_median": pct(tok, 0.5), "tokens_p90": pct(tok, 0.9),
            "active_s_mean": round(statistics.mean(act), 1) if act else None,
            "active_s_median": pct(act, 0.5),
            "model_calls_mean": round(statistics.mean([r.get("model_calls") or 0 for r in runs]), 2) if runs else None,
            "gate_calls_mean": round(statistics.mean([r.get("gate_calls") or 0 for r in runs]), 2) if runs else None,
            "exception_runs": sum(1 for r in runs if (r.get("exception_events") or 0) > 0)}


def by(runs, *keys):
    g = collections.defaultdict(list)
    for r in runs:
        g[tuple(r.get(k) for k in keys)].append(r)
    return g


def paired(runs, a, b):
    """Mean paired difference V_a - V_b over blocks (task, condition, repetition) where both systems ran."""
    cells = collections.defaultdict(dict)
    for r in runs:
        cells[(r["task_id"], r["condition_id"], r["repetition_id"])][r["system_id"]] = int(r.get("verified_completion") or 0)
    d = [c[a] - c[b] for c in cells.values() if a in c and b in c]
    return {"pairs": len(d), "diff_pp": round(100 * statistics.mean(d), 2) if d else None,
            "a_better": sum(1 for x in d if x > 0), "b_better": sum(1 for x in d if x < 0)}


def trace_ops(r) -> set[str]:
    """Tier-2 operations used in any materialize_features graph of the run (from the trusted trace)."""
    tp = r.get("trace_path")
    used = set()
    if not tp:
        return used
    p = os.path.join(STATE, tp)
    if not os.path.exists(p):
        return {"<no trace>"}
    with gzip.open(p, "rt") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") != "tool" or ev.get("tool") != "materialize_features":
                continue
            g = (ev.get("args") or {}).get("graph") or {}
            for n in g.get("nodes", []) if isinstance(g, dict) else []:
                if not isinstance(n, dict):
                    continue
                if n.get("op") in ("normalize_key", "infer_representation"):
                    used.add(n["op"])
                if n.get("op") == "load" and n.get("policy") == "authoritative_verified":
                    used.add("authoritative_verified")
                if n.get("op") == "dedupe" and n.get("mode") == "key":
                    used.add("dedupe_key")
    return used


def op_usage(runs) -> dict:
    out = {}
    for (s,), rs in sorted(by(runs, "system_id").items()):
        if s == "F":
            continue
        cnt = collections.Counter()
        for r in rs:
            for o in trace_ops(r):
                cnt[o] += 1
        out[s] = {"runs": len(rs), **{o: cnt.get(o, 0) for o in TIER2_OPS}, "no_trace": cnt.get("<no trace>", 0)}
    return out


def table(runs, cond_order) -> dict:
    t = {}
    for s in SYSTEMS:
        rs = [r for r in runs if r["system_id"] == s]
        if not rs:
            continue
        row = {"all": summarize(rs)}
        for c in cond_order:
            rc = [r for r in rs if r["condition_id"] == c]
            if rc:
                row[c] = {"n": len(rc), "verified": sum(int(r.get("verified_completion") or 0) for r in rc)}
        t[s] = row
    return t


res = {"state_dir": STATE, "experiments": {}}
EXPS = {"E0": TIER1, "E0S": TIER1, "E0SB": TIER1, "E0X": ["X1a", "X1b", "X1c", "X2a", "X2b", "X2c", "X3a", "X3b", "X3c"],
        "E0X2": ["X2a", "X2b", "X2c", "X3a", "X3b", "X3c", "X4a", "X4b", "X4c"]}
runs_all = {}
for e, conds in EXPS.items():
    rs = [r for r in load_runs(f"{STATE}/outputs/runs/{e}/*.json") if r.get("suite") != "smoke"]
    runs_all[e] = rs
    res["experiments"][e] = {
        "runs": len(rs), "backbones": dict(collections.Counter(r.get("backbone_id") for r in rs)),
        "models": dict(collections.Counter(f"{r.get('model_repo')}@{(r.get('model_revision') or '')[:12]}" for r in rs)),
        "repetitions": sorted({r.get("repetition_id") for r in rs}),
        "tasks": sorted({r.get("task_id") for r in rs}),
        "limits": sorted({json.dumps(r.get("limits"), sort_keys=True) for r in rs}),
        "table": table(rs, conds),
        "paired": {f"{a}-{b}": paired(rs, a, b) for a, b in
                   [("MQP", "M0"), ("MQP", "SQP"), ("MQP", "F"), ("SQP", "S0"), ("M0", "S0"), ("MQ", "M0"), ("MP", "M0")]},
        "first_start": min((r.get("start_time") or "~") for r in rs) if rs else None,
        "last_start": max((r.get("start_time") or "") for r in rs) if rs else None,
    }

# E0X2 calibration and repetition agreement
x2 = runs_all["E0X2"]
cal = {}
for c in EXPS["E0X2"]:
    rc = [r for r in x2 if r["condition_id"] == c and r["system_id"] in ("S0", "M0")]
    cal[c] = {"n": len(rc), "vcr_S0_M0": round(sum(int(r.get("verified_completion") or 0) for r in rc) / len(rc), 4) if rc else None}
res["e0x2_calibration"] = cal
res["e0x2_rep_agreement"] = {str(k[0]): summarize(v)["vcr"] for k, v in sorted(by([r for r in x2 if r["system_id"] != "F"], "repetition_id").items())}
res["e0x2_frozen_levels"] = table([r for r in x2 if r["condition_id"] in FROZEN_T2], FROZEN_T2)
res["e0x2_by_defect"] = {}
res["e0x2_detail_by_defect"] = {}
for d in ("X2", "X3", "X4"):
    rd = [r for r in x2 if r["condition_id"].startswith(d)]
    res["e0x2_by_defect"][d] = {s: summarize([r for r in rd if r["system_id"] == s])["vcr"] for s in SYSTEMS}
    det = {}
    for s in SYSTEMS:
        rs = [r for r in rd if r["system_id"] == s]
        sm = summarize(rs)
        det[s] = {"n": sm["n"], "verified": sm["verified"], "terminal": sm["terminal"], "first_failure": sm["first_failure"],
                  "mean_repairs": round(statistics.mean([r.get("repair_cycles") or 0 for r in rs]), 3) if rs else None,
                  "mean_gate_calls": sm["gate_calls_mean"], "tokens_mean": sm["tokens_mean"]}
    res["e0x2_detail_by_defect"][d] = det
# Exception (pipeline-crash) runs by experiment and backbone
res["exception_runs"] = {e: dict(collections.Counter(r.get("backbone_id") for r in rs if (r.get("exception_events") or 0) > 0))
                         for e, rs in runs_all.items()}
res["agentic_runs_by_backbone"] = {e: dict(collections.Counter(r.get("backbone_id") for r in rs if r.get("system_id") != "F"))
                                   for e, rs in runs_all.items()}

# Frozen-design pilot preview (backbone A): Tier 1 = E0 + E0S (C0-C6), Tier 2 = E0X2 at the frozen levels
t1 = [r for r in runs_all["E0"] + runs_all["E0S"] if r.get("backbone_id") != "B" and r["condition_id"] in TIER1]
t2 = [r for r in x2 if r["condition_id"] in FROZEN_T2]
res["frozen_design_preview"] = {
    "tier1": {s: summarize([r for r in t1 if r["system_id"] == s]) for s in SYSTEMS},
    "tier2": {s: summarize([r for r in t2 if r["system_id"] == s]) for s in SYSTEMS},
    "tier2_without_X4": {s: summarize([r for r in t2 if r["system_id"] == s and not r["condition_id"].startswith("X4")]) for s in SYSTEMS},
    "pooled": {s: summarize([r for r in t1 + t2 if r["system_id"] == s]) for s in SYSTEMS},
    "paired_pooled": {f"{a}-{b}": paired(t1 + t2, a, b) for a, b in [("MQP", "M0"), ("MQP", "SQP"), ("MQP", "F")]},
    "paired_tier1": {f"{a}-{b}": paired(t1, a, b) for a, b in [("MQP", "M0"), ("MQP", "SQP"), ("MQP", "F")]},
    "paired_tier2": {f"{a}-{b}": paired(t2, a, b) for a, b in [("MQP", "M0"), ("MQP", "SQP"), ("MQP", "F")]},
}

# Usage distribution behind the frozen limits (agentic runs ending SUBMITTED or ABSTAINED, frozen-design conditions)
pool = [r for r in t1 + t2 if r["system_id"] != "F" and r.get("terminal_state") in ("SUBMITTED", "ABSTAINED")]
res["limit_pool"] = {"n": len(pool), **{k: {"p50": pct([r.get(k) or 0 for r in pool], .5), "p90": pct([r.get(k) or 0 for r in pool], .9),
                                           "p95": pct([r.get(k) or 0 for r in pool], .95), "max": max([r.get(k) or 0 for r in pool], default=None)}
                                        for k in ("aggregate_tokens", "model_calls", "tool_calls", "active_seconds")}}
res["budget_exceeded_frozen_design"] = {s: sum(1 for r in t1 + t2 if r["system_id"] == s and r.get("terminal_state") == "BUDGET_EXCEEDED") for s in SYSTEMS}

# Use of Tier-2 operations: Tier 1 (false-alarm measure) and Tier 2
res["tier2_op_usage"] = {"tier1_E0_E0S": op_usage(t1), "tier2_E0X2_all_levels": op_usage(x2)}
res["tier2_op_usage_by_defect"] = {d: op_usage([r for r in x2 if r["condition_id"].startswith(d)]) for d in ("X2", "X3", "X4")}

# Archived E0SB versions
arch = {}
for p in sorted(glob.glob(f"{ARCHIVE}/*")):
    rs = [r for r in load_runs(f"{p}/**/E0SB*.json") if r.get("experiment_id") == "E0SB"] if os.path.isdir(p) else []
    if not rs:
        rs = [r for r in (load_runs(f"{p}/**/*.json") if os.path.isdir(p) else []) if r.get("experiment_id") == "E0SB"]
    if rs:
        arch[os.path.basename(p)] = {"runs": len(rs), "by_system": {s: summarize([r for r in rs if r["system_id"] == s]) for s in ("M0", "SQP", "MQP")}}
res["e0sb_archived"] = arch

# GPU accounting
gp = f"{STATE}/outputs/gpu_accounting.jsonl"
rows = []
if os.path.exists(gp):
    for line in open(gp):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
res["gpu_accounting"] = {"records": rows}

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/paper_numbers.json", "w") as fh:
    json.dump(res, fh, indent=1, default=str)

lines = ["# Pilot numbers for the paper (computed from raw run records)", ""]
for e, d in res["experiments"].items():
    lines.append(f"## {e}: {d['runs']} runs; backbones {d['backbones']}; reps {d['repetitions']}; tasks {len(d['tasks'])}")
    for s, row in d["table"].items():
        a = row["all"]
        lines.append(f"- {s}: {a['verified']}/{a['n']} = {a['vcr']}; terminal {a['terminal']}; first failures {a['first_failure']}; "
                     f"tokens median {a['tokens_median']}; exceptions {a['exception_runs']}")
    lines.append(f"- paired: {d['paired']}")
    lines.append("")
for k in ("e0x2_calibration", "e0x2_rep_agreement", "e0x2_by_defect", "e0x2_detail_by_defect", "exception_runs",
          "agentic_runs_by_backbone", "limit_pool", "budget_exceeded_frozen_design",
          "tier2_op_usage", "tier2_op_usage_by_defect", "gpu_accounting"):
    lines += [f"## {k}", "```", json.dumps(res[k], indent=1, default=str), "```", ""]
fp = res["frozen_design_preview"]
lines.append("## frozen_design_preview (VCR)")
for part in ("tier1", "tier2", "tier2_without_X4", "pooled"):
    lines.append(f"- {part}: " + ", ".join(f"{s} {v['verified']}/{v['n']}={v['vcr']}" for s, v in fp[part].items() if v["n"]))
lines.append(f"- paired pooled {fp['paired_pooled']}")
lines.append(f"- paired tier1 {fp['paired_tier1']}")
lines.append(f"- paired tier2 {fp['paired_tier2']}")
lines.append("")
lines.append("## e0sb_archived")
for k, v in res["e0sb_archived"].items():
    lines.append(f"- {k}: {v['runs']} runs; " + ", ".join(f"{s} {x['verified']}/{x['n']}={x['vcr']} (exc {x['exception_runs']})" for s, x in v["by_system"].items()))
with open(f"{OUT}/paper_numbers.md", "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
