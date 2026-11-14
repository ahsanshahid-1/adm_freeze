"""Internal treatment gates (Section 9.6). They use only agent-permitted information:
the contract, the visible catalog, the visible partition manifest and the materialised artifact."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import authority_records


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "passed": bool(ok), "detail": detail}


def quality_gate(handle: dict, contract: dict, catalog: dict, manifest: dict) -> dict:
    checks = []
    req = list(contract["required_features"])
    excluded = set(contract["excluded_predictors"]) - {"observation_id"}
    ranges = contract.get("value_ranges", {})
    num = set(contract.get("numeric_features", []))
    graph = handle["graph"]
    for part, df in handle["frames"].items():
        cols = [c for c in df.columns if c != "observation_id"]
        missing = [c for c in req if c not in df.columns]
        extra = [c for c in cols if c not in req]
        checks.append(_check(f"{part}:required_columns", not missing and not extra,
                             f"missing={missing[:8]} extra={extra[:8]}" if (missing or extra) else ""))
        forb = [c for c in cols if c in excluded]
        checks.append(_check(f"{part}:excluded_predictors", not forb, f"present={forb}" if forb else ""))
        bad_types = [c for c in cols if c in num and not pd.api.types.is_numeric_dtype(df[c])]
        checks.append(_check(f"{part}:numeric_types", not bad_types, f"non-numeric={bad_types}" if bad_types else ""))
        ids = df["observation_id"].astype(str)
        dup = int(ids.duplicated().sum())
        checks.append(_check(f"{part}:key_uniqueness", dup == 0, f"{dup} duplicated observation_id rows" if dup else ""))
        expected = set(manifest["partitions"][part])
        got = set(ids)
        miss, unexpected = len(expected - got), len(got - expected)
        checks.append(_check(f"{part}:record_coverage", miss == 0 and unexpected == 0,
                             f"{miss} expected observation_ids missing, {unexpected} unexpected ids "
                             f"(examples: {sorted(got - expected)[:3]})" if (miss or unexpected) else ""))
        viol = {}
        for c, (lo, hi) in ranges.items():
            if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
                v = df[c].to_numpy(dtype=float)
                v = v[~np.isnan(v)]
                n = int(((v < lo - 1e-9) | (v > hi + 1e-9)).sum())
                if n:
                    viol[c] = n
        checks.append(_check(f"{part}:value_ranges", not viol, f"out-of-range value counts {dict(list(viol.items())[:6])}" if viol else ""))
        for a in contract.get("aggregates", []):
            for s in a["series"]:
                cc = f"{s}_count"
                sd = f"{s}_std"
                if cc in df.columns and pd.api.types.is_numeric_dtype(df[cc]):
                    bad = int((df[cc].dropna() != a["readings_per_series"]).sum())
                    checks.append(_check(f"{part}:aggregate_count:{s}", bad == 0,
                                         f"{bad} rows with count != {a['readings_per_series']}" if bad else ""))
                if sd in df.columns and pd.api.types.is_numeric_dtype(df[sd]):
                    neg = int((df[sd].dropna() < 0).sum())
                    checks.append(_check(f"{part}:aggregate_std:{s}", neg == 0, f"{neg} negative std" if neg else ""))
    # canonical units: every loaded table with declared non-canonical shards must pass through to_canonical
    trace = handle["traces"]["train"]
    loaded = {l["table"] for l in trace["loads"]}
    converted = {o.get("table") for o in trace["operations"] if o["op"] == "to_canonical"}
    need = sorted(t for t in loaded if catalog.get("shard_representations", {}).get(t))
    lacking = [t for t in need if t not in converted]
    checks.append(_check("canonical_units", not lacking,
                         f"tables with declared shard-level representations not converted: {lacking}" if lacking else ""))
    drops = [n["id"] for n in graph["nodes"] if n["op"] == "drop_missing_rows"]
    checks.append(_check("missing_value_policy", not drops, f"rows dropped by {drops}; the contract requires keeping rows" if drops else ""))
    return {"gate": "quality", "artifact": handle["id"], "passed": all(c["passed"] for c in checks),
            "failures": [c for c in checks if not c["passed"]], "n_checks": len(checks)}


def provenance_gate(handle: dict, contract: dict, catalog: dict, provenance: list, stage: str = "materialize",
                    candidate: str | None = None) -> dict:
    checks = []
    for part, trace in handle["traces"].items():
        for load in trace["loads"]:
            recs = authority_records(catalog, load["table"])
            if not recs:
                checks.append(_check(f"{part}:authority:{load['table']}", False, "no authority record"))
                continue
            distinct = {(r["version"], tuple(sorted(r["shard_hashes"].items()))) for r in recs}
            if len(distinct) > 1:
                checks.append(_check(f"{part}:authority:{load['table']}", False,
                                     f"AMBIGUOUS_AUTHORITY: {len(recs)} conflicting records, no precedence rule"))
                continue
            rec = recs[0]
            wrong = [s for s, v in load["shards"].items()
                     if v["version"] != rec["version"] or v["declared_sha256"] != rec["shard_hashes"].get(s)]
            wanted = {s for s in rec["shard_hashes"] if s.startswith(part + "-")}
            absent = sorted(wanted - set(load["shards"]))
            ok = not wrong and not absent
            checks.append(_check(f"{part}:authority:{load['table']}", ok,
                                 (f"{len(wrong)} shards not matching authorised version {rec['version']} "
                                  f"(examples {wrong[:3]}); {len(absent)} authorised shards absent") if not ok else ""))
            drift = [s for s, v in load["shards"].items()
                     if v.get("content_sha256") and v["content_sha256"] != rec["shard_hashes"].get(s)]
            checks.append(_check(f"{part}:content_hash:{load['table']}", not drift,
                                 (f"{len(drift)} loaded shards have content whose SHA-256 differs from the authority "
                                  f"record although the file metadata declares the authorised hash (examples {drift[:3]})")
                                 if drift else ""))
        lin = trace.get("column_lineage", {})
        orphan = [c for c in contract["required_features"] if c in lin and not lin[c]]
        checks.append(_check(f"{part}:lineage_complete", not orphan, f"columns without source lineage {orphan}" if orphan else ""))
    fits = [p for p in provenance if p.get("activity") == "fit_evaluate" and p.get("handle") == handle["id"]]
    bad_scope = [f for f in fits if f.get("fit_partitions") != ["train"]]
    checks.append(_check("fit_scope", not bad_scope, f"{len(bad_scope)} fits used non-training partitions" if bad_scope else ""))
    if stage == "submit":
        prod = [p for p in provenance if p.get("activity") == "materialize_features" and p.get("handle") == handle["id"]]
        consistent = bool(prod) and prod[-1].get("graph_hash") == handle["graph_hash"]
        checks.append(_check("artifact_consistency", consistent, "" if consistent else "submitted handle not produced in this run"))
        if candidate is not None:
            ev = any(f.get("candidate") == candidate and f.get("status") == "ok" for f in fits)
            checks.append(_check("candidate_evaluated", ev, "" if ev else f"candidate {candidate} was not evaluated on {handle['id']}"))
    return {"gate": "provenance", "artifact": handle["id"], "stage": stage, "passed": all(c["passed"] for c in checks),
            "failures": [c for c in checks if not c["passed"]], "n_checks": len(checks)}


def fit_quality_gate(result: dict, handle_id: str) -> dict:
    rows = result.get("rows", {})
    tr = rows.get("train", {})
    cov = rows.get("validation_coverage", 1.0)
    checks = [_check("label_match:train", tr.get("unmatched_rows", 0) == 0,
                     f"{tr.get('unmatched_rows')} training rows have no canonical label match" if tr.get("unmatched_rows") else ""),
              _check("validation_coverage", abs(cov - 1.0) < 1e-12, f"validation coverage {cov:.4f}" if abs(cov - 1.0) >= 1e-12 else "")]
    return {"gate": "quality", "artifact": f"{handle_id}/{result.get('candidate')}", "stage": "fit",
            "passed": all(c["passed"] for c in checks), "failures": [c for c in checks if not c["passed"]], "n_checks": len(checks)}
