import gzip
import json
import math

import numpy as np
import pandas as pd
import pytest

from adm import engine as E
from adm import tasks as T
from adm.core import instance_dirs, read_json
from adm.fixed import contract_graph


def _matches(out, ref):
    o = out.assign(observation_id=out["observation_id"].astype(str)).sort_values("observation_id").reset_index(drop=True)
    r = ref.sort_values("observation_id").reset_index(drop=True)
    if len(o) != len(r) or not (o["observation_id"].values == r["observation_id"].values).all():
        return False
    for c in r.columns[1:]:
        if pd.api.types.is_numeric_dtype(r[c]):
            if not np.isclose(o[c].astype(float), r[c].astype(float), rtol=1e-6, atol=1e-8, equal_nan=True).all():
                return False
        elif not (o[c].astype(str).values == r[c].astype(str).values).all():
            return False
    return True


@pytest.mark.parametrize("fam,tmpl,cond", [("D5", "T1", "C2"), ("D5", "T2", "C4"), ("D6", "T3", "C3"),
                                           ("D6", "T4", "C6"), ("D5", "T5", "C5"), ("D6", "T6", "C4"), ("D5", "T6", "C1")])
def test_fixed_graph_reproduces_hidden_reference(paths, fam, tmpl, cond):
    T.build_instance(paths, "development", fam, tmpl, cond, 0)
    d = instance_dirs(paths, "development", fam, tmpl, cond, 0)
    c, cat = read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json")
    g = contract_graph(c, cat)
    for part, root in [("train", d["visible"]), ("validation", d["visible"]), ("test", d["private"])]:
        out, _ = E.execute(g, E.CatalogView.open(root, part))
        assert _matches(out, pd.read_parquet(d["private"] / f"reference_{part}.parquet")), (part, cond)


@pytest.mark.parametrize("fam,tmpl,cond", [("D5", "T1", "X1b"), ("D6", "T2", "X1c"), ("D5", "T3", "X2a"),
                                           ("D6", "T6", "X2c"), ("D5", "T4", "X3b"), ("D6", "T5", "X3c"),
                                           ("D5", "T6", "X3a"), ("D6", "T1", "X4a"), ("D5", "T3", "X4b"),
                                           ("D6", "T5", "X4c"), ("D5", "T6", "X4b")])
def test_tier2_oracle_solves_and_spec_graph_does_not(paths, fam, tmpl, cond):
    """Tier 2: every instance is solvable by the oracle; the declared-specification graph (F) fails on it."""
    from adm.fixed import oracle_graph
    T.build_instance(paths, "development", fam, tmpl, cond, 0)
    d = instance_dirs(paths, "development", fam, tmpl, cond, 0)
    c, cat = read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json")
    spec_ok = True
    for part, root in [("train", d["visible"]), ("validation", d["visible"]), ("test", d["private"])]:
        ref = pd.read_parquet(d["private"] / f"reference_{part}.parquet")
        out, _ = E.execute(oracle_graph(c, cat), E.CatalogView.open(root, part))
        assert _matches(out, ref), (part, cond)
        try:
            spec_out, _ = E.execute(contract_graph(c, cat), E.CatalogView.open(root, part))
            spec_ok &= _matches(spec_out, ref)
        except E.GraphError:
            spec_ok = False
    assert not spec_ok, f"{cond}: the declared-specification graph should not solve a Tier-2 instance"
    assert "_ingest_batch" in c["excluded_predictors"] and "value_ranges" in cat


def test_tier1_instances_unchanged_by_tier2_code(paths):
    """Tier-1 contracts and catalogs carry no Tier-2 fields (their content digests must stay reproducible)."""
    T.build_instance(paths, "development", "D5", "T2", "C3", 1)
    d = instance_dirs(paths, "development", "D5", "T2", "C3", 1)
    c, cat = read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json")
    assert "_ingest_batch" not in c["excluded_predictors"] and "value_ranges" not in cat
    assert all("_ingest_batch" not in t["columns"] for t in cat["tables"].values())


def test_content_drift_is_a_provenance_defect(paths):
    """X4: declared metadata matches the authority record, so 'authoritative' loads drifted content; only the provenance
    gate's content-hash check flags it; the quality gate's value-range check does not; heuristics do not repair it."""
    from adm import gates as G
    T.build_instance(paths, "development", "D5", "T1", "X4c", 1)
    d = instance_dirs(paths, "development", "D5", "T1", "X4c", 1)
    c, cat = read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json")
    man = read_json(d["visible"] / "visible_partition_manifest.json")
    view = lambda p: E.CatalogView.open(d["visible"], p)
    g = contract_graph(c, cat)
    frames, traces = {}, {}
    for p in ("train", "validation"):
        frames[p], traces[p] = E.execute(g, view(p))
    handle = {"id": "H1", "graph": g, "frames": frames, "traces": traces}
    prov = G.provenance_gate(handle, c, cat, [])
    assert any(f["check"].startswith("train:content_hash") for f in prov["failures"])
    qual = G.quality_gate(handle, c, cat, man)
    assert not any("value_ranges" in f["check"] for f in qual["failures"])
    for pol in ("latest_modified", "latest_snapshot"):
        g2 = {"nodes": [dict(n, policy=pol) if n["op"] == "load" else n for n in g["nodes"]], "output": g["output"]}
        out, tr = E.execute(g2, view("train"))
        assert any(not v["file_id"].endswith("__replica") for l in tr["loads"] for v in l["shards"].values())


def test_tier2_instances_carry_replicas_and_tier1_do_not(paths):
    for cond, expect in (("X2b", True), ("C3", False)):
        T.build_instance(paths, "development", "D6", "T2", cond, 2)
        cat = read_json(instance_dirs(paths, "development", "D6", "T2", cond, 2)["visible"] / "catalog.json")
        has = any(f["file_id"].endswith("__replica") for t in cat["tables"].values() for f in t["files"])
        assert has == expect, cond


def test_invalid_policy_is_a_tool_error_not_a_crash(paths):
    T.build_instance(paths, "development", "D5", "T1", "C0", 0)
    view = E.CatalogView.open(instance_dirs(paths, "development", "D5", "T1", "C0", 0)["visible"], "train")
    for bad in ("authority", "version", "version:", None, 3):
        with pytest.raises(E.GraphError):
            E.resolve(view, "observations", bad)


def test_normalize_key_value():
    assert E.normalize_key_value(" D5X-000060 ") == "D5X-000060"
    assert E.normalize_key_value("d5x-000060") == "D5X-000060"
    assert E.normalize_key_value("D5X-60") == "D5X-000060"
    assert E.normalize_key_value("d5x_60") == "d5x_60"  # permitted alias format is left for map_alias


def test_corruption_counts_and_ledger(paths):
    meta = T.build_instance(paths, "development", "D5", "T2", "C4", 1)
    d = instance_dirs(paths, "development", "D5", "T2", "C4", 1)
    ledger = json.load(gzip.open(d["private"] / "ledger.json.gz", "rt"))
    for part, info in meta["realized_severity"].items():
        assert info["affected"] == int(math.floor(0.20 * info["denominator"] + 0.5))
        n = sum(1 for e in ledger if e["partition"] == part)
        assert n == info["affected"]
    meta = T.build_instance(paths, "development", "D6", "T1", "C2", 1)
    for part, info in meta["realized_severity"].items():
        assert info["missing"] - info["encoded"] in (0, 1)


def test_visible_dirs_hold_no_test_data(paths):
    T.build_instance(paths, "development", "D5", "T3", "C0", 2)
    d = instance_dirs(paths, "development", "D5", "T3", "C0", 2)
    lab = pd.read_parquet(d["trusted"] / "labels.parquet")
    assert set(lab["partition"]) == {"train", "validation"}
    cat = read_json(d["visible"] / "catalog.json")
    assert all(f["partition"] != "test" for t in cat["tables"].values() for f in t["files"])
    names = {p.name for p in d["visible"].rglob("*")}
    assert not any("test" in n for n in names)


@pytest.mark.parametrize("cond,reason", [("N1", "REQUIRED_SOURCE_MISSING"), ("N2", "AMBIGUOUS_AUTHORITY")])
def test_negative_controls(paths, cond, reason):
    T.build_instance(paths, "development", "D6", "T2", cond, 0)
    d = instance_dirs(paths, "development", "D6", "T2", cond, 0)
    c, cat = read_json(d["visible"] / "contract.json"), read_json(d["visible"] / "catalog.json")
    with pytest.raises(E.ResolutionError) as ei:
        E.execute(contract_graph(c, cat), E.CatalogView.open(d["visible"], "train"))
    assert ei.value.reason == reason


def test_instance_digest_reproducible(paths):
    a = T.build_instance(paths, "development", "D6", "T5", "C6", 1)["hashes"]
    b = T.build_instance(paths, "development", "D6", "T5", "C6", 1)["hashes"]
    assert a == b


def test_graph_validation_errors():
    with pytest.raises(E.GraphError):
        E.validate_graph({"nodes": [{"id": "a", "op": "rm_rf", "table": "x"}], "output": "a"})
    with pytest.raises(E.GraphError):
        E.validate_graph({"nodes": [{"id": "a", "op": "project", "input": "zz", "columns": ["x"]}], "output": "a"})
    assert E.parse_cell("value:1.50")[0] == E.parse_cell("1.5")[0] == 1.5
