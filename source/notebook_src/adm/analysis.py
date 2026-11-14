"""Metrics, paired dependence-aware statistics, tables and figures (Sections 14-15, 22)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .core import FAMILIES, SYSTEMS, write_json, dumps

CONTRASTS = {
    "H1: MQP - M0": {"MQP": 1, "M0": -1},
    "Q main effect": {"MQ": 0.5, "M0": -0.5, "MQP": 0.5, "MP": -0.5},
    "P main effect": {"MP": 0.5, "M0": -0.5, "MQP": 0.5, "MQ": -0.5},
    "Q x P interaction": {"MQP": 1, "MQ": -1, "MP": -1, "M0": 1},
    "MQP - SQP": {"MQP": 1, "SQP": -1},
    "MQP - F": {"MQP": 1, "F": -1},
}
SECONDARY = ["Q main effect", "P main effect", "Q x P interaction", "MQP - SQP", "MQP - F"]
# Pre-freeze decision (2026-11-12): F abstains on every Tier-2 instance by construction, so the Holm-family MQP - F is
# estimated on Tier-1 conditions only; the all-tier MQP - F is reported as exploratory.
TIER1_ONLY = {"MQP - F"}
EXPLORATORY = {"M0 - S0": {"M0": 1, "S0": -1}, "SQP - S0": {"SQP": 1, "S0": -1},
               "MQP - F (all tiers, exploratory)": {"MQP": 1, "F": -1}}


def records_df(records: list) -> pd.DataFrame:
    rows = []
    for r in records:
        tm = r.get("test_metrics") or {}
        rows.append({
            "run_id": r["run_id"], "experiment": r["experiment_id"], "suite": r.get("suite"), "family": r["dataset_id"],
            "template": r["template_id"], "condition": r["condition_id"], "rep": r["repetition_id"],
            "system": r["system_id"], "backbone": r["backbone_id"], "budget": r.get("budget_profile", "standard"),
            "terminal": r["terminal_state"], "abstention": r.get("abstention_reason"),
            "V": r.get("verified_completion"), "first_failure": r.get("first_failure"),
            "codes": r.get("external_failure_codes") or [], "correct_refusal": r.get("correct_refusal"),
            "false_submission": r.get("false_submission"),
            "tokens": r.get("aggregate_tokens"), "input_tokens": r.get("input_tokens"), "output_tokens": r.get("output_tokens"),
            "model_calls": r.get("model_calls"), "tool_calls": r.get("tool_calls"), "gate_calls": r.get("gate_calls"),
            "repairs": r.get("repair_cycles"), "evaluations": r.get("pipeline_evaluations"), "fits": r.get("fit_count"),
            "active_s": r.get("active_seconds"), "llm_s": r.get("llm_seconds"), "queue_s": r.get("queue_seconds"),
            "memory_mb": r.get("peak_worker_memory_mb"), "exceptions": r.get("exception_events", 0),
            "attempt": r.get("attempt", 1), "replay": r.get("replay_status"),
            "ap": tm.get("average_precision"), "macro_f1": tm.get("macro_f1"), "roc_auc": tm.get("roc_auc"),
            "balanced_accuracy": tm.get("balanced_accuracy"), "rmse": tm.get("rmse"), "mae": tm.get("mae"),
            "value_match": r.get("test_value_match_rate"), "record_integrity": r.get("record_integrity_rate"),
            "repair_rate": (r.get("data_management") or {}).get("exact_reversible_repair_rate"),
            "unintended_edit": (r.get("data_management") or {}).get("unintended_edit_rate"),
            "version_ok": r.get("version_selection_correct"),
        })
    return pd.DataFrame(rows)


def recoverable(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["condition"].isin(["N1", "N2"])].copy()


# --------------------------------------------------------------------------- paired estimation
def block_differences(df: pd.DataFrame, weights: dict) -> pd.DataFrame | None:
    """D_fr: per (family, repetition), mean over templates and conditions of the weighted system contrast.
    Only complete paired cells (all systems in the contrast present) are used."""
    d = recoverable(df)
    d = d[d["system"].isin(weights)]
    if d.empty:
        return None
    piv = d.pivot_table(index=["family", "rep", "template", "condition"], columns="system", values="V", aggfunc="first")
    if not all(s in piv.columns for s in weights):
        return None
    piv = piv.dropna(subset=list(weights))
    if piv.empty:
        return None
    contrast = sum(w * piv[s].astype(float) for s, w in weights.items())
    D = contrast.groupby(level=["family", "rep"]).mean().rename("D").reset_index()
    D["cells"] = contrast.groupby(level=["family", "rep"]).size().to_numpy()
    return D


def estimate(D: pd.DataFrame) -> float:
    return float(D.groupby("family")["D"].mean().mean())


def block_bootstrap(D: pd.DataFrame, draws: int = 10000, seed: int = 20261030, level: float = 0.95) -> dict:
    """Families fixed; repetition blocks resampled with replacement within each family."""
    rng = np.random.default_rng(seed)
    fams = {f: g["D"].to_numpy() for f, g in D.groupby("family")}
    stats = np.empty(draws)
    for b in range(draws):
        stats[b] = np.mean([v[rng.integers(0, len(v), len(v))].mean() for v in fams.values()])
    a = (1 - level) / 2
    return {"ci_low": float(np.quantile(stats, a)), "ci_high": float(np.quantile(stats, 1 - a)),
            "bootstrap_sd": float(stats.std(ddof=1)), "draws": draws,
            "min_reps_per_family": int(min(len(v) for v in fams.values()))}


def sign_flip_test(D: pd.DataFrame, draws: int = 10000, seed: int = 20261031) -> float:
    """Paired block sign-flip test on family-repetition differences (assumes symmetric exchangeability)."""
    rng = np.random.default_rng(seed)
    obs = abs(estimate(D))
    fam = D["family"].to_numpy()
    vals = D["D"].to_numpy()
    uf = np.unique(fam)
    idx = [np.where(fam == f)[0] for f in uf]
    count = 0
    for _ in range(draws):
        s = rng.choice([-1.0, 1.0], size=len(vals))
        v = vals * s
        stat = abs(np.mean([v[i].mean() for i in idx]))
        count += stat >= obs - 1e-15
    return (count + 1) / (draws + 1)


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for k, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - k) * p))
        adj[name] = running
    return adj


def contrast_table(df: pd.DataFrame, draws: int = 10000) -> pd.DataFrame:
    rows = []
    pv = {}
    for name, w in {**CONTRASTS, **EXPLORATORY}.items():
        sub = df[df["condition"].map(tier_of) == "Tier 1"] if name in TIER1_ONLY else df
        D = block_differences(sub, w)
        if D is None or D.empty:
            rows.append({"contrast": name, "estimate_pp": None, "note": "insufficient paired data"})
            continue
        est = estimate(D)
        bs = block_bootstrap(D, draws)
        p = sign_flip_test(D, draws)
        lofo = {f: estimate(D[D["family"] != f]) for f in sorted(D["family"].unique())} if D["family"].nunique() > 1 else {}
        rows.append({"contrast": name, "estimate_pp": 100 * est, "ci_low_pp": 100 * bs["ci_low"], "ci_high_pp": 100 * bs["ci_high"],
                     "p_sign_flip": p, "families": int(D["family"].nunique()), "blocks": int(len(D)),
                     "paired_cells": int(D["cells"].sum()),
                     "lofo_min_pp": 100 * min(lofo.values()) if lofo else None, "lofo_max_pp": 100 * max(lofo.values()) if lofo else None,
                     "role": "primary" if name.startswith("H1") else "secondary" if name in SECONDARY else "exploratory"})
        if name in SECONDARY:
            pv[name] = p
    t = pd.DataFrame(rows)
    adj = holm(pv) if pv else {}
    t["p_holm"] = t["contrast"].map(adj)
    return t


def tier_of(condition: str) -> str:
    return "Tier 2" if str(condition).startswith("X") else "Tier 1"


TIER_CONTRASTS = ["H1: MQP - M0", "Q main effect", "P main effect", "Q x P interaction", "MQP - SQP", "MQP - F"]


def tier_difference(df: pd.DataFrame, weights: dict, draws: int = 10000) -> dict | None:
    """Tier-2 minus Tier-1 difference of a contrast, paired by (family, repetition) block; block bootstrap."""
    d = recoverable(df)
    D1 = block_differences(d[d["condition"].map(tier_of) == "Tier 1"], weights)
    D2 = block_differences(d[d["condition"].map(tier_of) == "Tier 2"], weights)
    if D1 is None or D2 is None:
        return None
    m = D2.merge(D1, on=["family", "rep"], suffixes=("_t2", "_t1"))
    if m.empty:
        return None
    D = pd.DataFrame({"family": m["family"], "rep": m["rep"], "D": m["D_t2"] - m["D_t1"]})
    bs = block_bootstrap(D, draws)
    return {"estimate_pp": 100 * estimate(D), "ci_low_pp": 100 * bs["ci_low"], "ci_high_pp": 100 * bs["ci_high"],
            "p_sign_flip": sign_flip_test(D, draws), "blocks": int(len(D))}


def tier_sections(df: pd.DataFrame, draws: int = 10000) -> str:
    """Prespecified tier analyses (main-plan-v2.1 Section 15): per-tier contrasts, Tier-2 minus Tier-1 differences,
    and sensitivity excluding X4."""
    d = recoverable(df)
    if d.empty or not (d["condition"].map(tier_of) == "Tier 2").any():
        return ""
    keep = lambda t: t[t["contrast"].isin(TIER_CONTRASTS)].drop(columns=["p_holm"], errors="ignore")
    parts = ["## Tier-separated analyses (prespecified, main-plan-v2.1)\n"]
    for title, sub in [("Tier 1 (declared defects, C0-C6)", d[d["condition"].map(tier_of) == "Tier 1"]),
                       ("Tier 2 (out-of-specification defects)", d[d["condition"].map(tier_of) == "Tier 2"]),
                       ("Sensitivity: Tier 2 excluding X4", d[(d["condition"].map(tier_of) == "Tier 2")
                                                             & ~d["condition"].str.startswith("X4")]),
                       ("Sensitivity: all recoverable tasks excluding X4", d[~d["condition"].str.startswith("X4")])]:
        parts.append(f"### {title}\n" + md_table(keep(contrast_table(sub, draws))))
    rows = []
    for name in TIER_CONTRASTS:
        r = tier_difference(d, CONTRASTS.get(name) or EXPLORATORY.get(name), draws)
        rows.append({"contrast": name, **(r or {"note": "insufficient paired data"})})
    parts.append("### Tier-2 minus Tier-1 difference of each contrast\n" + md_table(pd.DataFrame(rows)))
    parts.append("Per-tier and sensitivity estimates are prespecified secondary analyses; the primary H1 remains the "
                 "pooled estimate over all recoverable tasks. They are not Holm-adjusted.\n")
    return "\n".join(parts)


# --------------------------------------------------------------------------- descriptive tables
def vcr_tables(df: pd.DataFrame) -> dict:
    d = recoverable(df)
    out = {}
    if d.empty:
        return out
    g = d.groupby("system")["V"]
    fam_w = d.groupby(["system", "family"])["V"].mean().groupby("system").mean()
    out["by_system"] = pd.DataFrame({"attempted": g.size(), "verified": g.sum(), "VCR": g.mean(),
                                     "VCR_family_weighted": fam_w}).reindex([s for s in SYSTEMS if s in g.groups])
    out["by_system_family"] = d.pivot_table(index="system", columns="family", values="V", aggfunc="mean")
    out["by_system_condition"] = d.pivot_table(index="system", columns="condition", values="V", aggfunc="mean")
    out["counts_system_condition"] = d.pivot_table(index="system", columns="condition", values="V", aggfunc="count")
    out["terminal_states"] = d.pivot_table(index="system", columns="terminal", values="run_id", aggfunc="count", fill_value=0)
    out["first_failure"] = d[d["V"] == 0].pivot_table(index="system", columns="first_failure", values="run_id",
                                                       aggfunc="count", fill_value=0)
    sub = d[d["terminal"] == "SUBMITTED"]
    out["reliability"] = pd.DataFrame({
        "invalid_submission_rate": d.groupby("system").apply(lambda x: ((x["terminal"] == "SUBMITTED") & (x["V"] == 0)).mean()),
        "submission_error_rate": sub.groupby("system")["V"].apply(lambda v: 1 - v.mean()) if not sub.empty else None,
        "recoverable_abstention_rate": d.groupby("system")["terminal"].apply(lambda t: (t == "ABSTAINED").mean()),
    })
    return out


def efficiency_table(df: pd.DataFrame) -> pd.DataFrame:
    d = recoverable(df)
    g = d.groupby("system")
    t = pd.DataFrame({
        "runs": g.size(), "mean_tokens": g["tokens"].mean(), "p90_tokens": g["tokens"].quantile(0.9),
        "mean_model_calls": g["model_calls"].mean(), "mean_tool_calls": g["tool_calls"].mean(),
        "mean_gate_calls": g["gate_calls"].mean(), "mean_repairs": g["repairs"].mean(), "mean_fits": g["fits"].mean(),
        "mean_active_s": g["active_s"].mean(), "p90_active_s": g["active_s"].quantile(0.9), "mean_llm_s": g["llm_s"].mean(),
        "verified": g["V"].sum()})
    t["tokens_per_verified"] = (g["tokens"].sum() / t["verified"]).where(t["verified"] > 0)
    t["active_s_per_verified"] = (g["active_s"].sum() / t["verified"]).where(t["verified"] > 0)
    return t


def skill_table(df: pd.DataFrame, references: dict) -> pd.DataFrame:
    """Predictive scores for verified runs, skill relative to the correct-workflow dummy, verified utility."""
    rows = []
    for _, r in recoverable(df).iterrows():
        ref = references.get(f"{r['family']}-{r['template']}/r{r['rep']}")
        tt = ref["task_type"] if ref else None
        score, dummy, skill = None, None, None
        if ref:
            dm = ref["dummy_test_metrics"]
            if tt == "binary":
                score, dummy = r["ap"], dm.get("average_precision")
            elif tt == "multiclass":
                score, dummy = r["macro_f1"], dm.get("macro_f1")
            else:
                score, dummy = r["rmse"], dm.get("rmse")
            if score is not None and dummy is not None and not (isinstance(score, float) and math.isnan(score)):
                if tt == "regression":
                    skill = 1 - score / dummy if dummy else None
                else:
                    skill = (score - dummy) / (1 - dummy) if dummy != 1 else None
        v = r["V"] if r["V"] is not None else 0
        rows.append({"system": r["system"], "family": r["family"], "V": v, "score": score, "skill": skill,
                     "verified_utility": (v * max(0.0, skill)) if skill is not None else 0.0})
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    ver = t[t["V"] == 1]
    out = pd.DataFrame({
        "verified_runs": ver.groupby("system").size(),
        "mean_skill_verified": ver.groupby("system")["skill"].mean(),
        "mean_unclipped_skill_all_scored": t.groupby("system")["skill"].mean(),
        "mean_verified_utility_all_attempts": t.groupby("system")["verified_utility"].mean(),
    })
    return out


def raw_metric_table(df: pd.DataFrame) -> pd.DataFrame:
    d = recoverable(df)
    d = d[d["V"] == 1]
    if d.empty:
        return pd.DataFrame()
    return d.groupby(["family", "system"]).agg(n=("run_id", "size"), ap=("ap", "mean"), macro_f1=("macro_f1", "mean"),
                                               rmse=("rmse", "mean"), mae=("mae", "mean"))


def negative_table(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["condition"].isin(["N1", "N2"])]
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("system")
    return pd.DataFrame({"attempts": g.size(), "correct_refusal": g["correct_refusal"].mean(),
                         "false_submission": g["false_submission"].mean()})


def usage_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    d = df[(df["system"] != "F") & df["terminal"].isin(["SUBMITTED", "ABSTAINED"])]
    cols = ["tokens", "model_calls", "tool_calls", "active_s", "repairs", "evaluations"]
    if d.empty:
        return pd.DataFrame(index=cols)
    return d[cols].astype(float).quantile([0.5, 0.9, 0.95, 1.0]).T.rename(columns=lambda q: f"p{int(q * 100)}")


# --------------------------------------------------------------------------- figures
def figures(df: pd.DataFrame, outdir: Path, prefix: str) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir.mkdir(parents=True, exist_ok=True)
    d = recoverable(df)
    files = []
    if d.empty:
        return files
    piv = d.pivot_table(index="condition", columns="system", values="V", aggfunc="mean")
    piv = piv[[s for s in SYSTEMS if s in piv.columns]]
    ax = piv.plot(kind="bar", figsize=(10, 4.5), width=0.85)
    ax.set_ylabel("Verified-completion rate")
    ax.set_ylim(0, 1)
    ax.set_title(f"{prefix}: completion by defect condition (C* families are not one severity scale)")
    plt.tight_layout()
    p = outdir / f"{prefix}_completion_by_condition.png"
    plt.savefig(p, dpi=120)
    plt.close()
    files.append(p)
    e = d.groupby("system").agg(V=("V", "mean"), tokens=("tokens", "mean"), active=("active_s", "mean"))
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for ax, col, lab in [(axs[0], "tokens", "Mean aggregate tokens per run"), (axs[1], "active", "Mean active seconds per run")]:
        ax.scatter(e[col], e["V"])
        for s, row in e.iterrows():
            ax.annotate(s, (row[col], row["V"]))
        ax.set_xlabel(lab)
        ax.set_ylabel("VCR")
    fig.suptitle(f"{prefix}: cost versus completion")
    plt.tight_layout()
    p = outdir / f"{prefix}_cost_vs_completion.png"
    plt.savefig(p, dpi=120)
    plt.close()
    files.append(p)
    ff = d[d["V"] == 0].pivot_table(index="system", columns="first_failure", values="run_id", aggfunc="count", fill_value=0)
    if not ff.empty:
        ax = ff.plot(kind="bar", stacked=True, figsize=(10, 4.5))
        ax.set_ylabel("Runs (first failure category)")
        ax.set_title(f"{prefix}: failure categories")
        plt.tight_layout()
        p = outdir / f"{prefix}_failure_categories.png"
        plt.savefig(p, dpi=120)
        plt.close()
        files.append(p)
    return files


def md_table(t: pd.DataFrame | None, floatfmt: str = "{:.3f}") -> str:
    if t is None or (hasattr(t, "empty") and t.empty):
        return "_no data_\n"
    t = t.copy()
    t = t.reset_index() if not isinstance(t.index, pd.RangeIndex) else t
    cols = [str(c) for c in t.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in t.iterrows():
        vals = []
        for v in r.tolist():
            if isinstance(v, (float, np.floating)):
                vals.append("" if math.isnan(v) else floatfmt.format(v))
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def report(df: pd.DataFrame, title: str, outdir: Path, figdir: Path, references: dict, banner: str = "",
           draws: int = 10000, extra_sections: list | None = None) -> str:
    """Write the mandatory result tables (Section 22.1) for a set of runs."""
    outdir.mkdir(parents=True, exist_ok=True)
    parts = [f"# {title}\n", banner + "\n" if banner else ""]
    v = vcr_tables(df)
    parts.append("## 1. Verified-completion rate (recoverable runs)\n")
    parts.append(md_table(v.get("by_system")))
    parts.append("### By dataset family\n" + md_table(v.get("by_system_family")))
    parts.append("### By condition\n" + md_table(v.get("by_system_condition")))
    parts.append("### Attempt counts by condition\n" + md_table(v.get("counts_system_condition"), "{:.0f}"))
    parts.append("## 2. Paired effects (percentage points; family-weighted; block bootstrap within family)\n")
    ct = contrast_table(df, draws)
    parts.append(md_table(ct))
    parts.append("Failure to reject a difference is not evidence of equivalence. With three repetition blocks per family the "
                 "bootstrap interval can be unstable.\n")
    parts.append("## 3. Predictive quality\n" + md_table(skill_table(df, references)) + "\n### Raw metrics of verified runs\n"
                 + md_table(raw_metric_table(df)))
    parts.append("## 4. Cost and efficiency\n" + md_table(efficiency_table(df), "{:.1f}"))
    parts.append("## 5. Failure categories and reliability\n" + md_table(v.get("first_failure"), "{:.0f}")
                 + md_table(v.get("reliability")) + "### Terminal states\n" + md_table(v.get("terminal_states"), "{:.0f}"))
    parts.append("## 6. Negative controls (unrecoverable tasks)\n" + md_table(negative_table(df)))
    for s in extra_sections or []:
        parts.append(s)
    files = figures(df, figdir, title.split()[0].lower())
    import os
    parts.append("## Figures\n" + "\n".join(f"![{p.stem}]({os.path.relpath(p, outdir)})" for p in files) + "\n")
    text = "\n".join(parts)
    for k, t in v.items():
        t.to_csv(outdir / f"{title.split()[0].lower()}_{k}.csv")
    ct.to_csv(outdir / f"{title.split()[0].lower()}_contrasts.csv", index=False)
    return text
