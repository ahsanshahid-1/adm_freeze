"""Dataset acquisition, canonical import (D1-D4), synthetic generators (D5-D6), and splits."""
from __future__ import annotations

import io
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .core import (Paths, make_rng, now_iso, read_json, sha256_file, write_json, df_hash, small_seed,
                   derive_seed)

# --------------------------------------------------------------------------- sources
UCI_SOURCES = {
    "D1": {"uci_id": 601, "name": "AI4I 2020 Predictive Maintenance Dataset",
           "url": "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip",
           "page": "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset",
           "doi": "10.24432/C5HS5C", "citation": "Matzka, S. (2020). AI4I 2020 Predictive Maintenance Dataset. UCI Machine Learning Repository."},
    "D2": {"uci_id": 198, "name": "Steel Plates Faults",
           "url": "https://archive.ics.uci.edu/static/public/198/steel+plates+faults.zip",
           "page": "https://archive.ics.uci.edu/dataset/198/steel+plates+faults",
           "doi": "10.24432/C5J88N", "citation": "Buscema, M., Terzi, S., & Tastle, W. (2010). Steel Plates Faults. UCI Machine Learning Repository."},
    "D3": {"uci_id": 165, "name": "Concrete Compressive Strength",
           "url": "https://archive.ics.uci.edu/static/public/165/concrete+compressive+strength.zip",
           "page": "https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength",
           "doi": "10.24432/C5PK67", "citation": "Yeh, I.-C. (1998). Concrete Compressive Strength. UCI Machine Learning Repository."},
    "D4": {"uci_id": 242, "name": "Energy Efficiency",
           "url": "https://archive.ics.uci.edu/static/public/242/energy+efficiency.zip",
           "page": "https://archive.ics.uci.edu/dataset/242/energy+efficiency",
           "doi": "10.24432/C51307", "citation": "Tsanas, A. & Xifara, A. (2012). Energy Efficiency. UCI Machine Learning Repository."},
}
LICENSE = "CC BY 4.0"

STEEL_LABELS = ["Pastry", "Z_Scratch", "K_Scatch", "Stains", "Dirtiness", "Bumps", "Other_Faults"]


@dataclass
class FamilySpec:
    family: str
    name: str
    task_type: str                 # binary | multiclass | regression
    target: str
    features: list                 # ordered permitted predictors
    categorical: list
    excluded: list                 # columns present in source records but not permitted as predictors
    group_col: str | None          # internal grouping column (never shown as such)
    split_rule: str
    selection_metric: str
    classes: list = field(default_factory=list)
    synthetic: bool = False
    notes: str = ""

    @property
    def numeric(self) -> list:
        return [f for f in self.features if f not in self.categorical]

    def to_dict(self) -> dict:
        return asdict(self)


def _snake(s: str) -> str:
    out = []
    for ch in s.strip():
        out.append(ch.lower() if ch.isalnum() else "_")
    t = "".join(out)
    while "__" in t:
        t = t.replace("__", "_")
    return t.strip("_")


# --------------------------------------------------------------------------- acquisition
def _download(url: str, dest: Path, retries: int = 4) -> None:
    last = None
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "adm-research/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            dest.write_bytes(data)
            return
        except Exception as e:  # pragma: no cover - network
            last = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"download failed for {url}: {last}")


def acquire(paths: Paths, local_source_dir: str | Path | None = None) -> dict:
    """Download (or reuse) original archives, never modifying them; record checksums."""
    paths.raw.mkdir(parents=True, exist_ok=True)
    manifest_path = paths.manifests / "datasets.json"
    previous = read_json(manifest_path) if manifest_path.exists() else {}
    manifest = {}
    for fam, src in UCI_SOURCES.items():
        dest = paths.raw / f"uci_{src['uci_id']}.zip"
        if not dest.exists():
            if local_source_dir and (Path(local_source_dir) / f"{src['uci_id']}.zip").exists():
                dest.write_bytes((Path(local_source_dir) / f"{src['uci_id']}.zip").read_bytes())
            else:
                _download(src["url"], dest)
        digest = sha256_file(dest)
        prev = previous.get(fam, {})
        if prev.get("sha256") and prev["sha256"] != digest:
            raise RuntimeError(f"{fam}: raw archive checksum changed ({prev['sha256']} -> {digest}). "
                               "The frozen protocol requires the original archive.")
        manifest[fam] = {
            **src, "license": LICENSE, "archive": dest.name, "sha256": digest,
            "retrieved": prev.get("retrieved", now_iso()), "bytes": dest.stat().st_size,
        }
    write_json(manifest_path, manifest)
    return manifest


def _zip_member(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as z:
        return z.read(name)


# --------------------------------------------------------------------------- canonical import
def import_d1(raw: Path) -> tuple[pd.DataFrame, FamilySpec, dict]:
    df = pd.read_csv(io.BytesIO(_zip_member(raw / "uci_601.zip", "ai4i2020.csv")))
    mapping = {"UDI": "uid", "Product ID": "product_id", "Type": "type",
               "Air temperature [K]": "air_temperature_k", "Process temperature [K]": "process_temperature_k",
               "Rotational speed [rpm]": "rotational_speed_rpm", "Torque [Nm]": "torque_nm",
               "Tool wear [min]": "tool_wear_min", "Machine failure": "machine_failure",
               "TWF": "twf", "HDF": "hdf", "PWF": "pwf", "OSF": "osf", "RNF": "rnf"}
    assert list(df.columns) == list(mapping), f"D1 columns differ from documentation: {list(df.columns)}"
    assert len(df) == 10000, f"D1 expected 10000 rows, got {len(df)}"
    df = df.rename(columns=mapping)
    df["type"] = df["type"].astype(str)
    for c in ["air_temperature_k", "process_temperature_k", "rotational_speed_rpm", "torque_nm", "tool_wear_min"]:
        df[c] = df[c].astype(float)
    df["machine_failure"] = df["machine_failure"].astype(int)
    df.insert(0, "observation_id", [f"D1-{i:06d}" for i in range(len(df))])
    df["_group"] = np.arange(len(df))
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D1", "AI4I 2020", "binary", "machine_failure",
                      ["type", "air_temperature_k", "process_temperature_k", "rotational_speed_rpm", "torque_nm", "tool_wear_min"],
                      ["type"], ["uid", "product_id", "twf", "hdf", "pwf", "osf", "rnf"], None, "temporal",
                      "average_precision", [0, 1],
                      notes="The identifier column is UDI in the archive (the protocol text says UID); mapped to uid and excluded.")
    return df, spec, mapping


def import_d2(raw: Path) -> tuple[pd.DataFrame, FamilySpec, dict]:
    names = _zip_member(raw / "uci_198.zip", "Faults27x7_var").decode().split()
    data = pd.read_csv(io.BytesIO(_zip_member(raw / "uci_198.zip", "Faults.NNA")), sep=r"\s+", header=None)
    assert len(names) == 34 and data.shape == (1941, 34), f"D2 shape {data.shape}, {len(names)} names"
    data.columns = names
    labels = names[27:]
    assert labels == STEEL_LABELS, f"D2 label names differ: {labels}"
    active = data[labels].sum(axis=1)
    assert (active == 1).all(), "D2: every row must have exactly one active target indicator"
    mapping = {n: _snake(n) for n in names}
    df = data.rename(columns=mapping)
    lab_cols = [mapping[l] for l in labels]
    df["fault_class"] = [labels[i] for i in np.argmax(df[lab_cols].to_numpy(), axis=1)]
    feats = [mapping[n] for n in names[:27]]
    for c in feats:
        df[c] = df[c].astype(float)
    df.insert(0, "observation_id", [f"D2-{i:06d}" for i in range(len(df))])
    # group identical predictor rows
    key = df[feats].round(10).astype(str).agg("|".join, axis=1)
    df["_group"] = pd.factorize(key)[0]
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D2", "Steel Plates Faults", "multiclass", "fault_class", feats, [], lab_cols, "_group",
                      "stratified_group", "macro_f1", list(STEEL_LABELS))
    mapping["__label_mapping__"] = {l: l for l in labels}
    return df, spec, mapping


def import_d3(raw: Path) -> tuple[pd.DataFrame, FamilySpec, dict]:
    data = pd.read_excel(io.BytesIO(_zip_member(raw / "uci_165.zip", "Concrete_Data.xls")))
    assert data.shape == (1030, 9), f"D3 shape {data.shape}"
    canon = ["cement_kg_m3", "blast_furnace_slag_kg_m3", "fly_ash_kg_m3", "water_kg_m3", "superplasticizer_kg_m3",
             "coarse_aggregate_kg_m3", "fine_aggregate_kg_m3", "age_day", "compressive_strength_mpa"]
    expected_tokens = ["Cement", "Blast Furnace Slag", "Fly Ash", "Water", "Superplasticizer", "Coarse Aggregate",
                       "Fine Aggregate", "Age", "compressive strength"]
    for col, tok in zip(data.columns, expected_tokens):
        assert tok.lower() in str(col).lower(), f"D3 column mapping mismatch: {col!r} vs {tok!r}"
    mapping = {str(c): n for c, n in zip(data.columns, canon)}
    df = data.copy()
    df.columns = canon
    df = df.astype(float)
    df.insert(0, "observation_id", [f"D3-{i:06d}" for i in range(len(df))])
    comp = df[canon[:7]].round(6).astype(str).agg("|".join, axis=1)
    df["_group"] = pd.factorize(comp)[0]
    df["mix_id"] = [f"MIX-{g:04d}" for g in df["_group"]]
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D3", "Concrete Compressive Strength", "regression", "compressive_strength_mpa", canon[:8], [],
                      ["mix_id"], "_group", "group", "rmse")
    return df, spec, mapping


def import_d4(raw: Path) -> tuple[pd.DataFrame, FamilySpec, dict]:
    data = pd.read_excel(io.BytesIO(_zip_member(raw / "uci_242.zip", "ENB2012_data.xlsx")))
    data = data.dropna(how="all").dropna(axis=1, how="all")
    assert list(data.columns)[:10] == ["X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "Y1", "Y2"], list(data.columns)
    assert len(data) == 768, f"D4 expected 768 rows, got {len(data)}"
    names = ["relative_compactness", "surface_area", "wall_area", "roof_area", "overall_height", "orientation",
             "glazing_area", "glazing_area_distribution", "heating_load", "cooling_load"]
    mapping = dict(zip(["X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "Y1", "Y2"], names))
    df = data[list(mapping)].rename(columns=mapping).astype(float)
    df.insert(0, "observation_id", [f"D4-{i:06d}" for i in range(len(df))])
    geo = df[names[:5]].round(6).astype(str).agg("|".join, axis=1)
    df["_group"] = pd.factorize(geo)[0]
    assert df["_group"].nunique() == 12, f"D4 expected 12 base geometries (X1-X5), got {df['_group'].nunique()}"
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D4", "Energy Efficiency", "regression", "heating_load", names[:8], [], ["cooling_load"], "_group",
                      "geometry_groups", "rmse")
    return df, spec, mapping


# --------------------------------------------------------------------------- synthetic generators
def generate_d5(n_machines: int = 500, per_machine: int = 20, namespace: str = "evaluation", prefix: str = "D5"):
    """SYN-MACHINE-v1 (Section 5.2)."""
    rng = make_rng(namespace, "D5", "generator", "", "SYN-MACHINE-v1")
    b = rng.standard_normal((n_machines, 6))
    cat = rng.choice(np.array(["A", "B", "C"]), size=n_machines)
    eps = rng.standard_normal((n_machines, per_machine, 6))
    z = 0.4 * b[:, None, :] + np.sqrt(0.84) * eps
    eta = (-2.5 + 0.9 * z[..., 0] + 0.7 * z[..., 1] + 0.5 * z[..., 0] * z[..., 2]
           + 0.6 * (cat == "C")[:, None].astype(float))
    p = 1.0 / (1.0 + np.exp(-eta))
    y = (rng.random((n_machines, per_machine)) < p).astype(int)
    mids = [f"{prefix}M-{m:04d}" for m in range(n_machines)]
    machines = pd.DataFrame({"machine_id": mids, "machine_category": cat})
    rows = []
    for m in range(n_machines):
        for i in range(per_machine):
            rows.append((m, i))
    mi = np.array(rows)
    obs = pd.DataFrame({
        "observation_id": [f"{prefix}-{k:06d}" for k in range(len(mi))],
        "machine_id": [mids[m] for m in mi[:, 0]],
        **{f"sensor_{j + 1}": z[mi[:, 0], mi[:, 1], j] for j in range(6)},
        "failure": y[mi[:, 0], mi[:, 1]],
    })
    diag = pd.DataFrame({"observation_id": obs["observation_id"], "p_true": p[mi[:, 0], mi[:, 1]]})
    for j in range(6):
        diag[f"latent_b{j + 1}"] = b[mi[:, 0], j]
    df = obs.merge(machines, on="machine_id", how="left", validate="many_to_one")
    df["_group"] = mi[:, 0]
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D5", "SYN-MACHINE-v1", "binary", "failure",
                      [f"sensor_{j}" for j in range(1, 7)] + ["machine_category"], ["machine_category"],
                      ["machine_id"], "_group", "stratified_group", "average_precision", [0, 1], synthetic=True)
    return df, spec, {"machines": machines, "observations": obs, "diagnostics": diag}


def generate_d6(n_batches: int = 300, per_batch: int = 30, namespace: str = "evaluation", prefix: str = "D6"):
    """SYN-PROCESS-v1 (Section 5.3)."""
    rng = make_rng(namespace, "D6", "generator", "", "SYN-PROCESS-v1")
    u = rng.standard_normal(n_batches)
    x = rng.uniform(-1, 1, (n_batches, per_batch, 8)) + 0.2 * u[:, None, None]
    eps = rng.standard_normal((n_batches, per_batch))
    y = (50 + 10 * x[..., 0] - 7 * x[..., 1] + 5 * x[..., 2] * x[..., 3] + 4 * np.sin(np.pi * x[..., 4])
         + 2 * u[:, None] + eps)
    bids = [f"{prefix}B-{b:04d}" for b in range(n_batches)]
    batches = pd.DataFrame({"batch_id": bids, "line": [f"L{(b % 3) + 1}" for b in range(n_batches)]})
    bi = np.array([(b, i) for b in range(n_batches) for i in range(per_batch)])
    obs = pd.DataFrame({
        "observation_id": [f"{prefix}-{k:06d}" for k in range(len(bi))],
        "batch_id": [bids[b] for b in bi[:, 0]],
        **{f"x{j + 1}": x[bi[:, 0], bi[:, 1], j] for j in range(8)},
        "process_output": y[bi[:, 0], bi[:, 1]],
    })
    diag = pd.DataFrame({"observation_id": obs["observation_id"], "latent_u": u[bi[:, 0]]})
    df = obs.copy()
    df["_group"] = bi[:, 0]
    df["_order"] = np.arange(len(df))
    spec = FamilySpec("D6", "SYN-PROCESS-v1", "regression", "process_output", [f"x{j}" for j in range(1, 9)], [],
                      ["batch_id"], "_group", "group", "rmse", synthetic=True)
    return df, spec, {"batches": batches, "observations": obs, "diagnostics": diag}


DEV_SIZES = {"D5": (100, 20), "D6": (60, 30)}


def build_canonical(paths: Paths, include_public: bool = True) -> dict:
    """Write canonical tables + specs for the evaluation suite and the development suite."""
    out = {}
    imp = {"D1": import_d1, "D2": import_d2, "D3": import_d3, "D4": import_d4}
    mappings = {}
    for fam in (["D1", "D2", "D3", "D4"] if include_public else []):
        df, spec, mapping = imp[fam](paths.raw)
        mappings[fam] = mapping
        out[("evaluation", fam)] = (df, spec)
    for suite, ns in [("evaluation", "evaluation"), ("development", "development")]:
        n5 = (500, 20) if suite == "evaluation" else DEV_SIZES["D5"]
        n6 = (300, 30) if suite == "evaluation" else DEV_SIZES["D6"]
        p5 = "D5" if suite == "evaluation" else "D5X"
        p6 = "D6" if suite == "evaluation" else "D6X"
        df5, s5, parts5 = generate_d5(*n5, namespace=ns, prefix=p5)
        df6, s6, parts6 = generate_d6(*n6, namespace=ns, prefix=p6)
        out[(suite, "D5")] = (df5, s5)
        out[(suite, "D6")] = (df6, s6)
        d = paths.canonical / suite
        d.mkdir(parents=True, exist_ok=True)
        parts5["machines"].to_parquet(d / "D5_machines.parquet", index=False)
        parts5["diagnostics"].to_parquet(d / "D5_diagnostics.parquet", index=False)
        parts6["batches"].to_parquet(d / "D6_batches.parquet", index=False)
        parts6["diagnostics"].to_parquet(d / "D6_diagnostics.parquet", index=False)
    summary = {}
    for (suite, fam), (df, spec) in out.items():
        d = paths.canonical / suite
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / f"{fam}.parquet", index=False)
        write_json(d / f"{fam}_spec.json", spec.to_dict())
        info = {"rows": len(df), "groups": int(df["_group"].nunique()), "hash": df_hash(df),
                "features": len(spec.features), "task_type": spec.task_type}
        if spec.task_type != "regression":
            vc = df[spec.target].value_counts().sort_index()
            info["class_counts"] = {str(k): int(v) for k, v in vc.items()}
        summary[f"{suite}/{fam}"] = info
    write_json(paths.canonical / "column_mappings.json", {k: {kk: vv for kk, vv in v.items()} for k, v in mappings.items()})
    # Development and evaluation must not share observation IDs
    for fam in ["D5", "D6"]:
        ev = set(out[("evaluation", fam)][0]["observation_id"])
        dv = set(out[("development", fam)][0]["observation_id"])
        assert not (ev & dv), f"{fam}: development and evaluation share observation IDs"
    write_json(paths.manifests / "canonical.json", summary)
    return summary


def load_canonical(paths: Paths, suite: str, family: str) -> tuple[pd.DataFrame, FamilySpec]:
    d = paths.canonical / suite
    df = pd.read_parquet(d / f"{family}.parquet")
    spec = FamilySpec(**read_json(d / f"{family}_spec.json"))
    return df, spec


# --------------------------------------------------------------------------- splits
def _assign_groups(groups: np.ndarray, fractions, rng) -> dict:
    """Assign whole groups to partitions approximating the target fractions of rows."""
    uniq, counts = np.unique(groups, return_counts=True)
    order = rng.permutation(len(uniq))
    total = counts.sum()
    targets = np.cumsum(np.array(fractions)) * total
    assign = {}
    acc = 0
    names = ["train", "validation", "test"]
    for idx in order:
        acc_mid = acc + counts[idx] / 2.0
        part = int(np.searchsorted(targets, acc_mid, side="right"))
        part = min(part, 2)
        assign[uniq[idx]] = names[part]
        acc += counts[idx]
    return assign


def _stratified_group_assign(y: np.ndarray, groups: np.ndarray, rng, fractions=(0.6, 0.2, 0.2)) -> np.ndarray:
    """Stratified group-aware 60/20/20: greedy assignment of shuffled groups to the partition with
    the largest deficit for the group's dominant class."""
    names = np.array(["train", "validation", "test"])
    classes = np.unique(y)
    gdf = pd.DataFrame({"g": groups, "y": y})
    gcounts = gdf.groupby(["g", "y"]).size().unstack(fill_value=0).reindex(columns=classes, fill_value=0)
    totals = gcounts.sum(axis=0).to_numpy().astype(float)
    target = np.outer(np.array(fractions), totals)  # partitions x classes
    have = np.zeros_like(target)
    order = rng.permutation(len(gcounts))
    # largest groups first improves balance
    sizes = gcounts.sum(axis=1).to_numpy()
    order = order[np.argsort(-sizes[order], kind="stable")]
    assign = {}
    for i in order:
        c = gcounts.iloc[i].to_numpy().astype(float)
        deficit = ((target - have) * (c[None, :] > 0)).sum(axis=1) / np.maximum(c.sum(), 1)
        p = int(np.argmax(deficit))
        have[p] += c
        assign[gcounts.index[i]] = names[p]
    return np.array([assign[g] for g in groups])


def make_splits(df: pd.DataFrame, spec: FamilySpec, suite: str, repetition: int) -> pd.DataFrame:
    """Return a frame (observation_id, partition, fold) for one repetition (Section 8.1)."""
    fam = spec.family
    rng = make_rng("split", fam, suite, repetition, "outer")
    n = len(df)
    ids = df["observation_id"].to_numpy()
    groups = df["_group"].to_numpy()
    if spec.split_rule == "temporal":
        # fixed across repetitions: original order 60/20/20, forward-chaining folds
        order = df["_order"].to_numpy()
        part = np.where(order < int(0.6 * n), "train", np.where(order < int(0.8 * n), "validation", "test"))
        fold = np.full(n, -1)
        tr = order < int(0.6 * n)
        tr_order = order[tr]
        fold[tr] = np.minimum((tr_order * 4) // int(0.6 * n), 3)  # chunks 0..3
    elif spec.split_rule == "geometry_groups":
        uniq = np.unique(groups)
        assert len(uniq) == 12
        perm = rng.permutation(uniq)
        gpart = {g: ("train" if i < 7 else "validation" if i < 9 else "test") for i, g in enumerate(perm)}
        part = np.array([gpart[g] for g in groups])
        fold = np.full(n, -1)
        trg = perm[:7]
        frng = make_rng("split", fam, suite, repetition, "folds")
        trg = frng.permutation(trg)
        gfold = {g: i % 3 for i, g in enumerate(trg)}
        for i in range(n):
            if part[i] == "train":
                fold[i] = gfold[groups[i]]
    else:
        y = df[spec.target].to_numpy()
        if spec.split_rule == "stratified_group":
            part = _stratified_group_assign(y, groups, rng)
        else:
            assign = _assign_groups(groups, (0.6, 0.2, 0.2), rng)
            part = np.array([assign[g] for g in groups])
        fold = np.full(n, -1)
        tr = part == "train"
        frng = make_rng("split", fam, suite, repetition, "folds")
        if spec.task_type != "regression":
            from sklearn.model_selection import StratifiedGroupKFold
            sgk = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=small_seed(int(frng.integers(0, 2**31 - 1))))
            tr_idx = np.where(tr)[0]
            for k, (_, te) in enumerate(sgk.split(np.zeros(len(tr_idx)), y[tr_idx], groups[tr_idx])):
                fold[tr_idx[te]] = k
        else:
            tg = np.unique(groups[tr])
            tg = frng.permutation(tg)
            gfold = {g: i % 3 for i, g in enumerate(tg)}
            for i in np.where(tr)[0]:
                fold[i] = gfold[groups[i]]
    return pd.DataFrame({"observation_id": ids, "partition": part, "fold": fold.astype(int), "group": groups})


def cv_splits(split_df: pd.DataFrame, rule: str) -> list:
    """List of (train_ids, valid_ids) for the three inner folds of the training partition."""
    tr = split_df[split_df["partition"] == "train"]
    out = []
    if rule == "temporal":
        for k in range(3):
            out.append((tr.loc[tr["fold"] <= k, "observation_id"].tolist(), tr.loc[tr["fold"] == k + 1, "observation_id"].tolist()))
    else:
        for k in range(3):
            out.append((tr.loc[tr["fold"] != k, "observation_id"].tolist(), tr.loc[tr["fold"] == k, "observation_id"].tolist()))
    return out


def check_split(df: pd.DataFrame, spec: FamilySpec, split_df: pd.DataFrame) -> dict:
    """Feasibility assertions (Section 8.1). Raises on failure."""
    assert len(split_df) == len(df) and set(split_df["observation_id"]) == set(df["observation_id"])
    g = split_df.groupby("group")["partition"].nunique()
    if spec.split_rule != "temporal":
        assert (g == 1).all(), f"{spec.family}: a group spans more than one partition"
    counts = split_df["partition"].value_counts().to_dict()
    for p in ["train", "validation", "test"]:
        assert counts.get(p, 0) > 0, f"{spec.family}: empty partition {p}"
    info = {"sizes": {k: int(v) for k, v in counts.items()}}
    if spec.task_type != "regression":
        m = df[["observation_id", spec.target]].merge(split_df, on="observation_id")
        for p in ["train", "validation", "test"]:
            present = set(m.loc[m["partition"] == p, spec.target])
            assert present == set(spec.classes) or set(map(str, present)) == set(map(str, spec.classes)), \
                f"{spec.family}: partition {p} lacks classes {set(spec.classes) - present}"
        for k, (a, b) in enumerate(cv_splits(split_df, spec.split_rule)):
            ya = set(m.set_index("observation_id").loc[a, spec.target])
            yb = set(m.set_index("observation_id").loc[b, spec.target])
            assert len(ya) == len(spec.classes), f"{spec.family}: fold {k} training lacks a class"
            assert len(yb) >= 2, f"{spec.family}: fold {k} validation has fewer than two classes"
        info["positives"] = {p: int(((m["partition"] == p) & (m[spec.target] == 1)).sum()) for p in ["train", "validation", "test"]} \
            if spec.task_type == "binary" else None
    if spec.split_rule == "geometry_groups":
        ng = split_df.groupby("partition")["group"].nunique().to_dict()
        assert ng == {"train": 7, "validation": 2, "test": 3}, f"D4 geometry assignment {ng}"
        info["groups"] = ng
    return info


def build_splits(paths: Paths, suite: str, families: list, repetitions: list) -> dict:
    summary = {}
    for fam in families:
        df, spec = load_canonical(paths, suite, fam)
        for r in repetitions:
            s = make_splits(df, spec, suite, r)
            info = check_split(df, spec, s)
            d = paths.canonical / suite / "splits"
            d.mkdir(parents=True, exist_ok=True)
            s.to_parquet(d / f"{fam}_r{r}.parquet", index=False)
            info["hash"] = df_hash(s)
            summary[f"{suite}/{fam}/r{r}"] = info
    existing = read_json(paths.manifests / "splits.json") if (paths.manifests / "splits.json").exists() else {}
    existing.update(summary)
    write_json(paths.manifests / "splits.json", existing)
    return summary


def load_split(paths: Paths, suite: str, family: str, rep: int) -> pd.DataFrame:
    return pd.read_parquet(paths.canonical / suite / "splits" / f"{family}_r{rep}.parquet")
