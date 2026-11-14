"""Pilot-based power simulation, limit calibration rule, protocol freeze and freeze verification
(Sections 15.6 and 23)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import block_bootstrap, estimate, recoverable
from .core import (FAMILIES, PILOT_LIMITS, PROTOCOL_LIMITS, TEMPLATES, CONDITIONS, Paths, json_hash, now_iso,
                   read_json, sha256_tree, write_json)

LIMIT_KEYS = {"aggregate_tokens": ("tokens", 1000), "model_calls": ("model_calls", 1), "tool_calls": ("tool_calls", 1),
              "wall_seconds": ("active_s", 30)}


def _logit(p):
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def simulate_power(p0: float, effect: float, reps: int, sd_family: float, sd_block: float, sims: int = 200,
                   draws: int = 400, seed: int = 7, n_conditions: int | None = None) -> float:
    """Simulate the planned paired analysis: Bernoulli completions with family and family-repetition
    random effects shared by both systems in a block; power = P(CI lower bound > 0)."""
    rng = np.random.default_rng(seed)
    mu0 = _logit(p0)
    mu1 = _logit(min(p0 + effect, 0.999))
    nf, cells = len(FAMILIES), len(TEMPLATES) * (n_conditions or len(CONDITIONS))
    hits = 0
    for s in range(sims):
        rows = []
        u = rng.normal(0, sd_family, nf)
        for f in range(nf):
            for r in range(reps):
                v = rng.normal(0, sd_block)
                w = rng.normal(0, 0.5, cells)
                p_a = 1 / (1 + np.exp(-(mu1 + u[f] + v + w)))
                p_b = 1 / (1 + np.exp(-(mu0 + u[f] + v + w)))
                d = (rng.random(cells) < p_a).astype(float) - (rng.random(cells) < p_b).astype(float)
                rows.append({"family": f, "rep": r, "D": d.mean()})
        D = pd.DataFrame(rows)
        bs = block_bootstrap(D, draws=draws, seed=int(rng.integers(0, 2**31 - 1)))
        hits += bs["ci_low"] > 0
    return hits / sims


def power_analysis(pilot: pd.DataFrame, out_dir: Path, rep_options=(3, 4, 5, 6), effect: float = 0.10,
                   sims: int = 200, n_conditions: int | None = None, out_name: str = "power_simulation.json") -> dict:
    d = recoverable(pilot)
    p0 = float(d.loc[d["system"] == "M0", "V"].mean()) if (d["system"] == "M0").any() else 0.5
    if not np.isfinite(p0):
        p0 = 0.5
    grid = []
    for sd_block in (0.25, 0.5, 1.0):
        for reps in rep_options:
            pw = simulate_power(p0, effect, reps, sd_family=0.5, sd_block=sd_block, sims=sims, seed=1000 + reps,
                                n_conditions=n_conditions)
            grid.append({"reps": reps, "sd_block_logit": sd_block, "power": pw})
    res = {"assumptions": {"baseline_vcr_M0_pilot": p0, "effect_pp": 100 * effect, "sd_family_logit": 0.5,
                           "sd_cell_logit": 0.5, "sims": sims,
                           "note": "Development pilot tasks differ from the evaluation portfolio; the variance model is an assumption."},
           "grid": grid, "time": now_iso()}
    write_json(out_dir / out_name, res)
    return res


def calibrate_limits(pilot: pd.DataFrame) -> dict:
    """Prespecified rule: each frozen limit is max(protocol-text limit, 1.25 x p95 of pilot usage), rounded
    up, and never above the pilot calibration limit. Usage is pooled over agentic runs that ended in
    SUBMITTED or ABSTAINED. Repair and evaluation caps are unchanged. The floor keeps the protocol's
    stated budgets; the headroom keeps limits from binding by construction on well-behaved runs."""
    d = pilot[(pilot["system"] != "F") & pilot["terminal"].isin(["SUBMITTED", "ABSTAINED"])]
    out = {"rule": "max(protocol-text limit, ceil(1.25 x p95 of pilot usage)), capped at the pilot limit; "
                   "agentic SUBMITTED/ABSTAINED runs pooled", "n_runs": int(len(d)), "p95": {}}
    lim = dict(PROTOCOL_LIMITS)
    for k, (col, step) in LIMIT_KEYS.items():
        if len(d) and d[col].notna().any():
            p95 = float(np.nanquantile(d[col].astype(float), 0.95))
            out["p95"][k] = p95
            v = int(math.ceil(1.25 * p95 / step) * step)
            lim[k] = min(max(PROTOCOL_LIMITS[k], v), PILOT_LIMITS[k])
        else:
            lim[k] = PILOT_LIMITS[k]
    lim["repair_cycles"] = PROTOCOL_LIMITS["repair_cycles"]
    lim["pipeline_evaluations"] = PROTOCOL_LIMITS["pipeline_evaluations"]
    out["limits"] = lim
    out["protocol_text_limits"] = dict(PROTOCOL_LIMITS)
    out["pilot_limits"] = dict(PILOT_LIMITS)
    return out


def throughput(pilot: pd.DataFrame, stage_wall_seconds: float | None, concurrency: int) -> dict:
    ag = pilot[pilot["system"] != "F"]
    out = {"agentic_runs": int(len(ag)), "mean_active_s": float(ag["active_s"].mean()) if len(ag) else None,
           "mean_llm_s": float(ag["llm_s"].mean()) if len(ag) else None, "concurrency": concurrency}
    if stage_wall_seconds and len(pilot):
        out["stage_wall_seconds"] = stage_wall_seconds
        out["seconds_per_run_effective"] = stage_wall_seconds / len(pilot)
    return out


def session_estimates(tp: dict, reps: int, session_hours: float = 10.0, gpus: int = 2) -> dict:
    spr = tp.get("seconds_per_run_effective")
    agentic_e1 = 36 * 7 * 6 * reps
    fixed_e1 = 36 * 7 * reps
    e4 = 6 * 7 * 3 * reps
    e5 = 6 * 2 * 7 * reps
    total = agentic_e1 + fixed_e1 + e4 + e5
    out = {"repetitions": reps, "runs": {"E1": agentic_e1 + fixed_e1, "E4": e4, "E5": e5, "total": total}}
    if spr:
        hours = total * spr / 3600
        out["estimated_hours"] = round(hours, 1)
        out["estimated_sessions"] = math.ceil(hours / session_hours)
        out["estimated_gpu_hours"] = round(gpus * hours, 1)
        out["gpus"] = gpus
    return out


def formal_estimates(spr_t1: float | None, spr_t2: float | None, reps: int, n_t1: int = 7, n_t2: int = 3,
                     spr_b: float | None = None, gpus: int = 1) -> dict:
    """Run counts and time for the v2.1 formal design: E1 and E4 over Tier 1 (n_t1) and Tier 2 (n_t2) conditions,
    E5 negative controls. Seconds per run are measured per tier from pilot stages; E4 uses backbone B's rate if given."""
    e1_t1, e1_t2 = 36 * n_t1 * 7 * reps, 36 * n_t2 * 7 * reps
    e4_t1, e4_t2 = 6 * n_t1 * 3 * reps, 6 * n_t2 * 3 * reps
    e5 = 6 * 2 * 7 * reps
    out = {"repetitions": reps, "runs": {"E1": e1_t1 + e1_t2, "E4": e4_t1 + e4_t2, "E5": e5,
                                         "total": e1_t1 + e1_t2 + e4_t1 + e4_t2 + e5}}
    if spr_t1 and spr_t2:
        b1, b2 = (spr_b or spr_t1), (spr_b or spr_t1) * spr_t2 / spr_t1
        sec = (e1_t1 + e5) * spr_t1 + e1_t2 * spr_t2 + e4_t1 * b1 + e4_t2 * b2
        out["estimated_hours"] = round(sec / 3600, 1)
        out["estimated_gpu_hours"] = round(gpus * sec / 3600, 1)
        out["seconds_per_run"] = {"tier1": round(spr_t1, 2), "tier2": round(spr_t2, 2), "backbone_b": spr_b and round(spr_b, 2)}
    return out


def protocol_hash(pkg_dir: Path, study_cfg: dict) -> dict:
    code = sha256_tree(pkg_dir, patterns=("**/*.py", "**/*.md", "**/*.json"))
    return {"code_hash": code, "config_hash": json_hash(study_cfg), "protocol_hash": json_hash({"code": code, "cfg": study_cfg})}


def frozen_config_subset(cfg: dict) -> dict:
    """The parts of the study configuration that the freeze locks."""
    keys = ["limits", "generation", "repetitions", "optional_budget_experiment", "concurrency", "fit_slots"]
    if cfg.get("tier2_conditions") is not None:  # main-plan-v2.1: the frozen Tier-2 levels are locked too
        keys.append("tier2_conditions")
    return {k: cfg.get(k) for k in keys}


def write_freeze(paths: Paths, pkg_dir: Path, cfg: dict, proposal: dict, model_lock: dict) -> dict:
    sub = frozen_config_subset(cfg)
    ph = protocol_hash(pkg_dir, sub)
    man = {"created": now_iso(), **ph, "frozen_config": sub, "proposal": proposal, "model_lock": model_lock,
           "datasets_manifest_hash": json_hash(read_json(paths.manifests / "datasets.json")),
           "splits_manifest_hash": json_hash(read_json(paths.manifests / "splits.json")),
           "canonical_manifest_hash": json_hash(read_json(paths.manifests / "canonical.json")),
           "primary": ("H1: MQP - M0 verified completion, backbone A, all recoverable core tasks"
                       + (" (Tier 1 and the frozen Tier-2 conditions, pooled; main-plan-v2.1)" if cfg.get("tier2_conditions") else "")),
           "secondary_holm_family": ["Q main effect", "P main effect", "Q x P interaction", "MQP - SQP",
                                     "MQP - F (Tier 1 conditions only)"],
           "pre_freeze_decisions_20261112": [
               "MQP - F in the Holm family is estimated on Tier 1 only, because F abstains on Tier 2 by construction; "
               "MQP - F over all tiers is exploratory.",
               "Prespecified secondary outcome (not Holm-adjusted): use of the content-verifying load policy "
               "(authoritative_verified) on X4 when it is available but not enforced, per system, from trusted traces; "
               "and its use on Tier 1 as a false-alarm measure.",
               "Prespecified sensitivity analyses for the primary estimate (three repetition blocks per family): "
               "(a) mixed-effects logistic regression of V on system with random intercepts for task and for "
               "family-repetition block; (b) the block bootstrap with the small-sample variance inflation n/(n-1); "
               "(c) per-family estimates reported alongside leave-one-family-out.",
               "Prespecified descriptive analysis: terminal state and tool-call composition of budget-exhausted runs by "
               "system and tier (exploration, materialisation, fits, gate-check calls)."],
           "prespecified_tier_analyses": ([
               "Every primary and Holm-family contrast estimated separately on Tier 1 and on Tier 2",
               "Tier-2 minus Tier-1 difference of each contrast (paired family-repetition blocks, block bootstrap)",
               "Sensitivity: all contrasts on Tier 2 excluding X4, and on all recoverable tasks excluding X4"]
               if cfg.get("tier2_conditions") else []),
           "replication_tasks": ["D1-T5", "D2-T2", "D3-T4", "D4-T6", "D5-T3", "D6-T1"]}
    write_json(paths.manifests / "freeze.json", man)
    return man


def verify_freeze(paths: Paths, pkg_dir: Path, cfg: dict, model_lock: dict, require_model_lock: bool) -> dict:
    p = paths.manifests / "freeze.json"
    if not p.exists():
        raise RuntimeError("formal experiments require manifests/freeze.json; run the freeze stage first")
    man = read_json(p)
    sub = frozen_config_subset(cfg)
    ph = protocol_hash(pkg_dir, sub)
    problems = []
    if ph["code_hash"] != man["code_hash"]:
        problems.append("package code or prompts changed since the freeze")
    if ph["config_hash"] != man["config_hash"]:
        problems.append(f"frozen configuration changed: now {sub}, frozen {man['frozen_config']}")
    for k in ("datasets", "splits", "canonical"):
        if json_hash(read_json(paths.manifests / f"{k}.json")) != man[f"{k}_manifest_hash"]:
            problems.append(f"{k} manifest changed since the freeze")
    if require_model_lock:
        for b, e in (man.get("model_lock", {}).get("backbones") or {}).items():
            cur = (model_lock.get("backbones") or {}).get(b)
            if not cur or cur.get("revision") != e.get("revision") or cur.get("repo") != e.get("repo"):
                problems.append(f"backbone {b} differs from the frozen model lock")
        if not (man.get("model_lock", {}).get("backbones") or {}).get("A", {}).get("revision"):
            problems.append("frozen model lock has no resolved revision for backbone A")
    if problems:
        raise RuntimeError("protocol freeze verification failed: " + "; ".join(problems))
    return man
