"""Prespecified analyses added before the freeze (freeze manifest: pre_freeze_decisions_20261112) that the frozen
pipeline's final report does not compute. Read-only on the state directory.

  (a) mixed-effects logistic regression of V on system (M0 vs MQP) with random intercepts for task and for
      family-repetition block (variational Bayes, statsmodels BinomialBayesMixedGLM);
  (b) the family-weighted block-bootstrap estimate of MQP - M0 with small-sample variance inflation n/(n-1);
  (c) per-family estimates with the leave-one-family-out range;
  (d) available versus enforced verification: use of the Tier-2 operations per system, by defect, and on Tier 1
      (false-alarm measure), from the trusted traces;
  (e) composition of budget-exhausted runs by system and tier.

Usage: python prespecified_extra.py STATE_DIR OUT_DIR EXPERIMENT [EXPERIMENT ...]
Run it with ~/paper_env/bin/python (has statsmodels); it never writes into STATE_DIR.
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import math
import os
import sys

import numpy as np
import pandas as pd

STATE, OUT, EXPS = os.path.expanduser(sys.argv[1]), os.path.expanduser(sys.argv[2]), sys.argv[3:]
OPS = ("authoritative_verified", "normalize_key", "infer_representation", "dedupe_key")
EXPLORE = ("list_sources", "inspect_schema", "profile_data", "query_data")
DRAWS, SEED = 10000, 20261030


def load(exp: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(f"{STATE}/outputs/runs/{exp}/*.json")):
        with open(p) as fh:
            out.append(json.load(fh))
    return out


def tier(cond: str) -> str:
    return "Tier 2" if str(cond).startswith("X") else "Tier 1"


def trace_summary(rec: dict) -> dict:
    """Operations used in any materialize_features graph, and tool-call composition, from the trusted trace."""
    used, tools = set(), collections.Counter()
    tp = rec.get("trace_path")
    path = os.path.join(STATE, tp) if tp else None
    if not path or not os.path.exists(path):
        return {"ops": used, "tools": tools, "trace": False}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") != "tool":
                continue
            tools[ev.get("tool")] += 1
            if ev.get("tool") != "materialize_features":
                continue
            g = (ev.get("args") or {}).get("graph") or {}
            for n in (g.get("nodes") or []) if isinstance(g, dict) else []:
                if not isinstance(n, dict):
                    continue
                if n.get("op") in ("normalize_key", "infer_representation"):
                    used.add(n["op"])
                elif n.get("op") == "load" and n.get("policy") == "authoritative_verified":
                    used.add("authoritative_verified")
                elif n.get("op") == "dedupe" and n.get("mode") == "key":
                    used.add("dedupe_key")
    return {"ops": used, "tools": tools, "trace": True}


# --------------------------------------------------------------------------- data
recs = [r for e in EXPS for r in load(e)]
recs = [r for r in recs if not str(r.get("condition_id", "")).startswith("N") and r.get("backbone_id") in ("A", "none")]
df = pd.DataFrame([{
    "run_id": r["run_id"], "exp": r["experiment_id"], "family": r["dataset_id"], "template": r["template_id"],
    "task": r["task_id"], "condition": r["condition_id"], "tier": tier(r["condition_id"]), "rep": r["repetition_id"],
    "system": r["system_id"], "V": int(r.get("verified_completion") or 0), "terminal": r.get("terminal_state"),
    "tokens": r.get("aggregate_tokens") or 0, "rec": r} for r in recs])
res = {"experiments": EXPS, "records": int(len(df)), "systems": sorted(df["system"].unique().tolist()) if len(df) else []}


def block_D(d: pd.DataFrame, a: str = "MQP", b: str = "M0") -> pd.DataFrame:
    if not {a, b} <= set(d["system"]):
        return pd.DataFrame()
    piv = d[d["system"].isin([a, b])].pivot_table(index=["family", "rep", "template", "condition"], columns="system",
                                                   values="V", aggfunc="first").dropna(subset=[a, b])
    diff = piv[a] - piv[b]
    D = diff.groupby(level=["family", "rep"]).mean().rename("D").reset_index()
    D["cells"] = diff.groupby(level=["family", "rep"]).size().to_numpy()
    return D


def estimate(D: pd.DataFrame) -> float:
    return float(D.groupby("family")["D"].mean().mean())


def boot(D: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    fams = {f: g["D"].to_numpy() for f, g in D.groupby("family")}
    st = np.array([np.mean([v[rng.integers(0, len(v), len(v))].mean() for v in fams.values()]) for _ in range(DRAWS)])
    n = min(len(v) for v in fams.values())
    sd = float(st.std(ddof=1))
    infl = math.sqrt(n / (n - 1)) if n > 1 else float("nan")
    est = estimate(D)
    return {"estimate_pp": 100 * est, "percentile_ci_pp": [100 * float(np.quantile(st, .025)), 100 * float(np.quantile(st, .975))],
            "bootstrap_sd_pp": 100 * sd, "reps_per_family_min": n, "inflation_factor": infl,
            "inflated_normal_ci_pp": [100 * (est - 1.96 * sd * infl), 100 * (est + 1.96 * sd * infl)]}


# --------------------------------------------------------------------------- (b) and (c)
if {"MQP", "M0"} <= set(df["system"]):
    for label, sub in [("all recoverable", df), ("Tier 1", df[df["tier"] == "Tier 1"]), ("Tier 2", df[df["tier"] == "Tier 2"]),
                       ("all excluding X4", df[~df["condition"].str.startswith("X4")])]:
        D = block_D(sub)
        if D.empty:
            continue
        fam = D.groupby("family")["D"].mean()
        lofo = {f: estimate(D[D["family"] != f]) for f in fam.index} if len(fam) > 1 else {}
        res.setdefault("H1_MQP_minus_M0", {})[label] = {
            **boot(D), "families": int(len(fam)), "blocks": int(len(D)), "paired_cells": int(D["cells"].sum()),
            "per_family_pp": {f: round(100 * v, 3) for f, v in fam.items()},
            "lofo_range_pp": [round(100 * min(lofo.values()), 3), round(100 * max(lofo.values()), 3)] if lofo else None}

# --------------------------------------------------------------------------- (a) mixed-effects logistic
try:
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
    d = df[df["system"].isin(["M0", "MQP"])].copy()
    d["is_MQP"] = (d["system"] == "MQP").astype(float)
    d["fblock"] = d["family"] + "_r" + d["rep"].astype(str)
    if d["V"].nunique() > 1 and d["is_MQP"].nunique() > 1:
        m = BinomialBayesMixedGLM.from_formula("V ~ is_MQP", {"task": "0 + C(task)", "block": "0 + C(fblock)"}, d)
        fit = m.fit_vb()
        names = list(m.exog_names)
        i = names.index("is_MQP")
        b, s = float(fit.fe_mean[i]), float(fit.fe_sd[i])
        res["mixed_effects_logistic"] = {
            "model": "V ~ is_MQP + (1|task) + (1|family-repetition block), M0 and MQP, variational Bayes",
            "n": int(len(d)), "log_odds_MQP_vs_M0": b, "posterior_sd": s,
            "approx_95_interval_log_odds": [b - 1.96 * s, b + 1.96 * s],
            "odds_ratio": math.exp(b), "odds_ratio_95": [math.exp(b - 1.96 * s), math.exp(b + 1.96 * s)],
            "random_effect_sd_log": {n_: float(v) for n_, v in zip(m.vcp_names, fit.vcp_mean)}}
    else:
        res["mixed_effects_logistic"] = {"note": "not estimable: V or system has no variation"}
except Exception as ex:  # report the failure instead of hiding it
    res["mixed_effects_logistic"] = {"error": f"{type(ex).__name__}: {ex}"[:300]}

# --------------------------------------------------------------------------- (d) and (e) from traces
agentic = df[df["system"] != "F"].copy()
summ = {rid: trace_summary(r) for rid, r in zip(agentic["run_id"], agentic["rec"])}
res["traces_missing"] = int(sum(1 for s in summ.values() if not s["trace"]))
up = {}
for (sys_, scope), g in agentic.assign(scope=np.where(agentic["tier"] == "Tier 1", "Tier 1",
                                                      agentic["condition"].str[:2])).groupby(["system", "scope"]):
    row = {"runs": int(len(g)), "verified": int(g["V"].sum())}
    for op in OPS:
        row[op] = int(sum(1 for rid in g["run_id"] if op in summ[rid]["ops"]))
    up.setdefault(sys_, {})[scope] = row
res["operation_use"] = up

comp = {}
be = agentic[agentic["terminal"] == "BUDGET_EXCEEDED"]
for (sys_, t), g in be.groupby(["system", "tier"]):
    tl = [summ[rid]["tools"] for rid in g["run_id"]]
    comp.setdefault(sys_, {})[t] = {
        "budget_exceeded_runs": int(len(g)), "of_runs": int(((agentic["system"] == sys_) & (agentic["tier"] == t)).sum()),
        "mean_tokens": round(float(g["tokens"].mean()), 1),
        "mean_explore_calls": round(float(np.mean([sum(c[k] for k in EXPLORE) for c in tl])), 2),
        "mean_materialize": round(float(np.mean([c["materialize_features"] for c in tl])), 2),
        "mean_fit_evaluate": round(float(np.mean([c["fit_evaluate"] for c in tl])), 2),
        "mean_gate_check_calls": round(float(np.mean([c["quality_check"] + c["provenance_check"] for c in tl])), 2),
        "runs_never_fitted": int(sum(1 for c in tl if c["fit_evaluate"] == 0))}
res["budget_exhausted_composition"] = comp

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/prespecified_extra.json", "w") as fh:
    json.dump(res, fh, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k not in ("operation_use", "budget_exhausted_composition")}, indent=1, default=str))
print("operation_use (system -> scope -> counts):")
for s_, v in up.items():
    print(" ", s_, v)
print("budget_exhausted_composition:")
for s_, v in comp.items():
    print(" ", s_, v)
