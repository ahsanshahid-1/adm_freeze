"""Task templates T1-T6, catalogs, contracts, controlled defects C1-C6, negative controls N1/N2,
hidden corruption ledgers and independently computed reference features (Sections 6-7)."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .core import (Paths, TEMPLATES, base_task_index, df_hash, instance_dirs, make_rng, read_json,
                   write_json, sha256_file, json_hash, dumps)
from .datasets import FamilySpec, load_canonical, load_split

N_SHARDS = 20
AS_OF = "2025-06-30"
SNAPSHOTS = {"v1": "2024-12-31", "v2": "2025-06-30", "v3": "2025-09-30"}
MODIFIED = {"v1": "2024-12-31T00:00:00Z", "v2": "2025-06-30T00:00:00Z", "v3": "2025-09-30T00:00:00Z",
            "refresh": "2025-10-15T00:00:00Z"}
READINGS_PER_SERIES = 5
CONDITION_SPEC = {
    "C0": ("clean", 0.0), "C1": ("cell", 0.05), "C2": ("cell", 0.20), "C3": ("key", 0.05), "C4": ("key", 0.20),
    "C5": ("semantic", 0.05), "C6": ("semantic", 0.20), "N1": ("negative", 0.0), "N2": ("negative", 0.0),
}
SEMANTIC_SHARDS = {"C5": 1, "C6": 4}
# Tier 2 (main-plan-v2.1 Section 7.6): recoverable defects outside the declared data-format specification, each at three
# graded levels for calibration on development tasks. X1 near-duplicates (differ only in the packaging column
# _ingest_batch), X2 key-format variants not covered by the alias table, X3 undeclared shard representations.
TIER2 = {"X1a": ("near_dup", 0.05), "X1b": ("near_dup", 0.10), "X1c": ("near_dup", 0.20),
         "X2a": ("key_variant", 0.05), "X2b": ("key_variant", 0.10), "X2c": ("key_variant", 0.20),
         "X3a": ("undeclared_rep", 1), "X3b": ("undeclared_rep", 2), "X3c": ("undeclared_rep", 4),
         # X4 content drift (provenance type): the primary authorised file's content for k shards no longer matches the
         # authority hash, while the catalog file entry still declares the authorised hash; a replica with the authorised
         # content exists. Detectable only by verifying content hashes (provenance check); repaired by
         # load policy 'authoritative_verified'.
         "X4a": ("content_drift", 1), "X4b": ("content_drift", 2), "X4c": ("content_drift", 4)}
CONDITION_SPEC.update(TIER2)
from .core import TIER2_CONDITIONS as _T2, TIER2_DESIGN as _T2D  # noqa: E402
assert set(_T2) | set(_T2D) == set(TIER2)
TIER2_KINDS = {"near_dup", "key_variant", "undeclared_rep", "content_drift"}
REPLICA_MODIFIED = "2025-06-29T12:00:00Z"  # earlier than the primary: modification-time heuristics never pick it
GENERATOR_VERSION = 2  # cached instances built by an older generator are rebuilt (content digests are still verified)
PACKAGING_COLUMNS = ("_shard", "_ingest_batch")
PARTS = ["train", "validation", "test"]
VISIBLE_PARTS = ["train", "validation"]
TEMPLATE_DESCRIPTIONS = {
    "T1": "Single-source modeling: locate the observation-level feature source, respect predictor exclusions, prepare data and fit a model.",
    "T2": "Two-table reconstruction: permitted predictors are split across two vertical tables joined one-to-one by observation_id.",
    "T3": "Three-table integration: observations, a second feature block and a profile metadata relation joined through declared keys.",
    "T4": "Unit/representation harmonization: numeric features are stored in shard-level representations that must be converted to canonical units.",
    "T5": "Version-aware analysis: several snapshots exist; select the version required by the authoritative as-of catalog.",
    "T6": "Aggregate-feature construction: two predictors are supplied only as child readings that must be summarised before modeling.",
}


# --------------------------------------------------------------------------- numeric grammar
def encode_value(x: float) -> str:
    return f"value:{repr(float(x))}"


def plain_literal(x) -> str | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return repr(float(x))


# --------------------------------------------------------------------------- representations
_REAL_UNITS = {
    "air_temperature_k": [("celsius", 1.0, -273.15), ("fahrenheit", 1.8, -459.67)],
    "process_temperature_k": [("celsius", 1.0, -273.15), ("fahrenheit", 1.8, -459.67)],
    "rotational_speed_rpm": [("rad_per_s", 2 * math.pi / 60.0, 0.0), ("rev_per_s", 1 / 60.0, 0.0)],
    "torque_nm": [("kilonewton_metre", 0.001, 0.0), ("pound_force_foot", 0.737562149277, 0.0)],
    "tool_wear_min": [("hours", 1 / 60.0, 0.0), ("seconds", 60.0, 0.0)],
    "age_day": [("weeks", 1 / 7.0, 0.0), ("hours", 24.0, 0.0)],
}
_CANON_UNITS = {"air_temperature_k": "kelvin", "process_temperature_k": "kelvin", "rotational_speed_rpm": "rpm",
                "torque_nm": "newton_metre", "tool_wear_min": "minutes", "age_day": "days"}


def representation_options(spec: FamilySpec) -> dict:
    out = {}
    for f in spec.numeric:
        if f in _REAL_UNITS:
            opts = _REAL_UNITS[f]
            canon = _CANON_UNITS[f]
        elif f.endswith("_kg_m3"):
            opts = [("pound_per_cubic_yard", 1.685555, 0.0), ("gram_per_cubic_centimetre", 0.001, 0.0)]
            canon = "kilogram_per_cubic_metre"
        else:
            opts = [("synthetic_scaled_x100", 100.0, 0.0), ("synthetic_scaled_0.01_offset_1000", 0.01, 1000.0)]
            canon = "canonical (dimensionless or as published)"
        out[f] = {"canonical_unit": canon,
                  "options": {"R0": {"a": 1.0, "b": 0.0, "unit": canon}}
                  | {f"R{i + 1}": {"a": a, "b": b, "unit": u} for i, (u, a, b) in enumerate(opts)}}
    return out


# --------------------------------------------------------------------------- shards and helpers
def shard_map(split_df: pd.DataFrame, family: str, suite: str, rep: int) -> pd.Series:
    rng = make_rng("split", family, suite, rep, "shards")
    out = {}
    for p in PARTS:
        ids = np.sort(split_df.loc[split_df["partition"] == p, "observation_id"].to_numpy())
        perm = rng.permutation(len(ids))
        for rank, i in enumerate(perm):
            out[ids[i]] = f"{p}-{rank % N_SHARDS:02d}"
    return pd.Series(out, name="_shard")


def _alias(oid: str) -> str:
    fam, num = oid.split("-")
    return f"{fam.lower()}_{int(num)}"


def _profile_key(values: tuple) -> str:
    return "P" + hashlib.sha1(repr(values).encode()).hexdigest()[:12]


def _ranges(df: pd.DataFrame, cols: list) -> dict:
    out = {}
    for c in cols:
        v = df[c].astype(float)
        lo, hi = float(v.min()), float(v.max())
        span = max(hi - lo, 1e-9)
        out[c] = [lo - 0.25 * span, hi + 0.25 * span]
    return out


# --------------------------------------------------------------------------- relational templates
def _template_layout(spec: FamilySpec, template: str) -> dict:
    """Which canonical columns go to which logical table (pure function of the template)."""
    feats = list(spec.features)
    ex = list(spec.excluded)
    if template in ("T1", "T4", "T5"):
        return {"observations": {"cols": ex + feats, "grain": "observation"}}
    if template == "T2":
        k = math.ceil(len(feats) / 2)
        return {"block_a": {"cols": ex + feats[:k], "grain": "observation"},
                "block_b": {"cols": feats[k:], "grain": "observation"}}
    if template == "T3":
        blocks = [list(b) for b in np.array_split(np.array(feats, dtype=object), 3)]
        return {"observations": {"cols": ex + blocks[0], "grain": "observation", "fk": "profile_key"},
                "measurements_b": {"cols": blocks[1], "grain": "observation"},
                "profiles": {"cols": blocks[2], "grain": "profile"}}
    if template == "T6":
        sel = spec.numeric[:2]
        rest = [f for f in feats if f not in sel]
        return {"observations": {"cols": ex + rest, "grain": "observation"},
                "readings": {"cols": ["series", "reading_index", "value"], "grain": "reading", "series": sel}}
    raise ValueError(template)


def required_features(spec: FamilySpec, template: str) -> list:
    if template != "T6":
        return list(spec.features)
    sel = spec.numeric[:2]
    out = []
    for f in spec.features:
        if f in sel:
            out += [f"{f}_mean", f"{f}_std", f"{f}_count"]
        else:
            out.append(f)
    return out


def _readings(df: pd.DataFrame, spec: FamilySpec, suite: str, sel: list) -> pd.DataFrame:
    """Five child readings per selected predictor, derived with seeded feature-only noise (no labels)."""
    ns = "evaluation" if suite == "evaluation" else "development"
    rows = []
    for f in sel:
        rng = make_rng(ns, spec.family, "T6", "", f"readings:{f}")
        v = df[f].to_numpy(dtype=float)
        sd = float(np.nanstd(v)) or 1.0
        noise = rng.normal(0.0, 0.05 * sd, size=(len(v), READINGS_PER_SERIES))
        vals = v[:, None] + noise
        for j in range(READINGS_PER_SERIES):
            rows.append(pd.DataFrame({"observation_id": df["observation_id"].to_numpy(), "series": f,
                                      "reading_index": j, "value": vals[:, j]}))
    r = pd.concat(rows, ignore_index=True)
    return r.sort_values(["observation_id", "series", "reading_index"], kind="mergesort").reset_index(drop=True)


def _snapshot(df: pd.DataFrame, spec: FamilySpec, version: str, suite: str, cols: list) -> pd.DataFrame:
    """Earlier/later snapshot: numeric features perturbed independently of labels."""
    if version == "v2":
        return df.copy()
    ns = "evaluation" if suite == "evaluation" else "development"
    rng = make_rng(ns, spec.family, "snapshot", "", version)
    out = df.copy()
    for c in cols:
        if c in spec.numeric:
            v = out[c].to_numpy(dtype=float)
            sd = float(np.nanstd(v)) or 1.0
            out[c] = v + rng.normal(0.0, 0.1 * sd, size=len(v))
    return out


def reference_features(df: pd.DataFrame, spec: FamilySpec, template: str, suite: str) -> pd.DataFrame:
    """Independent reference computation of the correct canonical feature table (all partitions, clean)."""
    req = required_features(spec, template)
    if template != "T6":
        return df[["observation_id"] + req].copy()
    sel = spec.numeric[:2]
    r = _readings(df, spec, suite, sel)
    out = df[["observation_id"] + [f for f in spec.features if f not in sel]].copy()
    for f in sel:
        g = r[r["series"] == f].groupby("observation_id")["value"]
        agg = pd.DataFrame({f"{f}_mean": g.mean(), f"{f}_std": g.std(ddof=0), f"{f}_count": g.count().astype(float)})
        out = out.merge(agg, left_on="observation_id", right_index=True, how="left")
    return out[["observation_id"] + req]


# --------------------------------------------------------------------------- instance builder
class InstanceBuilder:
    def __init__(self, paths: Paths, suite: str, family: str, template: str, condition: str, rep: int):
        self.paths, self.suite, self.family, self.template = paths, suite, family, template
        self.condition, self.rep = condition, rep
        self.df, self.spec = load_canonical(paths, suite, family)
        self.split = load_split(paths, suite, family, rep)
        self.part_of = dict(zip(self.split["observation_id"], self.split["partition"]))
        self.shards = shard_map(self.split, family, suite, rep)
        self.layout = _template_layout(self.spec, template)
        self.reps = representation_options(self.spec)
        self.ledger: list = []
        self.task = f"{family}-{template}"
        self.versions = ["v2"]
        if template == "T5":
            self.versions = ["v1", "v2", "v3"]
        self.primary = "observations" if "observations" in self.layout else "block_a"
        if condition in ("N1", "N2") and template != "T5":
            self.versions_for = {self.primary: ["v1", "v2", "v3"]}
        else:
            self.versions_for = {}
        self.tier2 = CONDITION_SPEC[condition][0] in TIER2_KINDS

    # ----- clean relational tables (canonical units, all partitions)
    def clean_tables(self) -> dict:
        d = self.df.copy()
        d["_shard"] = d["observation_id"].map(self.shards)
        d["_partition"] = d["observation_id"].map(self.part_of)
        tables = {}
        for name, info in self.layout.items():
            if info["grain"] == "observation":
                cols = ["observation_id"] + info["cols"]
                t = d[cols + ["_shard", "_partition"]].copy()
                if info.get("fk") == "profile_key":
                    pcols = self.layout["profiles"]["cols"]
                    t["profile_key"] = [_profile_key(tuple(r)) for r in d[pcols].itertuples(index=False, name=None)]
                    t = t[["observation_id", "profile_key"] + info["cols"] + ["_shard", "_partition"]]
                tables[name] = t
            elif info["grain"] == "profile":
                pcols = info["cols"]
                t = d[pcols + ["_partition"]].copy()
                t.insert(0, "profile_key", [_profile_key(tuple(r)) for r in d[pcols].itertuples(index=False, name=None)])
                t = t.drop_duplicates(["profile_key", "_partition"]).sort_values(["_partition", "profile_key"], kind="mergesort")
                t["_shard"] = t["_partition"] + "-all"
                tables[name] = t[["profile_key"] + pcols + ["_shard", "_partition"]].reset_index(drop=True)
            elif info["grain"] == "reading":
                r = _readings(d, self.spec, self.suite, info["series"])
                r["_shard"] = r["observation_id"].map(self.shards)
                r["_partition"] = r["observation_id"].map(self.part_of)
                tables[name] = r
        if self.template == "T1":
            # decoy: per-shard summary (wrong grain)
            agg = d.groupby(["_partition", "_shard"])[self.spec.numeric].mean().reset_index()
            agg.insert(0, "shard_summary_id", agg["_shard"])
            tables["observations_rollup"] = agg[["shard_summary_id"] + self.spec.numeric + ["_shard", "_partition"]]
        al = pd.DataFrame({"alias": [_alias(o) for o in d["observation_id"]], "observation_id": d["observation_id"],
                           "_partition": d["_partition"]})
        al["_shard"] = al["_partition"] + "-all"
        tables["key_aliases"] = al.sort_values(["_partition", "observation_id"], kind="mergesort").reset_index(drop=True)
        return {k: t.reset_index(drop=True) for k, t in tables.items()}

    def table_meta(self, name: str) -> dict:
        if name == "key_aliases":
            return {"grain": "alias", "key": "alias", "description": "Complete catalog mapping every permitted key alias to its canonical observation_id."}
        if name == "observations_rollup":
            return {"grain": "shard_summary", "key": "shard_summary_id",
                    "description": "Per-shard mean summary of numeric measurements (one row per packaging shard; NOT observation-level)."}
        info = self.layout[name]
        desc = {"observation": "Observation-level records keyed by observation_id.",
                "profile": "Profile metadata relation keyed by profile_key (many observations may share one profile).",
                "reading": "Child readings: several rows per observation and series (one-to-many)."}[info["grain"]]
        key = {"observation": "observation_id", "profile": "profile_key", "reading": "observation_id"}[info["grain"]]
        return {"grain": info["grain"], "key": key, "description": desc}

    # ----- defects
    def _obs_tables(self, tables: dict) -> list:
        return [n for n in self.layout if self.layout[n]["grain"] in ("observation", "reading")]

    def _cell_tables(self) -> list:
        return [n for n in self.layout if self.layout[n]["grain"] == "observation"]

    def apply_representations(self, tables: dict) -> dict:
        """Per-shard stored representations: all shards for T4, selected shards for C5/C6 unit subtype."""
        shard_reps: dict = {}
        if self.template == "T4":
            rng = make_rng("evaluation" if self.suite == "evaluation" else "development", self.family, self.task, self.rep, "T4-representations")
            t = tables["observations"]
            for shard in sorted(t["_shard"].unique()):
                for f in self.spec.numeric:
                    r = ["R0", "R1", "R2"][int(rng.integers(0, 3))]
                    if r != "R0":
                        shard_reps.setdefault("observations", {}).setdefault(shard, {})[f] = r
        return shard_reps

    @staticmethod
    def _apply_affine(t: pd.DataFrame, shard_reps_t: dict, reps: dict) -> pd.DataFrame:
        t = t.copy()
        for shard, fmap in shard_reps_t.items():
            m = t["_shard"] == shard
            for f, r in fmap.items():
                o = reps[f]["options"][r]
                t.loc[m, f] = o["a"] * t.loc[m, f].astype(float) + o["b"]
        return t

    def corrupt_cells(self, tables: dict, rate: float, part: str) -> dict:
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:cell:{part}")
        cells = []
        for n in self._cell_tables():
            t = tables[n]
            cols = [c for c in self.layout[n]["cols"] if c in self.spec.numeric]
            idx = t.index[t["_partition"] == part]
            ids = t.loc[idx, "observation_id"].to_numpy()
            for c in cols:
                valid = t.loc[idx, c].notna().to_numpy()
                for i, oid, ok in zip(idx, ids, valid):
                    if ok:
                        cells.append((oid, n, c, i))
        cells.sort(key=lambda x: (x[0], x[1], x[2]))
        N = len(cells)
        k = int(math.floor(rate * N + 0.5))
        pick = rng.permutation(N)[:k]
        n_missing = (k + 1) // 2
        string_cols = set()
        actions = []
        for j, pi in enumerate(pick):
            oid, n, c, i = cells[pi]
            actions.append((oid, n, c, i, "missing" if j < n_missing else "encoded"))
            if j >= n_missing:
                string_cols.add((n, c))
        # convert affected columns to string (plain literals) for this partition's files
        for (n, c) in string_cols:
            t = tables[n]
            if t[c].dtype != object:
                t[c] = t[c].astype(object)
                t[c] = [plain_literal(v) if isinstance(v, (float, int, np.floating, np.integer)) else v for v in t[c]]
        for oid, n, c, i, kind in actions:
            t = tables[n]
            before = t.at[i, c]
            bval = None if before is None else float(before)
            if kind == "missing":
                t.at[i, c] = None if t[c].dtype == object else np.nan
            else:
                t.at[i, c] = encode_value(bval)
            self.ledger.append({"partition": part, "defect": f"cell_{kind}", "table": n, "observation_id": oid,
                                "column": c, "before": bval, "after": None if kind == "missing" else t.at[i, c],
                                "denominator": N, "reversible": kind == "encoded"})
        return {"denominator": N, "affected": k, "missing": n_missing, "encoded": k - n_missing}

    def corrupt_keys(self, tables: dict, rate: float, part: str) -> dict:
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:key:{part}")
        ids = np.sort(self.split.loc[self.split["partition"] == part, "observation_id"].to_numpy())
        N = len(ids)
        k = int(math.floor(rate * N + 0.5))
        pick = ids[rng.permutation(N)[:k]]
        n_dup = (k + 1) // 2
        obs_tables = self._obs_tables(tables)
        index_of = {n: tables[n].groupby("observation_id").indices for n in obs_tables}
        dups: dict = {n: [] for n in obs_tables}
        for j, oid in enumerate(pick):
            tname = obs_tables[int(rng.integers(0, len(obs_tables)))]
            t = tables[tname]
            rows = index_of[tname][oid]
            if j < n_dup:
                r = int(rows[int(rng.integers(0, len(rows)))])
                dups[tname].append(r)
                self.ledger.append({"partition": part, "defect": "duplicate", "table": tname, "observation_id": oid,
                                    "denominator": N, "reversible": True})
            else:
                al = _alias(oid)
                t.loc[t.index[rows], "observation_id"] = al
                self.ledger.append({"partition": part, "defect": "alias", "table": tname, "observation_id": oid,
                                    "alias": al, "rows": int(len(rows)), "denominator": N, "reversible": True})
        for tname, rs in dups.items():
            if rs:
                t = tables[tname]
                pos = np.arange(len(t), dtype=float)
                extra = t.iloc[rs].copy()
                order = np.concatenate([pos, np.array(rs, dtype=float) + 0.5])
                merged = pd.concat([t, extra], ignore_index=True)
                tables[tname] = merged.iloc[np.argsort(order, kind="mergesort")].reset_index(drop=True)
        return {"denominator": N, "affected": k, "duplicates": n_dup, "aliases": k - n_dup}

    # ----- Tier 2 defects (outside the declared specification; every one is recoverable)
    def add_ingest_batch(self, tables: dict):
        """Tier-2 instances carry a packaging column on observation-grain tables (identical in all Tier-2 conditions,
        so its presence does not reveal which defect is present)."""
        for n in self._cell_tables():
            t = tables[n]
            t.insert(list(t.columns).index("_shard"), "_ingest_batch", "batch-01")

    def near_duplicates(self, tables: dict, rate: float, part: str) -> dict:
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:near_dup:{part}")
        ids = np.sort(self.split.loc[self.split["partition"] == part, "observation_id"].to_numpy())
        N = len(ids)
        k = int(math.floor(rate * N + 0.5))
        pick = ids[rng.permutation(N)[:k]]
        names = self._cell_tables()
        index_of = {n: tables[n].groupby("observation_id").indices for n in names}
        dups: dict = {n: [] for n in names}
        for oid in pick:
            tname = names[int(rng.integers(0, len(names)))]
            rows = index_of[tname][oid]
            dups[tname].append(int(rows[0]))
            self.ledger.append({"partition": part, "defect": "near_duplicate", "table": tname, "observation_id": oid,
                                "denominator": N, "reversible": True})
        for tname, rs in dups.items():
            if rs:
                t = tables[tname]
                extra = t.iloc[rs].copy()
                extra["_ingest_batch"] = "batch-02"
                order = np.concatenate([np.arange(len(t), dtype=float), np.array(rs, dtype=float) + 0.5])
                merged = pd.concat([t, extra], ignore_index=True)
                tables[tname] = merged.iloc[np.argsort(order, kind="mergesort")].reset_index(drop=True)
        return {"denominator": N, "affected": k}

    def key_variants(self, tables: dict, rate: float, part: str) -> dict:
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:key_variant:{part}")
        ids = np.sort(self.split.loc[self.split["partition"] == part, "observation_id"].to_numpy())
        N = len(ids)
        k = int(math.floor(rate * N + 0.5))
        pick = ids[rng.permutation(N)[:k]]
        names = self._obs_tables(tables)
        index_of = {n: tables[n].groupby("observation_id").indices for n in names}
        kinds = ["lower", "unpadded", "padded_space"]
        for oid in pick:
            tname = names[int(rng.integers(0, len(names)))]
            kind = kinds[int(rng.integers(0, len(kinds)))]
            prefix, num = oid.rsplit("-", 1)
            variant = {"lower": oid.lower(), "unpadded": f"{prefix}-{int(num)}", "padded_space": f" {oid} "}[kind]
            rows = index_of[tname][oid]
            t = tables[tname]
            t.loc[t.index[rows], "observation_id"] = variant
            self.ledger.append({"partition": part, "defect": "key_variant", "table": tname, "observation_id": oid,
                                "variant": kind, "rows": int(len(rows)), "denominator": N, "reversible": True})
        return {"denominator": N, "affected": k}

    def undeclared_representations(self, tables: dict, n_shards: int, part: str, shard_reps: dict) -> dict:
        """Store k shards per partition in a documented representation that catalog.shard_representations does not
        declare. Only (shard, column, representation) choices that are detectable against the contract value ranges
        and uniquely invertible are used, so the correct canonical values are recoverable."""
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:undeclared_rep:{part}")
        ranges = self._contract_ranges()

        def frac(v, lo, hi):
            v = v[~np.isnan(v)]
            return float(((v >= lo - 1e-9) & (v <= hi + 1e-9)).mean()) if len(v) else 1.0

        shards = sorted({s for s in self.shards.values if s.startswith(part + "-")})
        chosen = 0
        for sh in [shards[i] for i in rng.permutation(len(shards))]:
            if chosen >= n_shards:
                break
            cands = []
            for tname in self._cell_tables():
                for f in self.layout[tname]["cols"]:
                    if f in self.spec.numeric and f in ranges and f not in shard_reps.get(tname, {}).get(sh, {}):
                        for r in ("R1", "R2"):
                            cands.append((tname, f, r))
            for j in rng.permutation(len(cands)):
                tname, f, r = cands[j]
                t = tables[tname]
                m = (t["_shard"] == sh).to_numpy()
                x = t.loc[m, f].to_numpy(dtype=float)
                lo, hi = ranges[f]
                opts = self.reps[f]["options"]
                stored = opts[r]["a"] * x + opts[r]["b"]
                others = [o for k2, o in opts.items() if k2 not in ("R0", r)]
                if (m.sum() == 0 or frac(x, lo, hi) < 0.99 or frac(stored, lo, hi) >= 0.5
                        or any(frac((stored - o["b"]) / o["a"], lo, hi) >= 0.5 for o in others)):
                    continue
                t.loc[m, f] = stored
                self.ledger.append({"partition": part, "defect": "undeclared_representation", "table": tname,
                                    "shard": sh, "column": f, "to": r, "denominator": N_SHARDS, "reversible": True})
                chosen += 1
                break
        if chosen < n_shards:
            raise RuntimeError(f"{self.task}/{self.condition}/{part}: only {chosen} of {n_shards} detectable "
                               "undeclared-representation shards could be placed")
        return {"denominator": N_SHARDS, "affected": chosen}

    def plan_content_drift(self, n_shards: int, part: str) -> dict:
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:content_drift:{part}")
        shards = sorted({s for s in self.shards.values if s.startswith(part + "-")})
        names = self._cell_tables()
        for sh in [shards[i] for i in rng.permutation(len(shards))[:n_shards]]:
            tname = names[int(rng.integers(0, len(names)))]
            self.drift.setdefault((tname, part), []).append(sh)
            self.ledger.append({"partition": part, "defect": "content_drift", "table": tname, "shard": sh,
                                "denominator": N_SHARDS, "reversible": True})
        return {"denominator": N_SHARDS, "affected": n_shards}

    def _drifted(self, df: pd.DataFrame, name: str, part: str) -> pd.DataFrame:
        """Primary-file content after drift: numeric features of the drifted shards perturbed independently of labels."""
        out = df.copy()
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:drift_values:{name}:{part}")
        for sh in self.drift.get((name, part), []):
            m = (out["_shard"] == sh).to_numpy()
            for c in [c for c in out.columns if c in self.spec.numeric]:
                v = out[c].to_numpy(dtype=float)
                sd = float(np.nanstd(v)) or 1.0
                v = v.copy()
                v[m] = v[m] + rng.normal(0.0, 0.1 * sd, size=int(m.sum()))
                out[c] = v
        return out

    def semantic_plan(self, part: str) -> list:
        k = SEMANTIC_SHARDS[self.condition]
        rng = make_rng("corruption", self.family, self.task, self.rep, f"{self.condition}:semantic:{part}")
        shards = sorted({s for s in self.shards.values if s.startswith(part + "-")})
        pick = [shards[i] for i in rng.permutation(len(shards))[:k]]
        bti = base_task_index(self.family, self.template) if self.suite == "evaluation" else TEMPLATES.index(self.template)
        plan = []
        for rank, sh in enumerate(pick):
            subtype = "unit" if (bti + self.rep + rank) % 2 == 0 else "stale"
            plan.append((sh, subtype, rng))
        return plan

    # ----- build
    def build(self) -> dict:
        dirs = instance_dirs(self.paths, self.suite, self.family, self.template, self.condition, self.rep)
        for d in dirs.values():
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        kind, rate = CONDITION_SPEC[self.condition]
        tables = self.clean_tables()
        ref_all = reference_features(self.df, self.spec, self.template, self.suite)
        shard_reps = self.apply_representations(tables)
        stale: dict = {}  # (table, shard) -> DataFrame
        realized = {}
        if kind == "semantic":
            for part in PARTS:
                plan = self.semantic_plan(part)
                realized[part] = {"shards": len(plan), "unit": 0, "stale": 0, "denominator": N_SHARDS}
                for sh, subtype, rng in plan:
                    obs_tables = [n for n in self._cell_tables()]
                    tname = obs_tables[int(rng.integers(0, len(obs_tables)))]
                    if subtype == "unit":
                        cand = [c for c in self.layout[tname]["cols"] if c in self.spec.numeric]
                        if not cand:
                            subtype = "stale"
                        else:
                            f = cand[int(rng.integers(0, len(cand)))]
                            cur = shard_reps.get(tname, {}).get(sh, {}).get(f, "R0")
                            choices = [r for r in ["R1", "R2", "R0"] if r != cur][:2]
                            newr = choices[int(rng.integers(0, len(choices)))]
                            shard_reps.setdefault(tname, {}).setdefault(sh, {})[f] = newr
                            self.ledger.append({"partition": part, "defect": "unit_representation", "table": tname,
                                                "shard": sh, "column": f, "from": cur, "to": newr,
                                                "denominator": N_SHARDS, "reversible": True})
                            realized[part]["unit"] += 1
                    if subtype == "stale":
                        stale[(tname, sh)] = None
                        self.ledger.append({"partition": part, "defect": "stale_candidate", "table": tname,
                                            "shard": sh, "denominator": N_SHARDS, "reversible": True})
                        realized[part]["stale"] += 1
        # stored representations
        for tname, sr in shard_reps.items():
            tables[tname] = self._apply_affine(tables[tname], sr, self.reps)
        self.drift = {}
        if self.tier2:
            self.add_ingest_batch(tables)
            for part in PARTS:
                if kind == "near_dup":
                    realized[part] = self.near_duplicates(tables, rate, part)
                elif kind == "key_variant":
                    realized[part] = self.key_variants(tables, rate, part)
                elif kind == "content_drift":
                    realized[part] = self.plan_content_drift(int(rate), part)
                else:
                    realized[part] = self.undeclared_representations(tables, int(rate), part, shard_reps)
        # other snapshots and stale candidates derive from the published (pre-defect) representation
        versions: dict = {}
        for name, t in tables.items():
            grain = self.layout.get(name, {}).get("grain")
            vs = self.versions_for.get(name, self.versions if grain == "observation" else ["v2"])
            versions[name] = {v: _snapshot(t, self.spec, v, self.suite, [c for c in t.columns if c in self.spec.numeric])
                              for v in vs if v != "v2"}
        for (tname, sh) in list(stale):
            rows = tables[tname][tables[tname]["_shard"] == sh]
            stale[(tname, sh)] = _snapshot(rows, self.spec, "v1", self.suite, [c for c in rows.columns if c in self.spec.numeric])
        if kind == "cell":
            for part in PARTS:
                realized[part] = self.corrupt_cells(tables, rate, part)
        if kind == "key":
            for part in PARTS:
                realized[part] = self.corrupt_keys(tables, rate, part)
        # missing cells -> NaN in reference (unknowable originals)
        ref = ref_all.set_index("observation_id")
        for e in self.ledger:
            if e["defect"] == "cell_missing":
                ref.at[e["observation_id"], e["column"]] = np.nan
        ref = ref.reset_index()
        for name, t in tables.items():
            versions[name] = dict(sorted({**versions[name], "v2": t}.items()))
        # write files and catalogs
        catalogs = {}
        for scope, parts, root in [("visible", VISIBLE_PARTS, dirs["visible"]), ("test", ["test"], dirs["private"])]:
            catalogs[scope] = self._write_scope(root, parts, versions, stale, shard_reps)
        # negative controls
        neg = None
        if self.condition in ("N1", "N2"):
            neg = self._apply_negative(catalogs, dirs)
        # references, labels, splits
        lab = self.df[["observation_id", self.spec.target]].rename(columns={self.spec.target: "target"})
        lab = lab.merge(self.split[["observation_id", "partition", "fold"]], on="observation_id")
        lab[lab["partition"].isin(VISIBLE_PARTS)].to_parquet(dirs["trusted"] / "labels.parquet", index=False)
        lab[lab["partition"] == "test"][["observation_id", "target"]].to_parquet(dirs["private"] / "labels_test.parquet", index=False)
        for part in PARTS:
            ids = set(self.split.loc[self.split["partition"] == part, "observation_id"])
            r = ref[ref["observation_id"].isin(ids)].sort_values("observation_id", kind="mergesort").reset_index(drop=True)
            r.to_parquet(dirs["private"] / f"reference_{part}.parquet", index=False)
        with gzip.open(dirs["private"] / "ledger.json.gz", "wt") as f:
            f.write(dumps(self.ledger))
        contract = self.contract(neg)
        write_json(dirs["visible"] / "contract.json", contract)
        (dirs["visible"] / "contract.md").write_text(render_contract(contract))
        vis_manifest = {
            "partitions": {p: sorted(self.split.loc[self.split["partition"] == p, "observation_id"].tolist()) for p in VISIBLE_PARTS},
            "cv_policy": {"rule": self.spec.split_rule, "folds": 3,
                          "description": "Inner folds are fixed and applied by the trusted fit_evaluate service."},
        }
        write_json(dirs["visible"] / "visible_partition_manifest.json", vis_manifest, indent=None)
        meta = {
            "instance": f"{self.suite}/{self.task}/{self.condition}/r{self.rep}",
            "suite": self.suite, "family": self.family, "template": self.template, "condition": self.condition,
            "repetition": self.rep, "spec": self.spec.to_dict(), "required_features": required_features(self.spec, self.template),
            "realized_severity": realized, "declared_severity": rate, "negative": neg,
            "ledger_counts": pd.Series([e["defect"] for e in self.ledger]).value_counts().to_dict() if self.ledger else {},
            "primary_table": self.primary, "generator_version": GENERATOR_VERSION,
        }
        write_json(dirs["private"] / "instance_meta.json", meta)
        meta["hashes"] = {k: _dir_digest(v) for k, v in dirs.items()}
        write_json(dirs["private"] / "instance_meta.json", meta)
        return meta

    def _write_scope(self, root: Path, parts: list, versions: dict, stale: dict, shard_reps: dict) -> dict:
        src = root / "sources"
        src.mkdir(parents=True, exist_ok=True)
        cat_tables, authority = {}, []
        for name, vmap in versions.items():
            meta = self.table_meta(name)
            files = []
            auth_hashes = {}
            cols_meta = None
            for v, t in vmap.items():
                for p in parts:
                    tp = t[t["_partition"] == p].drop(columns=["_partition"]).reset_index(drop=True)
                    if tp.empty:
                        continue
                    fid = f"{name}__{v}__{p}"
                    path = src / f"{fid}.parquet"
                    tp.to_parquet(path, index=False)
                    back = pd.read_parquet(path)
                    sh = {s: df_hash(g.reset_index(drop=True)) for s, g in back.groupby("_shard", sort=True)}
                    replica = self.tier2 and v == "v2" and name in self._cell_tables()
                    if replica and self.drift.get((name, p)):
                        # the primary file's content drifts; its catalog entry keeps declaring the authorised hashes
                        self._drifted(back, name, p).to_parquet(path, index=False)
                        bad = pd.read_parquet(path)
                        for s in self.drift[(name, p)]:
                            assert df_hash(bad[bad["_shard"] == s].reset_index(drop=True)) != sh[s]
                    files.append({"file_id": fid, "table": name, "version": v, "snapshot_date": SNAPSHOTS[v],
                                  "modified": MODIFIED[v], "partition": p, "path": f"sources/{fid}.parquet",
                                  "shards": sorted(sh), "shard_hashes": sh, "rows": int(len(back))})
                    if replica:
                        # every Tier-2 instance has a replica of the authorised content, so its presence reveals nothing
                        rfid = f"{fid}__replica"
                        back.to_parquet(src / f"{rfid}.parquet", index=False)
                        rb = pd.read_parquet(src / f"{rfid}.parquet")
                        rsh = {s: df_hash(g.reset_index(drop=True)) for s, g in rb.groupby("_shard", sort=True)}
                        assert rsh == sh
                        files.append({"file_id": rfid, "table": name, "version": v, "snapshot_date": SNAPSHOTS[v],
                                      "modified": REPLICA_MODIFIED, "partition": p, "path": f"sources/{rfid}.parquet",
                                      "shards": sorted(rsh), "shard_hashes": rsh, "rows": int(len(rb))})
                    if v == "v2":
                        auth_hashes.update(sh)
                    if cols_meta is None:
                        cols_meta = _column_types(back, self.spec)
            for (tname, shard), sdf in stale.items():
                if tname != name or shard.split("-")[0] not in parts:
                    continue
                fid = f"{name}__{shard}__refresh"
                path = src / f"{fid}.parquet"
                sdf.drop(columns=["_partition"]).reset_index(drop=True).to_parquet(path, index=False)
                back = pd.read_parquet(path)
                files.append({"file_id": fid, "table": name, "version": "v1", "snapshot_date": SNAPSHOTS["v1"],
                              "modified": MODIFIED["refresh"], "partition": shard.split("-")[0],
                              "path": f"sources/{fid}.parquet", "shards": [shard],
                              "shard_hashes": {shard: df_hash(back)}, "rows": int(len(back))})
            cat_tables[name] = {**meta, "columns": cols_meta or {}, "files": files,
                                "versions": sorted({f["version"] for f in files})}
            authority.append({"record_id": f"AUTH-{name}", "registry": "data-governance", "table": name,
                              "as_of": AS_OF, "version": "v2", "shard_hashes": auth_hashes})
        relationships = []
        if self.template == "T2":
            relationships.append({"left": "block_a", "right": "block_b", "keys": ["observation_id"], "cardinality": "one_to_one"})
        if self.template == "T3":
            relationships += [{"left": "observations", "right": "measurements_b", "keys": ["observation_id"], "cardinality": "one_to_one"},
                              {"left": "observations", "right": "profiles", "keys": ["profile_key"], "cardinality": "many_to_one"}]
        if self.template == "T6":
            relationships.append({"left": "observations", "right": "readings", "keys": ["observation_id"], "cardinality": "one_to_many"})
        sr = {t: {s: m for s, m in v.items() if s.split("-")[0] in parts} for t, v in shard_reps.items()}
        catalog = {
            "instance": f"{self.suite}/{self.task}/{self.condition}/r{self.rep}",
            "partitions": parts,
            "tables": cat_tables,
            "authority": authority,
            "authority_policy": "Each authority record lists the version and per-shard SHA-256 content hashes that are authorised for the stated as-of date.",
            "representations": {f: v for f, v in self.reps.items()},
            "shard_representations": sr,
            "relationships": relationships,
            "alias_table": "key_aliases",
            "numeric_format": "Numeric cells may be stored as numbers or strings: a plain decimal literal or 'value:<decimal literal>'. Null means missing.",
        }
        if self.tier2:
            catalog["value_ranges"] = self._contract_ranges()
            catalog["packaging_columns"] = list(PACKAGING_COLUMNS)
        write_json(root / "catalog.json", catalog)
        return catalog

    def _apply_negative(self, catalogs: dict, dirs: dict) -> dict:
        name = self.primary
        for scope, root in [("visible", dirs["visible"]), ("test", dirs["private"])]:
            cat = catalogs[scope]
            t = cat["tables"][name]
            if self.condition == "N1":
                for f in [f for f in t["files"] if f["version"] == "v2"]:
                    (root / f["path"]).unlink(missing_ok=True)
                t["files"] = [f for f in t["files"] if f["version"] != "v2"]
                t["versions"] = sorted({f["version"] for f in t["files"]})
            else:
                v3 = {}
                for f in t["files"]:
                    if f["version"] == "v3":
                        v3.update(f["shard_hashes"])
                cat["authority"].append({"record_id": f"AUTH-{name}-plant", "registry": "plant-registry", "table": name,
                                         "as_of": AS_OF, "version": "v3", "shard_hashes": v3})
            write_json(root / "catalog.json", cat)
        reason = "REQUIRED_SOURCE_MISSING" if self.condition == "N1" else "AMBIGUOUS_AUTHORITY"
        return {"condition": self.condition, "table": name, "expected_reason": reason}

    def _contract_ranges(self) -> dict:
        """Plausible canonical value ranges published in the contract (training partition, padded by 25% of span)."""
        req = required_features(self.spec, self.template)
        train = self.df[self.df["observation_id"].map(self.part_of) == "train"]
        ranges = _ranges(train, [f for f in self.spec.numeric])
        if self.template == "T6":
            r = reference_features(train, self.spec, "T6", self.suite)
            ranges = {k: v for k, v in ranges.items() if k in req}
            ranges.update(_ranges(r, [c for c in req if c.endswith(("_mean", "_std"))]))
            for s in self.spec.numeric[:2]:
                ranges[f"{s}_count"] = [READINGS_PER_SERIES, READINGS_PER_SERIES]
        return {k: [round(v[0], 6), round(v[1], 6)] for k, v in ranges.items()}

    def contract(self, neg) -> dict:
        req = required_features(self.spec, self.template)
        cat = [f for f in self.spec.categorical]
        num = [f for f in req if f not in cat]
        layout = self.layout
        joins = []
        if self.template == "T2":
            joins = [{"left": "block_a", "right": "block_b", "keys": ["observation_id"], "required_cardinality": "one_to_one"}]
        if self.template == "T3":
            joins = [{"left": "observations", "right": "measurements_b", "keys": ["observation_id"], "required_cardinality": "one_to_one"},
                     {"left": "observations", "right": "profiles", "keys": ["profile_key"], "required_cardinality": "many_to_one"}]
        aggregates = []
        if self.template == "T6":
            sel = layout["readings"]["series"]
            aggregates = [{"child_table": "readings", "key": "observation_id", "series_column": "series",
                           "value_column": "value", "series": sel, "stats": ["mean", "pop_std", "count"],
                           "output_columns": {s: [f"{s}_mean", f"{s}_std", f"{s}_count"] for s in sel},
                           "readings_per_series": READINGS_PER_SERIES,
                           "note": "std is the population standard deviation (ddof=0); join aggregates to observations one-to-one."}]
        ranges = self._contract_ranges()
        sizes = self.split[self.split["partition"].isin(VISIBLE_PARTS)]["partition"].value_counts().to_dict()
        from .modeling import candidate_ids
        return {
            "task_id": self.task,
            "instance_id": f"{self.suite}/{self.task}/{self.condition}/r{self.rep}",
            "template": self.template,
            "template_description": TEMPLATE_DESCRIPTIONS[self.template],
            "objective": f"Build a leakage-free feature table for every observation and select the best permitted model "
                         f"for predicting '{self.spec.target}' ({self.spec.task_type}).",
            "task_type": self.spec.task_type,
            "target": self.spec.target,
            "target_access": "Labels are held by the trusted fit_evaluate service; they are not a source table.",
            "prediction_key": "observation_id",
            "feature_grain": "observation",
            "selection_metric": self.spec.selection_metric,
            "required_features": req,
            "numeric_features": num,
            "categorical_features": cat,
            "excluded_predictors": list(self.spec.excluded) + ["observation_id", "profile_key", "_shard"]
                                   + (["_ingest_batch"] if self.tier2 else []),
            "source_versions": {"rule": "Use, for every table and shard, the content authorised by the catalog authority "
                                        f"record for as-of date {AS_OF}. File names and modification times do not establish authority.",
                                "as_of": AS_OF},
            "keys": {"canonical_key": "observation_id", "alias_table": "key_aliases",
                     "rule": "Some records may carry a permitted alias instead of the canonical observation_id; map aliases through key_aliases."},
            "duplicates": "Exact duplicate records are packaging errors. Each observation must appear exactly once in the output.",
            "joins": joins,
            "aggregates": aggregates,
            "units": "All numeric features must be in canonical units. Shard-level stored representations are declared in "
                     "catalog.shard_representations with stored = a*canonical + b.",
            "numeric_format": "Numeric cells may be numbers, plain decimal strings, or 'value:<decimal>' strings; null means missing.",
            "value_ranges": ranges,
            "missing_numeric_policy": "Keep rows with missing values; the shared pipeline applies training-fitted median imputation (zero if a column is entirely missing).",
            "visible_partition_sizes": {k: int(v) for k, v in sizes.items()},
            "final_refit_partitions": ["train", "validation"],
            "candidate_models": candidate_ids(self.spec.task_type),
            "abstention_reasons": ["REQUIRED_SOURCE_MISSING", "AMBIGUOUS_AUTHORITY", "CONTRACT_UNSATISFIABLE", "BUDGET_INSUFFICIENT"],
            "output": {"submission": "submit(handle, candidate) freezes the transform graph and the selected candidate",
                       "abstain": "abstain(reason, detail) when the contract cannot be satisfied"},
        }


def _column_types(df: pd.DataFrame, spec: FamilySpec) -> dict:
    out = {}
    for c in df.columns:
        if c == "_shard":
            out[c] = "string (packaging shard)"
        elif c == "_ingest_batch":
            out[c] = "string (packaging batch)"
        elif pd.api.types.is_numeric_dtype(df[c]):
            out[c] = "numeric"
        else:
            out[c] = "string"
    return out


def _dir_digest(root: Path) -> str:
    """Content digest: parquet files are hashed by their decoded table content so that writer
    metadata (library version strings) does not change the digest."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        h.update(p.relative_to(root).as_posix().encode())
        if p.suffix == ".parquet":
            h.update(df_hash(pd.read_parquet(p)).encode())
        elif p.name == "instance_meta.json":
            continue
        elif p.suffix == ".gz":
            with gzip.open(p, "rb") as f:
                h.update(hashlib.sha256(f.read()).hexdigest().encode())
        else:
            h.update(sha256_file(p).encode())
    return h.hexdigest()


def render_contract(c: dict) -> str:
    """Fixed natural-language rendering of the machine-readable contract."""
    lines = [f"# Task {c['task_id']} ({c['instance_id']})", "", c["objective"], "", c["template_description"], "",
             f"- Target: {c['target']} ({c['task_type']}); {c['target_access']}",
             f"- Selection metric: {c['selection_metric']} on the validation partition.",
             f"- Output grain: one row per observation_id. Visible partition sizes: {c['visible_partition_sizes']}.",
             f"- Required features (exact names): {', '.join(c['required_features'])}",
             f"- Categorical features: {', '.join(c['categorical_features']) or 'none'}",
             f"- Excluded predictors (never use as features): {', '.join(c['excluded_predictors'])}",
             f"- Source versions: {c['source_versions']['rule']}",
             f"- Keys: {c['keys']['rule']}",
             f"- Duplicates: {c['duplicates']}",
             f"- Units: {c['units']}",
             f"- Numeric format: {c['numeric_format']}",
             f"- Missing values: {c['missing_numeric_policy']}"]
    for j in c["joins"]:
        lines.append(f"- Join {j['left']} to {j['right']} on {j['keys']} ({j['required_cardinality']}).")
    for a in c["aggregates"]:
        lines.append(f"- Aggregate {a['child_table']}.{a['value_column']} by {a['key']} and {a['series_column']} for series "
                     f"{a['series']} with stats {a['stats']} -> columns {a['output_columns']}. {a['note']}")
    lines.append(f"- Candidate models: {', '.join(c['candidate_models'])} (at most six evaluations).")
    lines.append(f"- If the contract cannot be satisfied, abstain with one of: {', '.join(c['abstention_reasons'])}.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- suite helpers
def build_instance(paths: Paths, suite: str, family: str, template: str, condition: str, rep: int) -> dict:
    return InstanceBuilder(paths, suite, family, template, condition, rep).build()


def instance_record_path(paths: Paths) -> Path:
    return paths.manifests / "instances.json"


def ensure_instance(paths: Paths, suite: str, family: str, template: str, condition: str, rep: int) -> dict:
    """Build an instance if absent in this session's cache (no manifest side effects)."""
    dirs = instance_dirs(paths, suite, family, template, condition, rep)
    meta_path = dirs["private"] / "instance_meta.json"
    if meta_path.exists() and (dirs["visible"] / "catalog.json").exists():
        meta = read_json(meta_path)
        if "hashes" in meta and meta.get("generator_version", 1) == GENERATOR_VERSION:
            return meta
    return build_instance(paths, suite, family, template, condition, rep)


def ensure_instances(paths: Paths, keys: list, workers: int = 1, log=print) -> dict:
    """Build (in parallel) and verify a list of (suite, family, template, condition, rep) instances.
    The first build records the content digest; every later build must reproduce it exactly."""
    from concurrent.futures import ProcessPoolExecutor
    keys = sorted(set(tuple(k) for k in keys))
    metas = {}
    if workers > 1 and len(keys) > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {k: ex.submit(ensure_instance, paths, *k) for k in keys}
            for k, f in futs.items():
                metas[k] = f.result()
    else:
        for k in keys:
            metas[k] = ensure_instance(paths, *k)
    rec_path = instance_record_path(paths)
    recs = read_json(rec_path) if rec_path.exists() else {}
    changed = False
    for k, meta in metas.items():
        key = f"{k[0]}/{k[1]}-{k[2]}/{k[3]}/r{k[4]}"
        if key in recs:
            if recs[key] != meta["hashes"]:
                raise RuntimeError(f"instance {key} does not reproduce its recorded content digest; "
                                   "the generator, raw data or library versions changed")
        else:
            recs[key] = meta["hashes"]
            changed = True
    if changed:
        write_json(rec_path, recs)
    return metas
