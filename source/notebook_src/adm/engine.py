"""Declarative transform graph: validation, source resolution and execution on any partition.

A graph never names files. ``load`` names a logical table and a version policy, so the same
frozen graph can be replayed by the evaluator on hidden test shards."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .core import df_hash, read_json

POLICIES = ["authoritative", "authoritative_verified", "latest_modified", "latest_snapshot"]  # plus "version:<v>"
STAT_LABELS = {"mean": "mean", "pop_std": "std", "sample_std": "std", "count": "count", "min": "min",
               "max": "max", "median": "median"}
OP_ARGS = {
    "load": {"required": ["table", "policy"], "optional": []},
    "parse_numeric": {"required": ["input"], "optional": ["columns"]},
    "to_canonical": {"required": ["input"], "optional": []},
    "map_alias": {"required": ["input"], "optional": ["key"]},
    "normalize_key": {"required": ["input"], "optional": ["key"]},
    "infer_representation": {"required": ["input"], "optional": []},
    "dedupe": {"required": ["input"], "optional": ["mode", "key"]},
    "join": {"required": ["left", "right", "on"], "optional": ["how", "cardinality"]},
    "aggregate": {"required": ["input", "key", "series_column", "value_column", "stats"], "optional": []},
    "drop_missing_rows": {"required": ["input"], "optional": ["columns"]},
    "project": {"required": ["input", "columns"], "optional": []},
}
MAX_NODES = 40
PACKAGING_COLUMNS = ("_shard", "_ingest_batch")
KEY_PATTERN = re.compile(r"([A-Z0-9]+)-(\d+)")
KEY_DIGITS = 6


def normalize_key_value(v):
    """Canonical observation_id format: upper-case <PREFIX>-<six digits>. Values that do not match the pattern after
    trimming and upper-casing (e.g. permitted aliases) are returned unchanged."""
    if v is None:
        return v
    m = KEY_PATTERN.fullmatch(str(v).strip().upper())
    return f"{m.group(1)}-{int(m.group(2)):0{KEY_DIGITS}d}" if m else v


class GraphError(ValueError):
    pass


class ResolutionError(GraphError):
    def __init__(self, msg: str, reason: str):
        super().__init__(msg)
        self.reason = reason


@dataclass
class CatalogView:
    """A catalog plus its source directory, restricted to one partition."""
    root: Path
    catalog: dict
    partition: str
    _cache: dict = field(default_factory=dict)

    @classmethod
    def open(cls, root, partition: str) -> "CatalogView":
        root = Path(root)
        return cls(root, read_json(root / "catalog.json"), partition)

    def read(self, f: dict) -> pd.DataFrame:
        key = f["file_id"]
        if key not in self._cache:
            self._cache[key] = pd.read_parquet(self.root / f["path"])
        return self._cache[key].copy()


# --------------------------------------------------------------------------- validation
def validate_graph(graph) -> dict:
    if not isinstance(graph, dict):
        raise GraphError("graph must be an object with 'nodes' and 'output'")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise GraphError("graph.nodes must be a non-empty list")
    if len(nodes) > MAX_NODES:
        raise GraphError(f"graph has {len(nodes)} nodes; the limit is {MAX_NODES}")
    seen = set()
    for n in nodes:
        if not isinstance(n, dict):
            raise GraphError("every node must be an object")
        nid, op = n.get("id"), n.get("op")
        if not isinstance(nid, str) or not nid:
            raise GraphError("every node needs a string 'id'")
        if nid in seen:
            raise GraphError(f"duplicate node id {nid!r}")
        if op not in OP_ARGS:
            raise GraphError(f"node {nid}: unknown op {op!r}; allowed ops: {sorted(OP_ARGS)}")
        spec = OP_ARGS[op]
        for a in spec["required"]:
            if a not in n:
                raise GraphError(f"node {nid} ({op}) is missing argument {a!r}")
        extra = set(n) - set(spec["required"]) - set(spec["optional"]) - {"id", "op"}
        if extra:
            raise GraphError(f"node {nid} ({op}) has unknown arguments {sorted(extra)}")
        for ref in ("input", "left", "right"):
            if ref in n and n[ref] not in seen:
                raise GraphError(f"node {nid}: {ref} {n[ref]!r} must refer to an earlier node id")
        if op == "load":
            p = n["policy"]
            if not (p in POLICIES or (isinstance(p, str) and p.startswith("version:"))):
                raise GraphError(f"node {nid}: policy must be one of {POLICIES} or 'version:<v>'")
        if op == "dedupe" and n.get("mode", "exact") not in ("exact", "key"):
            raise GraphError(f"node {nid}: dedupe mode must be 'exact' or 'key'")
        if op == "join":
            if n.get("how", "inner") not in ("inner", "left"):
                raise GraphError(f"node {nid}: join how must be 'inner' or 'left'")
            if n.get("cardinality") not in (None, "one_to_one", "many_to_one", "one_to_many"):
                raise GraphError(f"node {nid}: cardinality must be one_to_one, many_to_one or one_to_many")
        if op == "aggregate":
            st = n["stats"]
            if not isinstance(st, list) or not st or any(s not in STAT_LABELS for s in st):
                raise GraphError(f"node {nid}: stats must be a non-empty list from {sorted(STAT_LABELS)}")
            labels = [STAT_LABELS[s] for s in st]
            if len(set(labels)) != len(labels):
                raise GraphError(f"node {nid}: stats {st} produce duplicate output labels")
        if op == "project" and (not isinstance(n["columns"], list) or not n["columns"]):
            raise GraphError(f"node {nid}: project columns must be a non-empty list")
        seen.add(nid)
    if graph.get("output") not in seen:
        raise GraphError("graph.output must name a node id")
    return graph


# --------------------------------------------------------------------------- resolution
def _candidates(view: CatalogView, table: str) -> dict:
    t = view.catalog["tables"].get(table)
    if t is None:
        raise GraphError(f"unknown table {table!r}; available: {sorted(view.catalog['tables'])}")
    out: dict = {}
    for f in t["files"]:
        if f["partition"] != view.partition:
            continue
        for s in f["shards"]:
            out.setdefault(s, []).append(f)
    return out


def authority_records(catalog: dict, table: str) -> list:
    return [a for a in catalog.get("authority", []) if a["table"] == table]


def shard_content_hash(view: CatalogView, f: dict, shard: str) -> str:
    d = view.read(f)
    return df_hash(d[d["_shard"] == shard].reset_index(drop=True))


def resolve(view: CatalogView, table: str, policy: str) -> tuple[pd.DataFrame, dict]:
    # tools such as profile_data pass the agent's policy straight through; an invalid one must be a normal tool error
    if not isinstance(policy, str) or not (policy in POLICIES or (policy.startswith("version:") and len(policy) > 8)):
        raise GraphError(f"policy {policy!r} is not valid; use one of {POLICIES} or 'version:<v>'")
    cands = _candidates(view, table)
    chosen: dict = {}
    if policy in ("authoritative", "authoritative_verified"):
        recs = authority_records(view.catalog, table)
        if not recs:
            raise ResolutionError(f"no authority record for table {table!r}", "REQUIRED_SOURCE_MISSING")
        distinct = {(r["version"], tuple(sorted(r["shard_hashes"].items()))) for r in recs}
        if len(distinct) > 1:
            raise ResolutionError(
                f"conflicting authority records for table {table!r}: " +
                "; ".join(f"{r['record_id']} ({r['registry']}) authorises version {r['version']}" for r in recs) +
                ". The catalog defines no precedence rule.", "AMBIGUOUS_AUTHORITY")
        rec = recs[0]
        wanted = {s: h for s, h in rec["shard_hashes"].items() if s.startswith(view.partition + "-")}
        if not wanted:
            raise ResolutionError(f"authority record for {table!r} lists no shards for partition {view.partition}",
                                  "REQUIRED_SOURCE_MISSING")
        for s, h in sorted(wanted.items()):
            match = [f for f in cands.get(s, []) if f["version"] == rec["version"] and f["shard_hashes"].get(s) == h]
            if policy == "authoritative_verified":
                # do not trust declared file metadata: keep only candidates whose actual content has the authorised hash
                match = [f for f in match if shard_content_hash(view, f, s) == h]
            if not match:
                raise ResolutionError(
                    f"table {table!r}: authorised version {rec['version']} for shard {s} is not available "
                    f"(available versions: {sorted({f['version'] for f in cands.get(s, [])})})", "REQUIRED_SOURCE_MISSING")
            chosen[s] = match[0]
    else:
        for s, fl in sorted(cands.items()):
            if policy == "latest_modified":
                chosen[s] = sorted(fl, key=lambda f: (f["modified"], f["file_id"]))[-1]
            elif policy == "latest_snapshot":
                chosen[s] = sorted(fl, key=lambda f: (f["snapshot_date"], f["modified"], f["file_id"]))[-1]
            else:
                v = policy.split(":", 1)[1]
                m = [f for f in fl if f["version"] == v]
                if not m:
                    raise ResolutionError(f"table {table!r}: shard {s} has no candidate with version {v}", "REQUIRED_SOURCE_MISSING")
                if len(m) > 1:
                    raise GraphError(f"table {table!r}: shard {s} has {len(m)} candidates with version {v}; "
                                     "use a policy that selects by authority")
                chosen[s] = m[0]
        if not chosen:
            raise GraphError(f"table {table!r} has no files for partition {view.partition}")
    frames, record = [], {}
    for s, f in sorted(chosen.items()):
        d = view.read(f)
        d = d[d["_shard"] == s]
        frames.append(d)
        record[s] = {"file_id": f["file_id"], "version": f["version"], "declared_sha256": f["shard_hashes"].get(s),
                     "content_sha256": df_hash(d.reset_index(drop=True))}
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    rejected = sorted({f["file_id"] for fl in cands.values() for f in fl} - {r["file_id"] for r in record.values()})
    return df, {"table": table, "policy": policy, "shards": record, "rejected_files": rejected}


# --------------------------------------------------------------------------- execution helpers
def parse_cell(v):
    if v is None:
        return np.nan, False
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v), False
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "<na>"):
        return np.nan, False
    enc = False
    if s.startswith("value:"):
        s, enc = s[6:].strip(), True
    return float(s), enc


def _shard_tables(lineage: dict, cols: list) -> set:
    out = set()
    for c in cols:
        out |= lineage.get(c, set())
    return out


def execute(graph: dict, view: CatalogView) -> tuple[pd.DataFrame, dict]:
    """Execute a validated graph on one partition. Returns the output frame and an execution trace."""
    validate_graph(graph)
    frames: dict = {}
    lineage: dict = {}   # node -> {column: set(tables)}
    single: dict = {}    # node -> table name when lineage is a single loaded table without joins
    trace = {"partition": view.partition, "nodes": [], "loads": [], "operations": []}
    for n in graph["nodes"]:
        op, nid = n["op"], n["id"]
        info: dict = {"id": nid, "op": op}
        try:
            if op == "load":
                df, rec = resolve(view, n["table"], n["policy"])
                trace["loads"].append({"node": nid, **rec})
                lineage[nid] = {c: {n["table"]} for c in df.columns}
                single[nid] = n["table"]
            else:
                src = n.get("input") or n.get("left")
                df = frames[src].copy()
                lin = copy.deepcopy(lineage[src])
                single[nid] = single.get(src) if op not in ("join", "aggregate") else None
                if op == "parse_numeric":
                    cols = n.get("columns", "all")
                    if cols in ("all", "all_numeric", None):
                        tab = single.get(src)
                        cat_types = view.catalog["tables"].get(tab, {}).get("columns", {}) if tab else {}
                        reps = view.catalog.get("representations", {})
                        cols = [c for c in df.columns if c in reps or cat_types.get(c) == "numeric"]
                    missing = [c for c in cols if c not in df.columns]
                    if missing:
                        raise GraphError(f"parse_numeric: columns not found {missing}")
                    parsed_locs = []
                    for c in cols:
                        if pd.api.types.is_numeric_dtype(df[c]):
                            df[c] = df[c].astype(float)
                            continue
                        vals, bad = [], []
                        for oid, v in zip(df["observation_id"] if "observation_id" in df else range(len(df)), df[c]):
                            try:
                                x, enc = parse_cell(v)
                            except (ValueError, TypeError):
                                bad.append(v)
                                x, enc = np.nan, False
                            if enc:
                                parsed_locs.append([str(oid), c])
                            vals.append(x)
                        if bad:
                            raise GraphError(f"parse_numeric: column {c!r} has unparseable values, e.g. {bad[:3]}")
                        df[c] = np.array(vals, dtype=float)
                    info["parsed_encoded"] = len(parsed_locs)
                    trace["operations"].append({"node": nid, "op": op, "locations": parsed_locs})
                elif op == "to_canonical":
                    tab = single.get(src)
                    if not tab:
                        raise GraphError("to_canonical must be applied to a single loaded table before any join or aggregate")
                    sr = view.catalog.get("shard_representations", {}).get(tab, {})
                    reps = view.catalog.get("representations", {})
                    converted = []
                    for shard, fmap in sr.items():
                        if not shard.startswith(view.partition + "-"):
                            continue
                        m = (df["_shard"] == shard).to_numpy()
                        if not m.any():
                            continue
                        for f, r in fmap.items():
                            if f not in df.columns:
                                continue
                            if not pd.api.types.is_numeric_dtype(df[f]):
                                raise GraphError(f"to_canonical: column {f!r} is not numeric; apply parse_numeric first")
                            o = reps[f]["options"][r]
                            df.loc[m, f] = (df.loc[m, f].astype(float) - o["b"]) / o["a"]
                            converted.append([shard, f, r])
                    info["converted"] = len(converted)
                    trace["operations"].append({"node": nid, "op": op, "table": tab, "locations": converted})
                elif op == "map_alias":
                    key = n.get("key", "observation_id")
                    if key not in df.columns:
                        raise GraphError(f"map_alias: key column {key!r} not found")
                    al, rec = resolve(view, view.catalog.get("alias_table", "key_aliases"), "authoritative")
                    trace["loads"].append({"node": nid + ":aliases", **rec})
                    amap = dict(zip(al["alias"], al["observation_id"]))
                    before = df[key].astype(str)
                    after = before.map(lambda x: amap.get(x, x))
                    changed = (before != after).to_numpy()
                    df[key] = after.to_numpy()
                    info["remapped"] = int(changed.sum())
                    trace["operations"].append({"node": nid, "op": op,
                                                "locations": sorted(set(after[changed].tolist()))})
                elif op == "normalize_key":
                    key = n.get("key", "observation_id")
                    if key not in df.columns:
                        raise GraphError(f"normalize_key: key column {key!r} not found")
                    before = df[key]
                    after = before.map(normalize_key_value)
                    changed = (before.astype(str) != after.astype(str)).to_numpy()
                    df[key] = after.to_numpy()
                    info["normalized"] = int(changed.sum())
                    trace["operations"].append({"node": nid, "op": op,
                                                "locations": sorted(set(after[changed].astype(str).tolist()))})
                elif op == "infer_representation":
                    tab = single.get(src)
                    if not tab:
                        raise GraphError("infer_representation must be applied to a single loaded table before any join "
                                         "or aggregate")
                    ranges = view.catalog.get("value_ranges") or {}
                    reps = view.catalog.get("representations", {})
                    declared = view.catalog.get("shard_representations", {}).get(tab, {})
                    converted = []
                    if "_shard" in df.columns:
                        for shard in sorted(df["_shard"].astype(str).unique()):
                            m = (df["_shard"] == shard).to_numpy()
                            for f in [c for c in df.columns if c in ranges and c in reps]:
                                if f in declared.get(shard, {}) or not pd.api.types.is_numeric_dtype(df[f]):
                                    continue
                                lo, hi = ranges[f]
                                v = df.loc[m, f].to_numpy(dtype=float)
                                v = v[~np.isnan(v)]
                                if not len(v):
                                    continue
                                inside = lambda x: float(((x >= lo - 1e-9) & (x <= hi + 1e-9)).mean())
                                if inside(v) >= 0.5:
                                    continue
                                best, best_f = None, 0.0
                                for r, o in reps[f]["options"].items():
                                    if r == "R0":
                                        continue
                                    fr = inside((v - o["b"]) / o["a"])
                                    if fr > best_f:
                                        best, best_f = r, fr
                                if best is not None and best_f >= 0.95:
                                    o = reps[f]["options"][best]
                                    df.loc[m, f] = (df.loc[m, f].astype(float) - o["b"]) / o["a"]
                                    converted.append([shard, f, best])
                    info["converted"] = len(converted)
                    if not ranges:
                        info["note"] = "catalog declares no value_ranges; nothing to infer"
                    trace["operations"].append({"node": nid, "op": op, "table": tab, "locations": converted})
                elif op == "dedupe":
                    mode = n.get("mode", "exact")
                    before = len(df)
                    if mode == "exact":
                        dmask = df.astype(str).duplicated(keep="first").to_numpy()
                    else:
                        key = n.get("key", "observation_id")
                        keys = [key] if isinstance(key, str) else list(key)
                        dmask = df.duplicated(subset=keys, keep="first").to_numpy()
                    removed = df.loc[dmask, "observation_id"].astype(str).tolist() if "observation_id" in df else []
                    df = df.loc[~dmask].reset_index(drop=True)
                    info["removed"] = before - len(df)
                    trace["operations"].append({"node": nid, "op": op, "mode": mode, "locations": sorted(set(removed))})
                elif op == "join":
                    right = frames[n["right"]].copy()
                    rlin = lineage[n["right"]]
                    on = n["on"] if isinstance(n["on"], list) else [n["on"]]
                    for k in on:
                        if k not in df.columns or k not in right.columns:
                            raise GraphError(f"join: key {k!r} missing on one side")
                    pack = [c for c in PACKAGING_COLUMNS if c in right.columns and c not in on]
                    if pack:
                        right = right.drop(columns=pack)
                    overlap = (set(df.columns) & set(right.columns)) - set(on)
                    if overlap:
                        raise GraphError(f"join: non-key columns present on both sides {sorted(overlap)}; project first")
                    for k in on:
                        if df[k].dtype != right[k].dtype:
                            df[k] = df[k].astype(str)
                            right[k] = right[k].astype(str)
                    validate = {"one_to_one": "1:1", "many_to_one": "m:1", "one_to_many": "1:m"}.get(n.get("cardinality"))
                    try:
                        df = df.merge(right, on=on, how=n.get("how", "inner"), validate=validate)
                    except pd.errors.MergeError as e:
                        raise GraphError(f"join: declared cardinality {n.get('cardinality')} violated: {e}")
                    for c in right.columns:
                        lin[c] = lin.get(c, set()) | rlin.get(c, set())
                    info["rows"] = len(df)
                elif op == "aggregate":
                    key, sc, vc = n["key"], n["series_column"], n["value_column"]
                    for c in (key, sc, vc):
                        if c not in df.columns:
                            raise GraphError(f"aggregate: column {c!r} not found")
                    if not pd.api.types.is_numeric_dtype(df[vc]):
                        raise GraphError(f"aggregate: value column {vc!r} is not numeric")
                    g = df.groupby([key, sc])[vc]
                    parts = []
                    for s in n["stats"]:
                        if s == "mean":
                            v = g.mean()
                        elif s == "pop_std":
                            v = g.std(ddof=0)
                        elif s == "sample_std":
                            v = g.std(ddof=1)
                        elif s == "count":
                            v = g.count().astype(float)
                        elif s == "min":
                            v = g.min()
                        elif s == "max":
                            v = g.max()
                        else:
                            v = g.median()
                        w = v.unstack(sc)
                        w.columns = [f"{c}_{STAT_LABELS[s]}" for c in w.columns]
                        parts.append(w)
                    df = pd.concat(parts, axis=1).reset_index()
                    src_tabs = lin.get(vc, set())
                    lin = {c: set(src_tabs) for c in df.columns}
                    info["rows"] = len(df)
                elif op == "drop_missing_rows":
                    cols = n.get("columns")
                    before = len(df)
                    df = df.dropna(subset=cols).reset_index(drop=True) if cols else df.dropna().reset_index(drop=True)
                    info["removed"] = before - len(df)
                elif op == "project":
                    missing = [c for c in n["columns"] if c not in df.columns]
                    if missing:
                        raise GraphError(f"project: columns not found {missing}; available {list(df.columns)[:40]}")
                    df = df[list(dict.fromkeys(n["columns"]))].copy()
                lineage[nid] = {c: lin.get(c, set()) for c in df.columns}
        except ResolutionError as e:
            raise ResolutionError(f"node {nid} ({op}): {e}", e.reason) from None
        except GraphError as e:
            raise GraphError(f"node {nid} ({op}): {e}") from None
        frames[nid] = df
        info["rows_out"] = int(len(df))
        trace["nodes"].append(info)
    out = frames[graph["output"]]
    if "observation_id" not in out.columns:
        raise GraphError("graph output must contain the observation_id column")
    trace["output_columns"] = list(out.columns)
    trace["column_lineage"] = {c: sorted(v) for c, v in lineage[graph["output"]].items()}
    trace["output_hash"] = df_hash(out)
    return out.reset_index(drop=True), trace


def summarize(df: pd.DataFrame, expected_ids: int | None = None, sample_rows: int = 3) -> dict:
    """Bounded summary of a materialised frame returned to agents (no verdicts)."""
    out = {
        "rows": int(len(df)),
        "distinct_observation_ids": int(df["observation_id"].nunique()) if "observation_id" in df else None,
        "columns": {c: str(df[c].dtype) for c in df.columns},
        "null_counts": {c: int(v) for c, v in df.isna().sum().items() if v},
    }
    if expected_ids is not None:
        out["visible_partition_size"] = expected_ids
    if sample_rows:
        out["sample"] = df.head(sample_rows).astype(object).where(df.head(sample_rows).notna(), None).to_dict("records")
    return out
