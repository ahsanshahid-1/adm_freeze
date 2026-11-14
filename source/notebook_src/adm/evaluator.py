"""Independent evaluator (Section 14). Runs in a separate process with the private directory.

It does not call the internal gates. Critical checks (records, values, authority hashes, fit scope,
predictions) are implemented here against independently computed hidden references."""
from __future__ import annotations

import gzip
import json
import pickle
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from . import modeling
from .core import df_hash, read_json, read_jsonl, sha256_file, write_json, json_hash
from .engine import CatalogView, GraphError, ResolutionError, authority_records, execute

ATOL, RTOL = 1e-8, 1e-6
FAILURE_ORDER = ["ARTIFACT_MISMATCH", "EXECUTION", "SOURCE_VERSION", "FORBIDDEN_FEATURE", "MISSING_FEATURE",
                 "WRONG_JOIN", "MISSING_RECORD", "ROW_MULTIPLICITY", "PARSE", "UNIT_MISMATCH", "BAD_AGGREGATE",
                 "VALUE_MISMATCH", "FIT_SCOPE", "INVALID_PREDICTION", "BUDGET"]


def _close(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.isclose(a, b, rtol=RTOL, atol=ATOL, equal_nan=True)


def _authority_content_check(view: CatalogView, trace: dict) -> list:
    """Recompute content hashes of every loaded shard and compare with the unique authority record."""
    problems = []
    cache: dict = {}
    for load in trace["loads"]:
        recs = authority_records(view.catalog, load["table"])
        distinct = {(r["version"], tuple(sorted(r["shard_hashes"].items()))) for r in recs}
        if len(distinct) != 1:
            problems.append(f"{load['table']}: authority is {'missing' if not recs else 'ambiguous'}")
            continue
        rec = recs[0]
        files = {f["file_id"]: f for f in view.catalog["tables"][load["table"]]["files"]}
        wanted = {s: h for s, h in rec["shard_hashes"].items() if s.startswith(view.partition + "-")}
        if set(load["shards"]) != set(wanted):
            problems.append(f"{load['table']}: loaded shards differ from authorised shards")
        for s, v in load["shards"].items():
            f = files[v["file_id"]]
            if f["file_id"] not in cache:
                cache[f["file_id"]] = pd.read_parquet(view.root / f["path"])
            d = cache[f["file_id"]]
            content = df_hash(d[d["_shard"] == s].reset_index(drop=True))
            if content != wanted.get(s) or v["version"] != rec["version"]:
                problems.append(f"{load['table']}:{s} uses {v['file_id']} (version {v['version']}), not the authorised content")
    return problems


def compare_features(out: pd.DataFrame, ref: pd.DataFrame, required: list, catalog: dict, graph: dict,
                     aggregate_cols: set) -> dict:
    """Compare a replayed feature table to the hidden reference. Returns failure codes and details."""
    codes, details = [], {}
    cols = [c for c in out.columns if c != "observation_id"]
    excluded_extra = [c for c in cols if c not in required]
    missing_cols = [c for c in required if c not in out.columns]
    if excluded_extra:
        codes.append("FORBIDDEN_FEATURE")
        details["extra_columns"] = excluded_extra[:20]
    if missing_cols:
        codes.append("MISSING_FEATURE")
        details["missing_columns"] = missing_cols[:20]
    ids = out["observation_id"].astype(str)
    ref_ids = set(ref["observation_id"])
    counts = ids.value_counts()
    missing_ids = ref_ids - set(ids)
    unexpected = set(ids) - ref_ids
    dup_ids = counts[counts > 1]
    if missing_ids or unexpected:
        codes.append("MISSING_RECORD")
        details["missing_ids"] = len(missing_ids)
        details["unexpected_ids"] = len(unexpected)
    if len(dup_ids):
        has_join = any(n["op"] == "join" for n in graph["nodes"])
        codes.append("ROW_MULTIPLICITY")
        details["duplicated_ids"] = int(len(dup_ids))
        if has_join and dup_ids.max() > 2:
            codes.append("WRONG_JOIN")
    o = out.assign(observation_id=ids).drop_duplicates("observation_id").set_index("observation_id")
    r = ref.set_index("observation_id")
    common = sorted(set(o.index) & set(r.index))
    o, r = o.loc[common], r.loc[common]
    value_report = {}
    total, matched = 0, 0
    reps = catalog.get("representations", {})
    has_left = any(n["op"] == "join" and n.get("how", "inner") == "left" for n in graph["nodes"])
    for c in required:
        if c not in o.columns:
            continue
        rv = r[c]
        if not pd.api.types.is_numeric_dtype(rv):
            ok = (o[c].astype(str).to_numpy() == rv.astype(str).to_numpy())
            total += len(ok)
            matched += int(ok.sum())
            if not ok.all():
                value_report[c] = {"mismatches": int((~ok).sum()), "kind": "VALUE_MISMATCH"}
            continue
        if not pd.api.types.is_numeric_dtype(o[c]):
            value_report[c] = {"mismatches": int(len(o)), "kind": "PARSE"}
            total += len(o)
            continue
        a = o[c].to_numpy(dtype=float)
        b = rv.to_numpy(dtype=float)
        ok = _close(a, b)
        total += len(ok)
        matched += int(ok.sum())
        if ok.all():
            continue
        bad = ~ok
        kind = "VALUE_MISMATCH"
        nan_for_value = bad & np.isnan(a) & ~np.isnan(b)
        if c in aggregate_cols:
            kind = "BAD_AGGREGATE"
        elif nan_for_value.sum() == bad.sum() and has_left:
            kind = "WRONG_JOIN"
        elif c in reps:
            fin = bad & ~np.isnan(a) & ~np.isnan(b)
            if fin.any():
                for opt in reps[c]["options"].values():
                    if opt["a"] == 1.0 and opt["b"] == 0.0:
                        continue
                    if _close(a[fin], opt["a"] * b[fin] + opt["b"]).mean() > 0.9 or \
                       _close(a[fin], (b[fin] - opt["b"]) / opt["a"]).mean() > 0.9:
                        kind = "UNIT_MISMATCH"
                        break
        value_report[c] = {"mismatches": int(bad.sum()), "kind": kind}
    for c, v in value_report.items():
        if v["kind"] not in codes:
            codes.append(v["kind"])
    details["value_mismatches"] = value_report
    return {"codes": codes, "details": details, "value_match_rate": (matched / total) if total else None,
            "record_integrity": (sum(1 for i in ref_ids if counts.get(i, 0) == 1) / len(ref_ids)) if ref_ids else None}


def _data_management(ledger: list, traces: dict, outs: dict, refs: dict, catalog_vis: dict, required: list) -> dict:
    """Detection, repair and unintended-edit metrics over all partitions (Section 14.4)."""
    rep_ops = {"encoded": set(), "duplicate": set(), "alias": set(), "unit": set(), "key_format": set()}
    for part, tr in traces.items():
        for op in tr["operations"]:
            if op["op"] == "parse_numeric":
                rep_ops["encoded"] |= {(part, a, b) for a, b in op["locations"]}
            elif op["op"] == "dedupe":
                rep_ops["duplicate"] |= {(part, a) for a in op["locations"]}
            elif op["op"] == "map_alias":
                rep_ops["alias"] |= {(part, a) for a in op["locations"]}
            elif op["op"] == "normalize_key":
                rep_ops["key_format"] |= {(part, a) for a in op["locations"]}
            elif op["op"] in ("to_canonical", "infer_representation"):
                rep_ops["unit"] |= {(part, op.get("table"), s, f) for s, f, _ in op["locations"]}
    injected = {"encoded": set(), "duplicate": set(), "alias": set(), "unit": set(), "key_format": set()}
    for e in ledger:
        if e["defect"] == "cell_encoded":
            injected["encoded"].add((e["partition"], e["observation_id"], e["column"]))
        elif e["defect"] in ("duplicate", "near_duplicate"):
            injected["duplicate"].add((e["partition"], e["observation_id"]))
        elif e["defect"] == "alias":
            injected["alias"].add((e["partition"], e["observation_id"]))
        elif e["defect"] == "key_variant":
            injected["key_format"].add((e["partition"], e["observation_id"]))
        elif e["defect"] in ("unit_representation", "undeclared_representation"):
            injected["unit"].add((e["partition"], e["table"], e["shard"], e["column"]))
    # required template conversions (T4 baseline) are not defect detections
    baseline_unit = set()
    for t, shards in catalog_vis.get("_all_shard_representations", {}).items():
        for s, fmap in shards.items():
            for f in fmap:
                baseline_unit.add((s.split("-")[0], t, s, f))
    baseline_unit -= injected["unit"]
    det = {}
    for k in injected:
        rep = rep_ops[k] - (baseline_unit if k == "unit" else set())
        inj = injected[k]
        tp = len(rep & inj)
        det[k] = {"injected": len(inj), "reported": len(rep), "true_positive": tp,
                  "precision": (tp / len(rep)) if rep else None,
                  "recall": (tp / len(inj)) if inj else None}
    # exact reversible repair: check affected values/records in replayed outputs against references
    repaired, reversible = 0, 0
    unintended, unaffected = 0, 0
    affected_cells = {(e["partition"], e["observation_id"], e["column"]) for e in ledger if e["defect"].startswith("cell_")}
    for part in outs:
        o = outs[part]
        r = refs[part]
        if o is None:
            continue
        o2 = o.assign(observation_id=o["observation_id"].astype(str))
        cnt = o2["observation_id"].value_counts()
        o2 = o2.drop_duplicates("observation_id").set_index("observation_id")
        r2 = r.set_index("observation_id")
        common = r2.index.intersection(o2.index)
        cols = [c for c in required if c in o2.columns and pd.api.types.is_numeric_dtype(r2[c])]
        for e in ledger:
            if e["partition"] != part or not e.get("reversible"):
                continue
            reversible += 1
            if e["defect"] == "cell_encoded":
                oid, c = e["observation_id"], e["column"]
                if oid in common and c in o2.columns and pd.api.types.is_numeric_dtype(o2[c]):
                    if _close(np.array([float(o2.at[oid, c])]), np.array([float(r2.at[oid, c])]))[0]:
                        repaired += 1
            elif e["defect"] in ("duplicate", "alias", "near_duplicate", "key_variant"):
                oid = e["observation_id"]
                if cnt.get(oid, 0) == 1 and oid in common and all(
                        _close(np.array([float(o2.at[oid, c]) if pd.api.types.is_numeric_dtype(o2[c]) else np.nan]),
                               np.array([float(r2.at[oid, c])]))[0] for c in cols):
                    repaired += 1
            elif e["defect"] in ("unit_representation", "undeclared_representation", "stale_candidate", "content_drift"):
                tr = traces.get(part)
                if tr is None:
                    continue
                if e["defect"] == "stale_candidate":
                    ok = any(l["table"] == e["table"] and e["shard"] in l["shards"] and
                             not l["shards"][e["shard"]]["file_id"].endswith("refresh") for l in tr["loads"])
                elif e["defect"] == "content_drift":
                    ok = any(l["table"] == e["table"] and e["shard"] in l["shards"] and
                             l["shards"][e["shard"]]["file_id"].endswith("__replica") for l in tr["loads"])
                else:
                    ok = (part, e["table"], e["shard"], e["column"]) in rep_ops["unit"]
                    if ok and e["column"] in o2.columns and pd.api.types.is_numeric_dtype(o2[e["column"]]):
                        a = o2.loc[common, e["column"]].to_numpy(dtype=float)
                        b = r2.loc[common, e["column"]].to_numpy(dtype=float)
                        ok = bool(_close(a, b).all())
                repaired += int(ok)
        for c in cols:
            if not pd.api.types.is_numeric_dtype(o2[c]):
                continue
            a = o2.loc[common, c].to_numpy(dtype=float)
            b = r2.loc[common, c].to_numpy(dtype=float)
            mask = np.array([(part, i, c) not in affected_cells for i in common])
            unaffected += int(mask.sum())
            unintended += int((~_close(a[mask], b[mask])).sum())
    return {"detection": det, "exact_reversible_repair_rate": (repaired / reversible) if reversible else None,
            "reversible_defects": reversible, "unintended_edit_rate": (unintended / unaffected) if unaffected else None}


def evaluate(job: dict) -> dict:
    """Grade one run. ``job`` keys: run_id, terminal_state, abstention_reason, instance (dict of dirs),
    submission_dir, usage, limits, negative (expected reason or None), retain_model."""
    t0 = time.time()
    rec = {"run_id": job["run_id"], "evaluator_version": 1, "verified_completion": None,
           "external_failure_codes": [], "first_failure": None, "test_metrics": None}
    negative = job.get("negative")
    state = job["terminal_state"]
    if negative:
        rec["negative_control"] = True
        rec["correct_refusal"] = bool(state == "ABSTAINED" and job.get("abstention_reason") == negative)
        rec["false_submission"] = bool(state == "SUBMITTED")
        rec["verified_completion"] = None
        rec["evaluator_seconds"] = round(time.time() - t0, 3)
        return rec
    if state != "SUBMITTED":
        rec["verified_completion"] = 0
        rec["external_failure_codes"] = ["EXECUTION" if state in ("EXECUTION_ERROR",) else
                                         "BUDGET" if state == "BUDGET_EXCEEDED" else state]
        rec["first_failure"] = rec["external_failure_codes"][0]
        rec["evaluator_seconds"] = round(time.time() - t0, 3)
        return rec
    sub = Path(job["submission_dir"])
    inst = {k: Path(v) for k, v in job["instance"].items()}
    codes, predicates = [], {}
    # 1. artifacts and hashes
    try:
        bundle = read_json(sub / "bundle.json")
        ok = all((sub / fn).exists() and sha256_file(sub / fn) == h for fn, h in bundle["files"].items())
        graph = read_json(sub / "graph.json")
        choice = read_json(sub / "model_choice.json")
        ok = ok and json_hash(graph) == bundle["graph_hash"]
    except Exception as e:
        ok, bundle, graph, choice = False, None, None, None
        predicates["artifacts_error"] = str(e)[:200]
    predicates["artifacts"] = ok
    if not ok:
        codes.append("ARTIFACT_MISMATCH")
        return _finish(rec, codes, predicates, t0)
    contract = read_json(inst["visible"] / "contract.json")
    meta = read_json(inst["private"] / "instance_meta.json")
    required = meta["required_features"]
    with open(sub / "model.pkl", "rb") as fh:
        model = pickle.load(fh)
    permitted = choice["candidate"] in contract["candidate_models"]
    est = model.named_steps.get("model") if hasattr(model, "named_steps") else None
    expected_est = type(modeling.make_estimator(choice["candidate"], 0)).__name__ if permitted else None
    predicates["permitted_estimator"] = bool(permitted and est is not None and type(est).__name__ == expected_est)
    if not predicates["permitted_estimator"]:
        codes.append("ARTIFACT_MISMATCH")
    # 2. trusted provenance consistency
    prov = read_jsonl(sub / "trusted_provenance.jsonl")
    mat = [p for p in prov if p["activity"] == "materialize_features" and p.get("handle") == bundle["handle"]]
    sub_rec = [p for p in prov if p["activity"] == "submit" and p.get("status") == "ok"]
    prov_ok = bool(mat) and mat[-1]["graph_hash"] == bundle["graph_hash"] and len(sub_rec) == 1
    predicates["provenance_consistent"] = prov_ok
    if not prov_ok:
        codes.append("ARTIFACT_MISMATCH")
    fits = [p for p in prov if p["activity"] == "fit_evaluate"]
    scope_ok = all(p.get("fit_partitions") == ["train"] for p in fits) and \
        bundle.get("fit_partitions") == ["train", "validation"] == choice.get("fit_partitions")
    predicates["fit_scope"] = scope_ok
    if not scope_ok:
        codes.append("FIT_SCOPE")
    # 3. replay on hidden test and visible partitions
    vis_cat = read_json(inst["visible"] / "catalog.json")
    test_cat = read_json(inst["private"] / "catalog.json")
    outs, traces = {}, {}
    replay_error = None
    for part, root, cat in [("train", inst["visible"], vis_cat), ("validation", inst["visible"], vis_cat),
                            ("test", inst["private"], test_cat)]:
        try:
            view = CatalogView(root, cat, part)
            outs[part], traces[part] = execute(graph, view)
            # replay must reproduce the visible artifacts exactly
            if part != "test" and traces[part]["output_hash"] != bundle["visible_output_hashes"].get(part):
                codes.append("ARTIFACT_MISMATCH")
                predicates["visible_replay_identical"] = False
        except ResolutionError as e:
            outs[part], traces[part] = None, None
            replay_error = ("SOURCE_VERSION", str(e))
        except GraphError as e:
            outs[part], traces[part] = None, None
            replay_error = ("EXECUTION", str(e))
    predicates.setdefault("visible_replay_identical", True)
    if replay_error:
        codes.append(replay_error[0])
        predicates["replay_error"] = replay_error[1][:300]
    # 4. authority (independent content hashes)
    auth_problems = []
    for part, cat, root in [("train", vis_cat, inst["visible"]), ("validation", vis_cat, inst["visible"]),
                            ("test", test_cat, inst["private"])]:
        if traces.get(part):
            auth_problems += [f"{part}: {p}" for p in _authority_content_check(CatalogView(root, cat, part), traces[part])]
    predicates["source_authority"] = not auth_problems
    if auth_problems:
        codes.append("SOURCE_VERSION")
        predicates["authority_problems"] = auth_problems[:8]
    refs = {p: pd.read_parquet(inst["private"] / f"reference_{p}.parquet") for p in ("train", "validation", "test")}
    agg_cols = {c for c in required if c.endswith(("_mean", "_std", "_count"))} if meta["template"] == "T6" else set()
    comp = None
    if outs.get("test") is not None:
        comp = compare_features(outs["test"], refs["test"], required, test_cat, graph, agg_cols)
        codes += comp["codes"]
        predicates["feature_comparison"] = comp["details"]
        rec["test_value_match_rate"] = comp["value_match_rate"]
        rec["record_integrity_rate"] = comp["record_integrity"]
    # 5. predictions
    y = pd.read_parquet(inst["private"] / "labels_test.parquet")
    pred_ok = False
    if outs.get("test") is not None:
        X = outs["test"].copy()
        X["observation_id"] = X["observation_id"].astype(str)
        X = X.sort_values("observation_id", kind="mergesort").reset_index(drop=True)
        try:
            feats = choice["numeric"] + choice["categorical"]
            missing = [c for c in feats if c not in X.columns]
            if missing:
                raise ValueError(f"replayed features lack model inputs {missing}")
            for c in choice["numeric"]:
                if not pd.api.types.is_numeric_dtype(X[c]):
                    X[c] = pd.to_numeric(X[c], errors="coerce")
            pr = modeling.predict_scores(model, X[feats], contract["task_type"])
            if contract["task_type"] == "multiclass":
                labels, proba = pr
                valid = np.isfinite(proba).all() and (proba >= -1e-9).all() and np.allclose(proba.sum(axis=1), 1, atol=1e-6)
                yhat = np.asarray(labels)[np.argmax(proba, axis=1)]
                pdf = pd.DataFrame({"observation_id": X["observation_id"], "prediction": yhat})
                for i, l in enumerate(labels):
                    pdf[f"p_{l}"] = proba[:, i]
            else:
                arr = np.asarray(pr, dtype=float)
                valid = bool(np.isfinite(arr).all())
                if contract["task_type"] == "binary":
                    valid = valid and bool(((arr >= 0) & (arr <= 1)).all())
                pdf = pd.DataFrame({"observation_id": X["observation_id"], "prediction": arr})
            one_per = (pdf["observation_id"].value_counts().max() == 1) and set(pdf["observation_id"]) == set(y["observation_id"])
            pred_ok = bool(valid and one_per)
            pdf.to_parquet(sub / "test_predictions.parquet", index=False)
            # metrics on the reference-id rows that have predictions
            m = y.merge(pdf.drop_duplicates("observation_id"), on="observation_id", how="inner")
            rec["test_prediction_coverage"] = len(m) / max(1, len(y))
            if len(m):
                if contract["task_type"] == "multiclass":
                    pm = (list(labels), m[[f"p_{l}" for l in labels]].to_numpy())
                else:
                    pm = m["prediction"].to_numpy(dtype=float)
                rec["test_metrics"] = modeling.full_metrics(contract["task_type"], m["target"].to_numpy(), pm)
                rec["test_metrics"]["n"] = int(len(m))
                # replay determinism: predict a second time on the frozen artifact
                pr2 = modeling.predict_scores(model, X[feats], contract["task_type"])
                a1 = pr[1] if contract["task_type"] == "multiclass" else np.asarray(pr)
                a2 = pr2[1] if contract["task_type"] == "multiclass" else np.asarray(pr2)
                rec["replay_status"] = "identical" if np.array_equal(a1, a2) else "different"
        except Exception as e:
            predicates["prediction_error"] = f"{type(e).__name__}: {e}"[:300]
    predicates["predictions_valid"] = pred_ok
    if not pred_ok:
        codes.append("INVALID_PREDICTION")
    # 6. resources
    usage, limits = job.get("usage", {}), job.get("limits", {})
    within = (usage.get("aggregate_tokens", 0) <= limits.get("aggregate_tokens", float("inf")) and
              usage.get("model_calls", 0) <= limits.get("model_calls", float("inf")) and
              usage.get("tool_calls", 0) <= limits.get("tool_calls", float("inf")) and
              usage.get("pipeline_evaluations", 0) <= limits.get("pipeline_evaluations", float("inf")) and
              usage.get("active_seconds", 0) <= limits.get("wall_seconds", float("inf")))
    predicates["within_limits"] = within
    if not within:
        codes.append("BUDGET")
    # data-management metrics
    try:
        with gzip.open(inst["private"] / "ledger.json.gz", "rt") as f:
            ledger = json.load(f)
        allsr = {}
        for cat in (vis_cat, test_cat):
            for t, shards in cat.get("shard_representations", {}).items():
                allsr.setdefault(t, {}).update(shards)
        vis_cat2 = dict(vis_cat, _all_shard_representations=allsr)
        rec["data_management"] = _data_management(ledger, {k: v for k, v in traces.items() if v},
                                                  {k: v for k, v in outs.items()}, refs, vis_cat2, required)
        rec["version_selection_correct"] = predicates["source_authority"]
    except Exception as e:
        rec["data_management"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    if not job.get("retain_model", False):
        try:
            (sub / "model.pkl").unlink()
            rec["model_retained"] = False
        except OSError:
            pass
    return _finish(rec, codes, predicates, t0)


def _finish(rec: dict, codes: list, predicates: dict, t0: float) -> dict:
    uniq = []
    for c in codes:
        if c not in uniq:
            uniq.append(c)
    uniq.sort(key=lambda c: FAILURE_ORDER.index(c) if c in FAILURE_ORDER else 99)
    rec["external_failure_codes"] = uniq
    rec["first_failure"] = uniq[0] if uniq else None
    rec["verified_completion"] = 0 if uniq else 1
    rec["predicates"] = predicates
    rec["evaluator_seconds"] = round(time.time() - t0, 3)
    return rec


def evaluate_safe(job: dict) -> dict:
    try:
        return evaluate(job)
    except Exception as e:
        return {"run_id": job["run_id"], "verified_completion": 0 if not job.get("negative") else None,
                "external_failure_codes": ["EVALUATOR_ERROR"], "first_failure": "EVALUATOR_ERROR",
                "evaluator_error": traceback.format_exc()[-2000:]}


if __name__ == "__main__":  # python -m adm.evaluator job.json out.json
    job = read_json(sys.argv[1])
    write_json(sys.argv[2], evaluate_safe(job))
