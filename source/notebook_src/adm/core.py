"""Core utilities: seeds, hashing, paths, settings, JSON I/O and the session clock."""
from __future__ import annotations

import decimal
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

PROTOCOL_VERSION = "adm-kaggle-1.0"
MASTER_SEED = 20261030
NAMESPACES = ("development", "evaluation", "corruption", "split", "estimator", "agent")

FAMILIES = ["D1", "D2", "D3", "D4", "D5", "D6"]
DEV_FAMILIES = ["D5", "D6"]
TEMPLATES = ["T1", "T2", "T3", "T4", "T5", "T6"]
CONDITIONS = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
NEGATIVE_CONDITIONS = ["N1", "N2"]
TIER2_CONDITIONS = ["X1a", "X1b", "X1c", "X2a", "X2b", "X2c", "X3a", "X3b", "X3c"]  # first calibration (E0X)
# main-plan-v2.1 Section 7.6 (amended): X1 is dropped from the design and replaced by X4, a provenance-type defect
TIER2_DESIGN = ["X2a", "X2b", "X2c", "X3a", "X3b", "X3c", "X4a", "X4b", "X4c"]  # second calibration (E0X2)
SYSTEMS = ["F", "S0", "M0", "MQ", "MP", "SQP", "MQP"]
AGENTIC_SYSTEMS = ["S0", "M0", "MQ", "MP", "SQP", "MQP"]
REPLICATION_TASKS = ["D1-T5", "D2-T2", "D3-T4", "D4-T6", "D5-T3", "D6-T1"]
REPLICATION_SYSTEMS = ["M0", "SQP", "MQP"]

# Architecture table (Section 11): code -> (planning, Q gates, P gates)
SYSTEM_SPEC = {
    "F": {"planner": "fixed", "q": True, "p": True},
    "S0": {"planner": "single", "q": False, "p": False},
    "M0": {"planner": "multi", "q": False, "p": False},
    "MQ": {"planner": "multi", "q": True, "p": False},
    "MP": {"planner": "multi", "q": False, "p": True},
    "SQP": {"planner": "single", "q": True, "p": True},
    "MQP": {"planner": "multi", "q": True, "p": True},
}

ABSTENTION_REASONS = [
    "REQUIRED_SOURCE_MISSING",
    "AMBIGUOUS_AUTHORITY",
    "CONTRACT_UNSATISFIABLE",
    "BUDGET_INSUFFICIENT",
]

TERMINAL_STATES = ["SUBMITTED", "ABSTAINED", "BUDGET_EXCEEDED", "EXECUTION_ERROR", "INFRASTRUCTURE_ERROR"]

PILOT_LIMITS = {
    "aggregate_tokens": 300_000,
    "model_calls": 48,
    "tool_calls": 40,
    "repair_cycles": 2,
    "pipeline_evaluations": 6,
    "wall_seconds": 1200,
}
PROTOCOL_LIMITS = {
    "aggregate_tokens": 30_000,
    "model_calls": 48,
    "tool_calls": 40,
    "repair_cycles": 2,
    "pipeline_evaluations": 6,
    "wall_seconds": 600,
}
GENERATION = {
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "max_context_tokens": 16384,
    "max_output_tokens_per_call": 1024,
    # main-plan-v2.md Section 9.2: reasoning ("thinking") mode off for every backbone; actions are schema-constrained
    # JSON within a 1,024-token output limit. Sent as chat_template_kwargs; templates without the switch ignore it.
    "enable_thinking": False,
}


# --------------------------------------------------------------------------- seeds
def seed_string(namespace: str, family: str = "", task: str = "", repetition: Any = "",
                component: str = "", master_seed: int = MASTER_SEED,
                protocol_version: str = PROTOCOL_VERSION) -> str:
    """The exact string hashed for seed derivation (Section 5.1)."""
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown seed namespace {namespace!r}")
    parts = [protocol_version, str(master_seed), namespace, str(family), str(task), str(repetition), str(component)]
    return "|".join(parts)


def derive_seed(namespace: str, family: str = "", task: str = "", repetition: Any = "",
                component: str = "", master_seed: int = MASTER_SEED,
                protocol_version: str = PROTOCOL_VERSION) -> int:
    """First eight bytes of SHA-256 over the UTF-8 seed string, read as unsigned big-endian."""
    s = seed_string(namespace, family, task, repetition, component, master_seed, protocol_version)
    return int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "big", signed=False)


def make_rng(namespace: str, family: str = "", task: str = "", repetition: Any = "",
             component: str = "") -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(derive_seed(namespace, family, task, repetition, component)))


def small_seed(seed: int) -> int:
    """Fold a 64-bit seed into the 31-bit range accepted by scikit-learn and vLLM."""
    return int(seed % (2**31 - 1))


# --------------------------------------------------------------------------- hashing
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_tree(root: str | Path, patterns: Iterable[str] = ("**/*",), exclude_dirs: Iterable[str] = ("__pycache__",)) -> str:
    root = Path(root)
    entries = []
    ex = set(exclude_dirs)
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file() and not (set(p.relative_to(root).parts) & ex):
                entries.append((p.relative_to(root).as_posix(), sha256_file(p)))
    entries = sorted(set(entries))
    return sha256_text(json.dumps(entries))


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_json_default)


def json_hash(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def df_hash(df: pd.DataFrame) -> str:
    """Content hash of a table: independent of file encoding, row order and column order, but
    sensitive to every value and to row multiplicity."""
    d = df[sorted(df.columns)]
    buf = io.StringIO()
    d.to_csv(buf, index=False, float_format="%.17g", na_rep="<NA>", lineterminator="\n")
    lines = buf.getvalue().split("\n")
    header, rows = lines[0], sorted(l for l in lines[1:] if l != "")
    return sha256_text(header + "\n" + "\n".join(rows))


# --------------------------------------------------------------------------- JSON I/O
def _json_default(o: Any):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return None if not math.isfinite(v) else v
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, decimal.Decimal):  # DuckDB returns DECIMAL columns as decimal.Decimal
        v = float(o)
        return None if not math.isfinite(v) else v
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    raise TypeError(f"not JSON serializable: {type(o)}")


def clean_json(obj: Any) -> Any:
    """Replace non-finite floats with None recursively (JSON has no NaN)."""
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def dumps(obj: Any, indent: int | None = None) -> str:
    return json.dumps(clean_json(obj), indent=indent, default=_json_default, sort_keys=indent is not None)


def write_json(path: str | Path, obj: Any, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(dumps(obj, indent=indent))
    os.replace(tmp, path)


def write_json_once(path: str | Path, obj: Any) -> bool:
    """Write an immutable record. Returns False (and does not overwrite) if it exists."""
    path = Path(path)
    if path.exists():
        return False
    write_json(path, obj)
    return True


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def append_jsonl_gz(path: str | Path, records: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as f:
        for r in records:
            f.write(dumps(r) + "\n")


def read_jsonl_gz(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: str | Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(dumps(record) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------- paths
@dataclass
class Paths:
    """All directories used by the study. ``state`` is persisted between Kaggle sessions;
    ``cache`` is session-local (rebuilt deterministically and hash-verified)."""

    state: Path
    cache: Path
    models: Path

    def __post_init__(self):
        self.state = Path(self.state)
        self.cache = Path(self.cache)
        self.models = Path(self.models)

    # persisted
    @property
    def configs(self) -> Path: return self.state / "configs"
    @property
    def manifests(self) -> Path: return self.state / "manifests"
    @property
    def raw(self) -> Path: return self.state / "data" / "raw"
    @property
    def canonical(self) -> Path: return self.state / "data" / "canonical"
    @property
    def outputs(self) -> Path: return self.state / "outputs"
    @property
    def runs(self) -> Path: return self.outputs / "runs"
    @property
    def attempts(self) -> Path: return self.outputs / "attempts"
    @property
    def traces(self) -> Path: return self.outputs / "traces"
    @property
    def submissions(self) -> Path: return self.outputs / "submissions"
    @property
    def tables(self) -> Path: return self.outputs / "tables"
    @property
    def figures(self) -> Path: return self.outputs / "figures"
    @property
    def reports(self) -> Path: return self.state / "reports"
    # session-local
    @property
    def generated(self) -> Path: return self.cache / "data" / "generated"
    @property
    def trusted(self) -> Path: return self.cache / "data" / "trusted"
    @property
    def private(self) -> Path: return self.cache / "private_evaluation"
    @property
    def work(self) -> Path: return self.cache / "work"

    def ensure(self) -> "Paths":
        for p in [self.configs, self.manifests, self.raw, self.canonical, self.runs, self.attempts,
                  self.traces, self.submissions, self.tables, self.figures, self.reports,
                  self.generated, self.trusted, self.private, self.work, self.models]:
            p.mkdir(parents=True, exist_ok=True)
        return self

    def to_dict(self) -> dict:
        return {"state": str(self.state), "cache": str(self.cache), "models": str(self.models)}

    @classmethod
    def from_dict(cls, d: dict) -> "Paths":
        return cls(Path(d["state"]), Path(d["cache"]), Path(d["models"]))


# --------------------------------------------------------------------------- session clock
@dataclass
class SessionClock:
    """Guards the 12-hour Kaggle session. New runs stop being dispatched at ``stop_new_h``;
    in-flight runs are killed at ``hard_stop_h`` and marked as infrastructure failures."""

    start: float = field(default_factory=time.time)
    stop_new_h: float = 10.5
    hard_stop_h: float = 11.25
    already_elapsed_s: float = 0.0
    now_fn: Any = time.time

    def elapsed(self) -> float:
        return self.now_fn() - self.start + self.already_elapsed_s

    def may_start_new(self, expected_duration_s: float = 0.0) -> bool:
        return self.elapsed() + expected_duration_s < self.stop_new_h * 3600

    def must_stop(self) -> bool:
        return self.elapsed() >= self.hard_stop_h * 3600

    def remaining_new_s(self) -> float:
        return self.stop_new_h * 3600 - self.elapsed()

    def to_dict(self) -> dict:
        return {"start": self.start, "stop_new_h": self.stop_new_h, "hard_stop_h": self.hard_stop_h,
                "already_elapsed_s": self.already_elapsed_s}


# --------------------------------------------------------------------------- misc
def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def dir_size_bytes(path: str | Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def rmtree(path: str | Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def task_id(family: str, template: str) -> str:
    return f"{family}-{template}"


def base_task_index(family: str, template: str) -> int:
    return FAMILIES.index(family) * len(TEMPLATES) + TEMPLATES.index(template)


def instance_key(suite: str, family: str, template: str, condition: str, rep: int) -> str:
    return f"{suite}/{family}-{template}/{condition}/r{rep}"


def instance_dirs(paths: Paths, suite: str, family: str, template: str, condition: str, rep: int) -> dict:
    rel = Path(suite) / f"{family}-{template}" / condition / f"r{rep}"
    return {
        "visible": paths.generated / rel,
        "trusted": paths.trusted / rel,
        "private": paths.private / rel,
    }


def safe_name(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)
