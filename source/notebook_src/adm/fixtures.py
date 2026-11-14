"""Known-answer evaluator fixtures (E0 pre-step) and replay/invariance checks (E6).
Results are kept separate from model-capability scores."""
from __future__ import annotations

import copy
import pickle
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .core import Paths, SYSTEM_SPEC, instance_dirs, read_json, sha256_file, write_json, PILOT_LIMITS
from .engine import parse_cell
from .evaluator import evaluate
from .fixed import contract_graph, oracle_graph
from .tasks import ensure_instance
from .tools import Budget, Terminal, ToolSession


class InvalidProbaModel:
    """Wraps a fitted pipeline but returns invalid probabilities (fixture only)."""

    def __init__(self, inner):
        self.inner = inner
        self.named_steps = inner.named_steps
        self.classes_ = inner.classes_

    def predict_proba(self, X):
        return self.inner.predict_proba(X) * 1.5 + 0.1

    def predict(self, X):
        return self.inner.predict(X)


def mutate(graph: dict, **flags) -> dict:
    alias, nodes = {}, []
    for n in copy.deepcopy(graph["nodes"]):
        for r in ("input", "left", "right"):
            if r in n:
                n[r] = alias.get(n[r], n[r])
        op = n["op"]
        if (op == "map_alias" and flags.get("skip_alias")) or (op == "dedupe" and flags.get("skip_dedupe")) or \
           (op == "to_canonical" and flags.get("skip_canonical")):
            alias[n["id"]] = n["input"]
            continue
        if op == "load" and flags.get("policy"):
            n["policy"] = flags["policy"]
        if op == "join":
            if flags.get("join_how"):
                n["how"] = flags["join_how"]
            if flags.get("drop_cardinality"):
                n.pop("cardinality", None)
        if op == "aggregate" and flags.get("sample_std"):
            n["stats"] = ["mean", "sample_std", "count"]
        if op == "project" and n["id"] == "features":
            if flags.get("extra_column"):
                n["columns"] = n["columns"] + [flags["extra_column"]]
            if flags.get("drop_missing"):
                nodes.append({"id": "dropna", "op": "drop_missing_rows", "input": n["input"]})
                n["input"] = "dropna"
        nodes.append(n)
    return {"nodes": nodes, "output": alias.get(graph["output"], graph["output"])}


FIXTURES = [
    # name, (family, template, condition), graph flags, candidate index, tamper, expected (None = verified)
    ("correct_T3_C4", ("D5", "T3", "C4"), {}, 2, None, None),
    ("valid_alt_inner_join_T3_C4", ("D5", "T3", "C4"), {"join_how": "inner"}, 0, None, None),
    ("valid_alt_explicit_version_T3_C4", ("D5", "T3", "C4"), {"policy": "version:v2"}, 4, None, None),
    ("wrong_join_unmapped_alias_T3_C4", ("D5", "T3", "C4"), {"skip_alias": True, "join_how": "inner"}, 2, None, "MISSING_RECORD"),
    ("duplicated_predictions_T3_C4", ("D5", "T3", "C4"), {"skip_dedupe": True, "drop_cardinality": True}, 2, None, "ROW_MULTIPLICITY"),
    ("correct_T6_C6", ("D6", "T6", "C6"), {}, 2, None, None),
    ("wrong_version_T6_C6", ("D6", "T6", "C6"), {"policy": "latest_modified"}, 2, None, "SOURCE_VERSION"),
    ("unit_mismatch_T6_C6", ("D6", "T6", "C6"), {"skip_canonical": True}, 2, None, "UNIT_MISMATCH"),
    ("bad_aggregate_T6_C6", ("D6", "T6", "C6"), {"sample_std": True}, 2, None, "BAD_AGGREGATE"),
    ("forbidden_predictor_T6_C6", ("D6", "T6", "C6"), {"extra_column": "batch_id"}, 2, None, "FORBIDDEN_FEATURE"),
    ("wrong_version_T5_C0", ("D6", "T5", "C0"), {"policy": "latest_snapshot"}, 2, None, "SOURCE_VERSION"),
    ("missing_records_drop_rows_T1_C2", ("D5", "T1", "C2"), {"drop_missing": True}, 2, None, "MISSING_RECORD"),
    ("forbidden_identifier_T1_C0", ("D5", "T1", "C0"), {"extra_column": "machine_id"}, 2, None, "FORBIDDEN_FEATURE"),
    ("changed_artifact_hash_T1_C0", ("D5", "T1", "C0"), {}, 2, "graph", "ARTIFACT_MISMATCH"),
    ("invalid_probabilities_T1_C0", ("D5", "T1", "C0"), {}, 2, "proba", "INVALID_PREDICTION"),
]
# Tier 2 (main-plan-v2.1): the oracle repairs each defect; the declared-specification graph (F) does not
TIER2_FIXTURES = [
    ("oracle_T2_X1b", ("D5", "T2", "X1b"), {"oracle": True}, 2, None, None),
    ("spec_graph_near_duplicates_T1_X1b", ("D5", "T1", "X1b"), {}, 2, None, "ROW_MULTIPLICITY"),
    ("oracle_T6_X2b", ("D6", "T6", "X2b"), {"oracle": True}, 2, None, None),
    ("spec_graph_key_variants_T1_X2b", ("D5", "T1", "X2b"), {}, 2, None, "MISSING_RECORD"),
    ("oracle_T4_X3b", ("D6", "T4", "X3b"), {"oracle": True}, 2, None, None),
    ("spec_graph_undeclared_rep_T1_X3b", ("D5", "T1", "X3b"), {}, 2, None, "UNIT_MISMATCH"),
    ("oracle_T3_X4b", ("D5", "T3", "X4b"), {"oracle": True}, 2, None, None),
    ("spec_graph_content_drift_T1_X4b", ("D6", "T1", "X4b"), {}, 2, None, "SOURCE_VERSION"),
    ("latest_modified_content_drift_T2_X4c", ("D5", "T2", "X4c"), {"oracle": True, "policy": "latest_modified"}, 2, None,
     "SOURCE_VERSION"),
]


def _submit(paths: Paths, run_id: str, inst: tuple, graph_flags: dict, cand_idx: int, suite: str, rep: int) -> tuple:
    fam, tmpl, cond = inst
    ensure_instance(paths, suite, fam, tmpl, cond, rep)
    dirs = instance_dirs(paths, suite, fam, tmpl, cond, rep)
    sub = paths.work / "fixtures" / run_id
    if sub.exists():
        shutil.rmtree(sub)
    lim = dict(PILOT_LIMITS)
    s = ToolSession(run_id, dirs["visible"], dirs["trusted"], sub, SYSTEM_SPEC["S0"], Budget(lim),
                    {"estimator": 12345, "agent": 1})
    flags = dict(graph_flags)
    builder = oracle_graph if flags.pop("oracle", False) else contract_graph
    g = mutate(builder(s.contract, s.catalog), **flags)
    obs = s.call("materialize_features", {"graph": g})
    if not obs.get("materialized"):
        raise RuntimeError(f"fixture {run_id}: materialization failed: {obs.get('error')}")
    cand = s.contract["candidate_models"][cand_idx]
    r = s.call("fit_evaluate", {"handle": obs["handle"], "candidate": cand})
    try:
        s.call("submit", {"handle": obs["handle"], "candidate": cand})
    except Terminal:
        pass
    s.close()
    return dirs, sub, s.budget.usage(), lim


def _tamper(sub: Path, kind: str):
    if kind == "graph":
        g = read_json(sub / "graph.json")
        g["nodes"][0]["policy"] = "latest_modified"
        write_json(sub / "graph.json", g)
    elif kind == "proba":
        with open(sub / "model.pkl", "rb") as f:
            m = pickle.load(f)
        with open(sub / "model.pkl", "wb") as f:
            pickle.dump(InvalidProbaModel(m), f)
        b = read_json(sub / "bundle.json")
        b["files"]["model.pkl"] = sha256_file(sub / "model.pkl")
        write_json(sub / "bundle.json", b)


def run_evaluator_fixtures(paths: Paths, suite: str = "development", rep: int = 2, log=print, fixtures=None,
                           out_name: str = "evaluator_fixtures.json") -> dict:
    results = []
    for name, inst, flags, ci, tamper, expected in (FIXTURES if fixtures is None else fixtures):
        dirs, sub, usage, lim = _submit(paths, f"FIX-{name}", inst, flags, ci, suite, rep)
        if tamper:
            _tamper(sub, tamper)
        ev = evaluate({"run_id": f"FIX-{name}", "terminal_state": "SUBMITTED", "abstention_reason": None,
                       "instance": {k: str(v) for k, v in dirs.items()}, "submission_dir": str(sub), "usage": usage,
                       "limits": lim, "negative": None, "retain_model": True})
        codes = ev["external_failure_codes"]
        ok = (ev["verified_completion"] == 1) if expected is None else (expected in codes)
        results.append({"fixture": name, "expected": expected or "VERIFIED", "codes": codes,
                        "verified": ev["verified_completion"], "passed": bool(ok)})
        log(f"  fixture {name:40s} expected {expected or 'VERIFIED':18s} got {codes or 'VERIFIED'} -> {'PASS' if ok else 'FAIL'}")
    # unit-level invariance: equivalent numeric representations parse identically
    eq = all(parse_cell(a)[0] == parse_cell(b)[0] for a, b in [("value:1.50", "1.5"), ("2.0", 2), (" value:3e2", "300")])
    results.append({"fixture": "equivalent_numeric_representations", "expected": "equal", "codes": [], "verified": None,
                    "passed": bool(eq)})
    out = {"fixtures": results, "all_passed": all(r["passed"] for r in results)}
    write_json(paths.outputs / out_name, out)
    return out


def oracle_solvability(paths: Paths, keys: list, log=print) -> dict:
    """Run the oracle solver on every partition of every instance and compare with the hidden reference
    (ABC II.7-II.8: every task is verified to be solvable before agents run)."""
    from .engine import CatalogView, execute
    failures = []
    for k in keys:
        suite, fam, tmpl, cond, rep = k
        ensure_instance(paths, suite, fam, tmpl, cond, rep)
        d = instance_dirs(paths, suite, fam, tmpl, cond, rep)
        g = oracle_graph(read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json"))
        for part, root in [("train", d["visible"]), ("validation", d["visible"]), ("test", d["private"])]:
            out, _ = execute(g, CatalogView.open(root, part))
            ref = pd.read_parquet(d["private"] / f"reference_{part}.parquet")
            o = out.assign(observation_id=out["observation_id"].astype(str)).sort_values("observation_id").reset_index(drop=True)
            r = ref.sort_values("observation_id").reset_index(drop=True)
            ok = len(o) == len(r) and (o["observation_id"].values == r["observation_id"].values).all()
            if ok:
                for c in r.columns[1:]:
                    if pd.api.types.is_numeric_dtype(r[c]):
                        ok &= bool(np.isclose(o[c].astype(float), r[c].astype(float), rtol=1e-6, atol=1e-8, equal_nan=True).all())
                    else:
                        ok &= bool((o[c].astype(str).values == r[c].astype(str).values).all())
            if not ok:
                failures.append(f"{fam}-{tmpl}/{cond}/r{rep}/{part}")
    log(f"oracle solvability: {len(keys)} instances, {len(failures)} failures {failures[:5]}")
    return {"instances": len(keys), "failures": failures, "all_solvable": not failures}


# --------------------------------------------------------------------------- E6
def _copy_instance(dirs: dict, dest: Path) -> dict:
    if dest.exists():
        shutil.rmtree(dest)
    out = {}
    for k, v in dirs.items():
        shutil.copytree(v, dest / k)
        out[k] = dest / k
    return out


def replay_checks(paths: Paths, record: dict, sub_dir: Path, log=print) -> dict:
    """E6 for one frozen submission with a retained model: replay, row/column-order invariance,
    wrong-version substitution, one missing test record, changed artifact hash."""
    r = record
    ensure_instance(paths, r["suite"], r["dataset_id"], r["template_id"], r["condition_id"], r["repetition_id"])
    dirs = instance_dirs(paths, r["suite"], r["dataset_id"], r["template_id"], r["condition_id"], r["repetition_id"])
    base = paths.work / "e6" / r["run_id"]
    out = {"run_id": r["run_id"], "checks": {}}

    def ev(inst, sub):
        return evaluate({"run_id": r["run_id"], "terminal_state": "SUBMITTED", "abstention_reason": None,
                         "instance": {k: str(v) for k, v in inst.items()}, "submission_dir": str(sub),
                         "usage": {}, "limits": {}, "negative": None, "retain_model": True})

    def fresh_sub(tag):
        d = base / f"sub_{tag}"
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(sub_dir, d)
        return d

    e0 = ev(dirs, fresh_sub("orig"))
    p0 = pd.read_parquet(base / "sub_orig" / "test_predictions.parquet") if (base / "sub_orig" / "test_predictions.parquet").exists() else None
    out["checks"]["replay_matches_record"] = {"passed": e0["verified_completion"] == r["verified_completion"],
                                              "detail": e0["external_failure_codes"]}
    # reordered rows and columns in every hidden test source
    inst = _copy_instance(dirs, base / "inst_reorder")
    rng = np.random.default_rng(99)
    for f in (inst["private"] / "sources").glob("*.parquet"):
        d = pd.read_parquet(f)
        d = d.iloc[rng.permutation(len(d))][list(reversed(d.columns))]
        d.to_parquet(f, index=False)
    e1 = ev(inst, fresh_sub("reorder"))
    same = False
    if p0 is not None and (base / "sub_reorder" / "test_predictions.parquet").exists():
        p1 = pd.read_parquet(base / "sub_reorder" / "test_predictions.parquet")
        a = p0.sort_values("observation_id").reset_index(drop=True)
        b = p1.sort_values("observation_id").reset_index(drop=True)
        num = [c for c in a.columns if c not in ("observation_id",) and pd.api.types.is_numeric_dtype(a[c])]
        same = a["observation_id"].equals(b["observation_id"]) and all(
            np.allclose(a[c], b[c], rtol=1e-6, atol=1e-8, equal_nan=True) for c in num)
    out["checks"]["row_column_reorder_invariant"] = {"passed": bool(same and e1["external_failure_codes"] == e0["external_failure_codes"]),
                                                     "detail": e1["external_failure_codes"]}
    if e0["verified_completion"] == 1:
        # wrong-version substitution: altered content behind an authorised hash
        inst = _copy_instance(dirs, base / "inst_wrongver")
        tcat = read_json(inst["private"] / "catalog.json")
        tab = next(t for t, v in tcat["tables"].items() if v["grain"] == "observation")
        fpath = inst["private"] / next(f["path"] for f in tcat["tables"][tab]["files"] if f["version"] == "v2")
        d = pd.read_parquet(fpath)
        numc = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c]) and c != "_shard"]
        if numc:
            d.loc[d.index[0], numc[0]] = float(d[numc[0]].iloc[0]) + 1.2345
            d.to_parquet(fpath, index=False)
        e2 = ev(inst, fresh_sub("wrongver"))
        out["checks"]["wrong_version_detected"] = {"passed": "SOURCE_VERSION" in e2["external_failure_codes"],
                                                   "detail": e2["external_failure_codes"]}
        # one missing test record, removed from the primary observation table
        inst = _copy_instance(dirs, base / "inst_missing")
        primary = read_json(dirs["private"] / "instance_meta.json")["primary_table"]
        fpath = inst["private"] / next(f["path"] for f in tcat["tables"][primary]["files"] if f["version"] == "v2")
        d = pd.read_parquet(fpath)
        d.iloc[1:].to_parquet(fpath, index=False)
        e3 = ev(inst, fresh_sub("missing"))
        out["checks"]["missing_record_detected"] = {
            "passed": e3["verified_completion"] == 0 and bool({"MISSING_RECORD", "INVALID_PREDICTION"} & set(e3["external_failure_codes"])),
            "detail": e3["external_failure_codes"]}
        # changed artifact hash
        s4 = fresh_sub("tamper")
        g = read_json(s4 / "graph.json")
        g["nodes"].append({"id": "zz", "op": "project", "input": g["output"], "columns": ["observation_id"]})
        write_json(s4 / "graph.json", g)
        e4 = ev(dirs, s4)
        out["checks"]["changed_artifact_detected"] = {"passed": "ARTIFACT_MISMATCH" in e4["external_failure_codes"],
                                                      "detail": e4["external_failure_codes"]}
    shutil.rmtree(base, ignore_errors=True)
    out["all_passed"] = all(c["passed"] for c in out["checks"].values())
    return out
