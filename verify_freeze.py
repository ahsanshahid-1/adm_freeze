"""Recompute the frozen hashes from the files in this repository (Python standard library only).

Usage:  python verify_freeze.py

Checks, against freeze/manifests/freeze.json:
  1. code_hash      = SHA-256 tree hash of code/adm_code (*.py, *.md, *.json), as computed by adm.core.sha256_tree
  2. config_hash    = canonical-JSON hash of the frozen configuration subset of freeze/configs/study.json
  3. protocol_hash  = canonical-JSON hash of {"code": code_hash, "cfg": frozen configuration}
  4. datasets / splits / canonical manifest hashes
  5. the formal Tier-2 oracle solvability record (all instances solvable)
The hashing functions below mirror adm/core.py and adm/power.py in code/adm_code exactly.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FREEZE = ROOT / "freeze"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_tree(root: Path, patterns=("**/*.py", "**/*.md", "**/*.json"), exclude_dirs=("__pycache__",)) -> str:
    entries = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file() and not (set(p.relative_to(root).parts) & set(exclude_dirs)):
                entries.append((p.relative_to(root).as_posix(), sha256_file(p)))
    return hashlib.sha256(json.dumps(sorted(set(entries))).encode("utf-8")).hexdigest()


def json_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def frozen_config_subset(cfg: dict) -> dict:
    keys = ["limits", "generation", "repetitions", "optional_budget_experiment", "concurrency", "fit_slots"]
    if cfg.get("tier2_conditions") is not None:
        keys.append("tier2_conditions")
    return {k: cfg.get(k) for k in keys}


def main() -> int:
    man = json.loads((FREEZE / "manifests" / "freeze.json").read_text())
    study = json.loads((FREEZE / "configs" / "study.json").read_text())
    sub = frozen_config_subset(study)
    code = sha256_tree(ROOT / "code" / "adm_code")
    checks = [
        ("code_hash", code, man["code_hash"]),
        ("frozen config = study.json subset", json_hash(sub), json_hash(man["frozen_config"])),
        ("config_hash", json_hash(man["frozen_config"]), man["config_hash"]),
        ("protocol_hash", json_hash({"code": code, "cfg": man["frozen_config"]}), man["protocol_hash"]),
    ]
    for k in ("datasets", "splits", "canonical"):
        checks.append((f"{k}_manifest_hash", json_hash(json.loads((FREEZE / "manifests" / f"{k}.json").read_text())),
                       man[f"{k}_manifest_hash"]))
    ok = True
    for name, got, want in checks:
        good = got == want
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {name}: {got}" + ("" if good else f" (expected {want})"))
    sol = json.loads((FREEZE / "outputs" / "tier2_solvability_formal.json").read_text())
    good = sol["all_solvable"] and not sol["failures"]
    ok &= good
    print(f"{'OK  ' if good else 'FAIL'} Tier-2 oracle solvability: {sol['instances'] - len(sol['failures'])}/{sol['instances']}")
    print(f"freeze created {man['created']}; protocol hash {man['protocol_hash']}")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
