"""Main results figure: (a) verified-completion rate by system on declared defects (Tier 1), undeclared defects other
than content drift (X2, X3), and content drift (X4); (b) on X4, the share of runs that used the content-verifying load
policy and the share that were verified. Read-only on the state directory.

Usage: MPLBACKEND=Agg python make_figure.py STATE_DIR EXTRA_JSON OUT_DIR EXPERIMENT [EXPERIMENT ...]
  EXTRA_JSON is the prespecified_extra.json written by prespecified_extra.py for the same experiments.
Writes OUT_DIR/fig_main.pdf and OUT_DIR/fig_main_data.json (every plotted number with its n).
"""
from __future__ import annotations

import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STATE, EXTRA, OUT, EXPS = (os.path.expanduser(sys.argv[1]), os.path.expanduser(sys.argv[2]),
                           os.path.expanduser(sys.argv[3]), sys.argv[4:])
SYSTEMS = ["F", "S0", "M0", "MQ", "MP", "SQP", "MQP"]
AGENTS = SYSTEMS[1:]
ENFORCED = {"MP", "SQP", "MQP"}

recs = []
for e in EXPS:
    for p in sorted(glob.glob(f"{STATE}/outputs/runs/{e}/*.json")):
        with open(p) as fh:
            r = json.load(fh)
        c = str(r.get("condition_id", ""))
        if c.startswith("N") or r.get("backbone_id") not in ("A", "none"):
            continue
        recs.append((r["system_id"], c, int(r.get("verified_completion") or 0)))


def group(c: str) -> str:
    return "X4" if c.startswith("X4") else ("X2+X3" if c.startswith("X") else "Tier 1")


GROUPS = ["Tier 1", "X2+X3", "X4"]
vcr = {s: {} for s in SYSTEMS}
for s in SYSTEMS:
    for g in GROUPS:
        v = [x for (s_, c, x) in recs if s_ == s and group(c) == g]
        vcr[s][g] = {"n": len(v), "vcr": (sum(v) / len(v)) if v else None}

with open(EXTRA) as fh:
    use = json.load(fh)["operation_use"]
x4 = {}
for s in AGENTS:
    row = use.get(s, {}).get("X4")
    if row and row["runs"]:
        x4[s] = {"runs": row["runs"], "used": row["authoritative_verified"], "verified": row["verified"],
                 "used_share": row["authoritative_verified"] / row["runs"], "verified_share": row["verified"] / row["runs"]}

plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 7.5,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.45, 3.3), gridspec_kw={"height_ratios": [1, 1], "hspace": 0.55})
w = 0.26
colors = {"Tier 1": "#bdbdbd", "X2+X3": "#6baed6", "X4": "#08519c"}
for i, g in enumerate(GROUPS):
    xs = [k + (i - 1) * w for k in range(len(SYSTEMS))]
    ys = [vcr[s][g]["vcr"] or 0 for s in SYSTEMS]
    ax1.bar(xs, ys, w, color=colors[g], label=g, edgecolor="none")
ax1.set_xticks(range(len(SYSTEMS)), SYSTEMS)
ax1.set_ylim(0, 1.28)
ax1.set_yticks([0, 0.5, 1.0])
ax1.set_ylabel("Verified completion")
ax1.set_title("(a) Verified completion by system and defect group", fontsize=7.5)
ax1.legend(ncol=3, frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.0), handlelength=1.2)
ax1.spines[["top", "right"]].set_visible(False)

xs = range(len(AGENTS))
ax2.bar([k - 0.18 for k in xs], [x4.get(s, {}).get("used_share", 0) for s in AGENTS], 0.36,
        color=["#08519c" if s in ENFORCED else "#fd8d3c" for s in AGENTS], label="used verifying load")
ax2.bar([k + 0.18 for k in xs], [x4.get(s, {}).get("verified_share", 0) for s in AGENTS], 0.36,
        color="none", edgecolor="#333333", linewidth=0.6, hatch="////", label="verified")
for k, s in enumerate(AGENTS):
    if s in x4:
        ax2.text(k - 0.18, x4[s]["used_share"] + 0.03, str(x4[s]["used"]), ha="center", fontsize=6)
ax2.set_xticks(list(xs), [s + ("\n(enforced)" if s in ENFORCED else "\n(available)") for s in AGENTS], fontsize=6.5)
ax2.set_ylim(0, 1.28)
ax2.set_yticks([0, 0.5, 1.0])
ax2.set_ylabel("Share of X4 runs")
ax2.set_title("(b) Content drift: verifying load used vs. run verified", fontsize=7.5)
ax2.legend(ncol=2, frameon=False, fontsize=6.5, loc="upper left", handlelength=1.2)
ax2.spines[["top", "right"]].set_visible(False)

os.makedirs(OUT, exist_ok=True)
fig.savefig(f"{OUT}/fig_main.pdf", bbox_inches="tight", pad_inches=0.02)
with open(f"{OUT}/fig_main_data.json", "w") as fh:
    json.dump({"experiments": EXPS, "records": len(recs), "vcr": vcr, "x4_operation_use": x4}, fh, indent=1)
print(json.dumps({"records": len(recs), "vcr": vcr, "x4": x4}, indent=1))
