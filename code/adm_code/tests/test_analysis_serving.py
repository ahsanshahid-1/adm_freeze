from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from adm import analysis as A
from adm import power as PW
from adm.serving import BACKBONES, LAUNCH_VARIANTS, Server


def _synthetic(effect=0.2, reps=3, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for f in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        for r in range(reps):
            for t in ["T1", "T2", "T3", "T4", "T5", "T6"]:
                for c in ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]:
                    base = 0.5
                    for s, p in [("M0", base), ("MQP", base + effect), ("MQ", base + effect / 2), ("MP", base + effect / 2),
                                 ("SQP", base + effect), ("F", base), ("S0", base)]:
                        rows.append({"run_id": f"{f}{r}{t}{c}{s}", "family": f, "rep": r, "template": t, "condition": c,
                                     "system": s, "V": int(rng.random() < p), "terminal": "SUBMITTED"})
    return pd.DataFrame(rows)


def test_contrast_recovers_known_effect():
    df = _synthetic(0.2, reps=6)
    D = A.block_differences(df, {"MQP": 1, "M0": -1})
    est = A.estimate(D)
    assert abs(est - 0.2) < 0.06
    bs = A.block_bootstrap(D, draws=500)
    assert bs["ci_low"] < est < bs["ci_high"]
    assert A.sign_flip_test(D, draws=500) < 0.05
    null = A.block_differences(_synthetic(0.0, reps=3, seed=3), {"MQP": 1, "M0": -1})
    assert abs(A.estimate(null)) < 0.08


def test_bootstrap_resamples_whole_blocks():
    D = pd.DataFrame({"family": ["a", "a", "b", "b"], "rep": [0, 1, 0, 1], "D": [1.0, 1.0, -1.0, -1.0]})
    bs = A.block_bootstrap(D, draws=200)
    assert bs["ci_low"] == bs["ci_high"] == 0.0  # family means are constant under within-family resampling


def test_holm():
    adj = A.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)


def test_limit_calibration_rule():
    df = pd.DataFrame({"system": ["S0"] * 21 + ["F"], "terminal": ["SUBMITTED"] * 22,
                       "tokens": [80000.0] * 21 + [10 ** 9], "model_calls": [10] * 22,
                       "tool_calls": [45] * 22, "active_s": [2000.0] * 22})
    lim = PW.calibrate_limits(df)["limits"]
    assert lim["aggregate_tokens"] == 100000          # 1.25 x 80k, above the 30k protocol floor
    assert lim["model_calls"] == 48                   # protocol floor
    assert lim["tool_calls"] == 40                    # capped at the pilot limit (40)
    assert lim["wall_seconds"] == 1200                # capped at the pilot limit
    assert lim["pipeline_evaluations"] == 6 and lim["repair_cycles"] == 2


def test_serving_command_and_ladder(tmp_path):
    s = Server(tmp_path / "env", tmp_path / "models", tmp_path / "cfg", tmp_path / "logs", log=lambda *a: None)
    cmd = s.command("/m", "A", LAUNCH_VARIANTS[1])
    assert cmd[1] == "serve" and "--tensor-parallel-size" in cmd and cmd[cmd.index("--dtype") + 1] == "float16"
    assert "--enforce-eager" in cmd and cmd[cmd.index("--max-model-len") + 1] == "16384"
    assert BACKBONES["A"]["candidates"][0].startswith("cyankiwi/") and BACKBONES["B"]["candidates"] == ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"]


def test_freeze_refuses_modified_config(tmp_path, paths):
    from adm.core import write_json
    pkg = Path(A.__file__).parent
    for k in ("datasets", "splits", "canonical"):
        if not (paths.manifests / f"{k}.json").exists():
            write_json(paths.manifests / f"{k}.json", {"x": 1})
    cfg = {"limits": {"aggregate_tokens": 1}, "generation": {}, "repetitions": [0, 1, 2], "optional_budget_experiment": False,
           "concurrency": 8, "fit_slots": 3}
    PW.write_freeze(paths, pkg, cfg, {}, {})
    PW.verify_freeze(paths, pkg, cfg, {}, require_model_lock=False)
    with pytest.raises(RuntimeError):
        PW.verify_freeze(paths, pkg, {**cfg, "repetitions": [0]}, {}, require_model_lock=False)
    with pytest.raises(RuntimeError):
        PW.verify_freeze(paths, pkg, cfg, {}, require_model_lock=True)
    (paths.manifests / "freeze.json").unlink()


def test_formal_design_with_tier2_and_locking():
    from adm import runner as R
    t2 = ["X2b", "X3a", "X4b"]
    e1 = R.experiment_runs("E1", [0, 1, 2], None, t2)
    assert len(e1) == 36 * 10 * 7 * 3 and len({r["run_id"] for r in e1}) == len(e1)
    assert len(R.experiment_runs("E4", [0, 1, 2], None, t2)) == 6 * 10 * 3 * 3
    assert len(R.experiment_runs("E5", [0, 1, 2], None, t2)) == 252  # negative controls unchanged
    assert len(R.experiment_runs("E1", [0, 1, 2])) == 5292  # Tier 1 only when no Tier-2 list is given
    cfg = {"limits": {}, "generation": {}, "repetitions": [0], "optional_budget_experiment": False, "concurrency": 8,
           "fit_slots": 3, "tier2_conditions": t2}
    assert PW.frozen_config_subset(cfg)["tier2_conditions"] == t2
    est = PW.formal_estimates(15.0, 20.0, 3, 7, 3, 16.0, 1)
    assert est["runs"] == {"E1": 7560, "E4": 540, "E5": 252, "total": 8352} and est["estimated_gpu_hours"] > 0


def _tiered(tier2_gap: float, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for fam in ["D1", "D2", "D3"]:
        for rep in range(3):
            for cond in ["C0", "C1", "X2b", "X4b"]:
                for tmpl in ["T1", "T2"]:
                    for s in ["M0", "MQ", "MP", "MQP", "SQP", "F"]:
                        p = 0.9 if cond.startswith("C") else (0.5 + (tier2_gap if s in ("MP", "MQP", "SQP") else 0))
                        rows.append({"run_id": f"{fam}{rep}{cond}{tmpl}{s}", "family": fam, "rep": rep, "condition": cond,
                                     "template": tmpl, "system": s, "V": float(rng.random() < p)})
    return pd.DataFrame(rows)


def test_tier_sections_and_difference():
    df = _tiered(0.4)
    r = A.tier_difference(df, A.CONTRASTS["P main effect"], draws=500)
    assert r is not None and r["estimate_pp"] > 10 and r["blocks"] == 9
    text = A.tier_sections(df, draws=300)
    assert "Tier-2 minus Tier-1" in text and "excluding X4" in text
    assert A.tier_sections(df[df["condition"].str.startswith("C")], draws=100) == ""
