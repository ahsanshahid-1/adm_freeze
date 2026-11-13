"""Stage orchestration used by the notebook: setup/restore, build, tests, pilot, freeze, formal runs,
analysis and the end-of-session summary."""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from . import analysis as A
from . import datasets as D
from . import fixtures as FX
from . import power as PW
from . import references as REF
from . import runner as R
from . import tasks as T
from .core import (FAMILIES, GENERATION, PILOT_LIMITS, PROTOCOL_LIMITS, TEMPLATES, CONDITIONS, Paths, SessionClock,
                   dir_size_bytes, now_iso, read_json, write_json, append_jsonl, read_jsonl)

MOCK_BANNER = ("> **MOCK MODE.** Agent decisions came from the scripted MockLLM, not a language model. These numbers test the "
               "pipeline only and are not research results.")
PILOT_BANNER = ("> Pilot (E0) on separate development tasks. Not part of confirmatory scores. Used to calibrate limits, "
                "estimate variance and cost, and freeze the protocol.")
REHEARSAL_BANNER = "> **REHEARSAL DESIGN.** A reduced design used to test multi-session execution locally."

_ISOLATION = ("Agents act only through bounded tools; DuckDB runs in memory with external access disabled and configuration "
              "locked; the evaluator runs in a separate process and is the only component given the private evaluation directory.")
PLATFORM_DEVIATIONS = {
    "kaggle": [
        "Backbones are 4-bit AWQ community/official quantizations served in float16 (Tesla T4 has no native BF16 and cannot "
        "hold BF16 30B weights). Section 9.1 requires this to be recorded; the exact repository and revision are in configs/models.lock.json.",
        "Isolation is process-level instead of containers (Kaggle does not provide containers). " + _ISOLATION,
        "The 8 GiB per-run memory cap is measured (peak RSS) rather than enforced.",
        "Monetary cost is not available on Kaggle; GPU-seconds (2 x T4 server wall time) and active seconds are reported instead.",
    ],
    "crc": [
        "This run follows main-plan-v2.md, a revision of main-plan.md v1.0 made before the pilot: backbones changed to "
        "Qwen/Qwen3.8-27B (A) and google/gemma-4-31B-it (B), reasoning mode disabled (Section 9.2), single-GPU hardware "
        "(Section 20.1) and a ceiling check in E0. Exact repositories and revisions are in configs/models.lock.json.",
        "Isolation is process-level instead of containers (the CRC JupyterHub server provides no container runtime). " + _ISOLATION,
        "The 8 GiB per-run memory cap is measured (peak RSS) rather than enforced.",
        "Monetary cost is not available for the CRC server (no per-run tariff); GPU-seconds (1 x RTX PRO 6000 server wall "
        "time) and active seconds are reported instead.",
    ],
}
PLATFORM_DEVIATIONS["local"] = PLATFORM_DEVIATIONS["kaggle"]
COMMON_DEVIATIONS = [
    "Pilot limits are a calibration budget (300k tokens, 48 calls, 40 tool calls, 20 minutes). Frozen limits are set by the "
    "prespecified p90 rule in adm/power.py; the protocol text's 30k-token budget is reported alongside.",
    "The AI4I identifier column is UDI in the archive (the protocol says UID); it is mapped to uid and excluded.",
    "Repair cycles are counted as materialize_features calls issued after a failure verdict (gate failure or execution error).",
    "Workers in the three-agent team cannot submit or abstain; those are coordinator decisions (Section 9.4 responsibilities).",
    "One-hot encoding groups categories beyond 64 levels (max_categories) to protect memory if an identifier is used as a predictor.",
    "Fitted model pickles are deleted after evaluation except for a 2% deterministic sample retained for E6 replay; graphs, "
    "choices, provenance and test predictions are kept for every submission.",
    "Pickled models and hidden data are regenerated deterministically in each session and verified against recorded content digests.",
]
STATIC_DEVIATIONS = PLATFORM_DEVIATIONS["kaggle"] + COMMON_DEVIATIONS  # backwards-compatible name


def deviations_for(platform: str) -> list:
    return PLATFORM_DEVIATIONS.get(platform, PLATFORM_DEVIATIONS["kaggle"]) + COMMON_DEVIATIONS


SESSION_ENV = "ADM_RUN_ROOT"


def _proc_ids() -> list:
    try:
        return [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return []


def _proc_has_marker(pid: int, marker: bytes) -> bool:
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            return marker in (f.read() + b"\0")
    except OSError:
        return False


def _is_python(pid: int) -> bool:
    """A live session owner is a kernel process. (Its own /proc environ predates the marker, so check the command.)"""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return b"python" in f.read()
    except OSError:
        return False


def _ancestors(pid: int) -> set:
    out = set()
    while pid > 1 and pid not in out:
        out.add(pid)
        try:
            with open(f"/proc/{pid}/stat") as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return out


def acquire_session(paths: Paths, log=print) -> dict:
    """Make a session safe to start after a previous one was killed (kernel restart, server cull, kill -9).

    Every process this pipeline starts (agent workers, evaluator workers, the vLLM server) inherits the environment
    marker ADM_RUN_ROOT=<state dir>. If the previous session's owner is dead, its leftover processes are terminated
    so the GPU and port are free. If another live session owns this state directory, starting is refused.
    Completed runs are never redone; a run that was in flight is retried once (Section 13.4)."""
    root = str(paths.state.resolve())
    os.environ[SESSION_ENV] = root
    marker = f"{SESSION_ENV}={root}\0".encode()
    lock = paths.state / "session.lock"
    me = os.getpid()
    if lock.exists():
        try:
            other = int(read_json(lock).get("pid", 0))
        except Exception:
            other = 0
        if other and other != me and _is_python(other):
            raise RuntimeError(f"another notebook session (pid {other}) is running on {root}; stop it before starting "
                               "a new one (Kernel -> Shut Down in its tab), then run again")
    mine = _ancestors(me)
    uid = os.getuid()
    stale = []
    for pid in _proc_ids():
        if pid in mine:
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != uid:
                continue
        except OSError:
            continue
        if _proc_has_marker(pid, marker):
            stale.append(pid)
    if stale:
        log(f"previous session left {len(stale)} processes running (workers / model server); stopping them")
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in stale:
                try:
                    os.kill(pid, sig)
                except OSError:
                    pass
            t0 = time.time()
            while time.time() - t0 < 30 and any(Path(f"/proc/{p}").exists() for p in stale):
                time.sleep(1)
        t0 = time.time()  # the GPU releases memory asynchronously after the server dies
        while time.time() - t0 < 300:
            q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True,
                               text=True) if shutil.which("nvidia-smi") else None
            if q is None or not {int(x) for x in q.stdout.split() if x.strip().isdigit()} & set(stale):
                break
            time.sleep(5)
    write_json(lock, {"pid": me, "started": now_iso()})
    return {"stopped_processes": len(stale)}


def release_session(paths: Paths):
    lock = paths.state / "session.lock"
    try:
        if int(read_json(lock).get("pid", 0)) == os.getpid():
            lock.unlink()
    except Exception:
        pass


def detect_mode() -> str:
    forced = os.environ.get("ADM_PLATFORM")
    if forced:
        return forced
    if Path("/kaggle/working").exists() and os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        return "kaggle"
    if Path("/srv/exaiops-shared").exists() and "/exaiops/" in os.environ.get("JUPYTERHUB_API_URL", ""):
        return "crc"
    return "local"


def make_paths(mode: str, local_root: Path | None = None, crc_root: Path | None = None) -> tuple[Paths, Path]:
    if mode == "kaggle":
        return Paths(Path("/kaggle/working/adm_state"), Path("/tmp/adm_cache"), Path("/tmp/adm_models")).ensure(), Path("/tmp/adm_vllm_env")
    if mode == "crc":
        # everything the notebook creates lives under one run folder and persists, so later sessions reuse the
        # vLLM environment and model weights
        root = Path(crc_root or "adm_crc_run").resolve()
        return Paths(root / "adm_state", root / "adm_cache", root / "adm_models").ensure(), root / "vllm_env"
    root = Path(local_root or "adm_local_run").resolve()
    return Paths(root / "adm_state", root / "adm_cache", root / "adm_models").ensure(), root / "vllm_env_unused"


# --------------------------------------------------------------------------- state
def state(paths: Paths) -> dict:
    p = paths.state / "STATE.json"
    return read_json(p) if p.exists() else {"created": now_iso(), "sessions": [], "stages": {}}


def save_state(paths: Paths, st: dict):
    st["updated"] = now_iso()
    write_json(paths.state / "STATE.json", st)


def restore_from_inputs(paths: Paths, log=print, roots=("/kaggle/input",)) -> str | None:
    """Copy the most recent previous-session state attached as a Kaggle input."""
    best, best_t = None, ""
    for root in roots:
        r = Path(root)
        if not r.exists():
            continue
        for p in list(r.glob("*/adm_state/STATE.json")) + list(r.glob("*/*/adm_state/STATE.json")) + \
                list(r.glob("*/*/*/adm_state/STATE.json")):
            try:
                t = read_json(p).get("updated", "")
            except Exception:
                continue
            if t > best_t:
                best, best_t = p.parent, t
    cur = state(paths).get("updated", "") if (paths.state / "STATE.json").exists() else ""
    if best and best_t > cur:
        log(f"restoring previous session state from {best} (updated {best_t})")
        shutil.copytree(best, paths.state, dirs_exist_ok=True)
        return str(best)
    log("no newer previous-session state found in inputs" if roots else "")
    return None


def init_config(paths: Paths, mode: str, user: dict) -> dict:
    p = paths.configs / "study.json"
    cfg = read_json(p) if p.exists() else {}
    frozen = (paths.manifests / "freeze.json").exists()
    defaults = {
        "study_id": f"agentic-data-mining-{'crc' if mode == 'crc' else 'kaggle'}-v1", "master_seed": 20261030, "human_subjects": False,
        "human_evaluators": False, "llm_judge": False, "runtime_human_approval": False,
        "limits": dict(PILOT_LIMITS), "generation": dict(GENERATION), "repetitions": [0, 1, 2],
        "optional_budget_experiment": False, "concurrency": 8 if mode in ("kaggle", "crc") else 6, "fit_slots": 3,
        "evaluator_workers": 1, "retain_model_fraction": 0.02,
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)
    lockable = set(PW.frozen_config_subset(cfg))
    for k, v in user.items():
        if v is None:
            continue
        if frozen and k in lockable and cfg.get(k) != v:
            raise RuntimeError(f"'{k}' is locked by the protocol freeze (frozen {cfg.get(k)}, requested {v})")
        cfg[k] = v
    cfg["mode"] = mode
    cfg["llm"] = cfg.get("llm") or {}
    cfg["llm"]["mode"] = "mock" if mode == "local" or user.get("force_mock") else "vllm"
    write_json(p, cfg)
    return cfg


def write_deviations(paths: Paths, extra: list | None = None):
    study = paths.configs / "study.json"
    platform = (read_json(study).get("mode") if study.exists() else None) or "kaggle"
    lines = ["# Protocol deviations (recorded automatically)", ""]
    lines += [f"{i + 1}. {d}" for i, d in enumerate(deviations_for(platform) + (extra or []))]
    lock = paths.configs / "models.lock.json"
    if lock.exists():
        L = read_json(lock)
        lines.append("")
        hw = (L.get("platform") or {}).get("label")
        lines.append(f"Resolved serving stack: vLLM {L.get('vllm_version')}" + (f" on {hw}." if hw else "."))
        for b, e in (L.get("backbones") or {}).items():
            lines.append(f"- Backbone {b}: {e.get('repo')} @ {e.get('revision')} (base {e.get('base_model')}), "
                         f"dtype {e.get('dtype')}, launch variant '{e.get('launch_variant')}', "
                         f"structured output via {e.get('structured_mode')}.")
    (paths.reports / "deviations.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- build and tests
def stage_build(paths: Paths, log=print) -> dict:
    t0 = time.time()
    man = D.acquire(paths)
    summary = D.build_canonical(paths)
    D.build_splits(paths, "evaluation", FAMILIES, [0, 1, 2, 3, 4, 5])
    D.build_splits(paths, "development", ["D5", "D6"], [0, 1, 2])
    log(f"benchmark sources and splits ready in {time.time() - t0:.0f}s")
    return {"datasets": {k: v["sha256"] for k, v in man.items()}, "canonical": summary}


def stage_tests(pkg_root: Path, log=print) -> int:
    env = {**os.environ, "PYTHONPATH": str(pkg_root)}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", str(pkg_root / "tests")],
                       capture_output=True, text=True, env=env, cwd=str(pkg_root))
    log(r.stdout[-4000:] + r.stderr[-2000:])
    return r.returncode


# --------------------------------------------------------------------------- LLM
def start_llm(paths: Paths, cfg: dict, server, backbone: str, frozen: bool, log=print):
    if cfg["llm"]["mode"] == "mock":
        return
    entry = server.ensure(backbone, cfg["generation"], frozen=frozen)
    cfg["llm"].update({"base_url": server.url, "served_model": backbone,
                       "served_models": {"A": "A", "B": "B"}, "structured_mode": entry["structured_mode"]})
    lock = server.lock()
    cfg["model_lock"] = {b: {"repo": e["repo"], "revision": e["revision"], "tokenizer_hash": e.get("tokenizer_hash")}
                         for b, e in (lock.get("backbones") or {}).items()}
    write_json(paths.configs / "study.json", cfg)
    write_deviations(paths)


def stop_llm(paths: Paths, server, experiment: str):
    if server is None:
        return
    b = server.backbone
    server.stop()
    if b:
        append_jsonl(paths.outputs / "gpu_accounting.jsonl", {"time": now_iso(), "experiment": experiment, "backbone": b,
                                                              "gpu_seconds_total": server.gpu_seconds.get(b)})


# --------------------------------------------------------------------------- runs
def _prepare(paths: Paths, runs: list, cfg: dict, log=print) -> None:
    keys = {(r["suite"], r["family"], r["template"], r["condition"], r["repetition"]) for r in runs}
    t0 = time.time()
    metas = T.ensure_instances(paths, list(keys), workers=min(4, os.cpu_count() or 2))
    cfg["instance_hashes"] = {**cfg.get("instance_hashes", {}),
                              **{f"{k[0]}/{k[1]}-{k[2]}/{k[3]}/r{k[4]}": m["hashes"] for k, m in metas.items()}}
    cfg["split_hashes"] = read_json(paths.manifests / "splits.json")
    log(f"{len(keys)} task instances ready ({time.time() - t0:.0f}s)")


def _retain(run_id: str, frac: float) -> bool:
    return int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % 10000 < frac * 10000


def run_experiment(paths: Paths, cfg: dict, clock: SessionClock, runs: list, label: str, log=print) -> dict:
    if not runs:
        return {"scheduled": 0}
    rn = R.Runner(paths, cfg, clock, log)
    pend = rn.pending(runs)
    log(f"[{label}] {len(runs)} scheduled, {len(pend)} pending")
    if not pend:
        return {"scheduled": len(runs), "pending_at_start": 0, "completed": 0}
    _prepare(paths, pend, cfg, log)
    retain_ids = {r["run_id"] for r in pend if _retain(r["run_id"], cfg.get("retain_model_fraction", 0.02))}
    t0 = time.time()

    def progress(st, q, a, e):
        log(f"[{label}] done {st['completed']}/{st['pending_at_start']} | queued {q} | running {a} | evaluating {e} | "
            f"elapsed {(time.time() - t0) / 60:.1f} min | session {clock.elapsed() / 3600:.2f} h")

    st = rn.execute(pend, cfg["concurrency"], cfg.get("evaluator_workers", 1), progress, retain_ids)
    st["wall_seconds"] = round(time.time() - t0, 1)
    append_jsonl(paths.outputs / "stage_log.jsonl", {"time": now_iso(), "label": label, **st})
    log(f"[{label}] session result: {st}")
    return st


# --------------------------------------------------------------------------- pilot
def stage_pilot(paths: Paths, cfg: dict, clock: SessionClock, server, log=print) -> dict:
    st = state(paths)
    if st["stages"].get("pilot") == "done":
        log("pilot already complete")
        return st["stages"]
    log("== Evaluator fixtures (known-correct and known-incorrect artifacts) ==")
    fx = FX.run_evaluator_fixtures(paths, log=log)
    if not fx["all_passed"]:
        raise RuntimeError("evaluator fixtures failed; fix the evaluator before running agents")
    cfg["limits"] = dict(PILOT_LIMITS)
    runs = R.experiment_runs("E0", [0, 1])
    start_llm(paths, cfg, server, "A", frozen=False, log=log)
    res = run_experiment(paths, cfg, clock, runs, "E0", log)
    stop_llm(paths, server, "E0")
    if R.Runner(paths, cfg, clock).pending(runs):
        log("pilot incomplete; rerun this stage in the next session")
        save_state(paths, st)
        return st["stages"]
    # backbone-B smoke test (unscored)
    b_runs = R.experiment_runs("E0B", [0])
    start_llm(paths, cfg, server, "B", frozen=False, log=log)
    run_experiment(paths, cfg, clock, b_runs, "E0B", log)
    stop_llm(paths, server, "E0B")
    pilot_report(paths, cfg, log)
    st["stages"]["pilot"] = "done"
    save_state(paths, st)
    return st["stages"]


CEILING_M0_VCR = 0.95  # main-plan-v2.md E0 ceiling check


def ceiling_check(df: pd.DataFrame) -> str:
    """main-plan-v2.md E0: flag a benchmark that is too easy before the freeze (never swap in a weaker model)."""
    if df.empty or "V" not in df:
        return "## 15. Ceiling check\nNo pilot records.\n"
    vcr = df.groupby("system")["V"].mean()
    m0 = float(vcr.get("M0", float("nan")))
    full = sorted(s for s, v in vcr.items() if s != "F" and v >= 1.0)
    flag = (m0 >= CEILING_M0_VCR) or bool(full)
    lines = ["## 15. Ceiling check (main-plan-v2.md, E0)",
             f"M0 pilot VCR: {m0:.3f} (threshold {CEILING_M0_VCR}). Agentic systems at 100%: {', '.join(full) or 'none'}.",
             ("**CEILING WARNING:** revise task difficulty (conditions or tasks) before the freeze and record the change; "
              "do not substitute a weaker backbone." if flag else "No ceiling warning.")]
    return "\n".join(lines) + "\n"


TIER2_LEVELS = {"X1": ["X1a", "X1b", "X1c"], "X2": ["X2a", "X2b", "X2c"], "X3": ["X3a", "X3b", "X3c"]}
TIER2_LEVELS_V2 = {"X2": ["X2a", "X2b", "X2c"], "X3": ["X3a", "X3b", "X3c"], "X4": ["X4a", "X4b", "X4c"]}
CALIBRATIONS = {  # STAGE -> (experiment, repetitions, defect levels, output suffix, state key)
    "calibrate": ("E0X", [0], TIER2_LEVELS, "", "tier2_calibration"),
    "calibrate2": ("E0X2", [1, 2], TIER2_LEVELS_V2, "_v2", "tier2_calibration_v2"),
}
CALIBRATION_SYSTEMS = ["S0", "M0"]  # baseline agents whose success should sit near 50% (main-plan-v2.1 Section 12, E0X)


def tier2_calibration(df: pd.DataFrame, levels_map: dict | None = None) -> dict:
    """Prespecified rule (main-plan-v2.1): for each Tier-2 defect, freeze the level whose pooled S0+M0 verified-completion
    rate is closest to 0.5; ties go to the lower severity. Uses development tasks only."""
    out = {"rule": "argmin |VCR(S0,M0 pooled) - 0.5| per defect; ties -> lower level", "defects": {}}
    for d, levels in (levels_map or TIER2_LEVELS).items():
        rows = []
        for lv in levels:
            sub = df[(df["condition"] == lv) & (df["system"].isin(CALIBRATION_SYSTEMS))] if not df.empty else df
            n = int(len(sub))
            v = float(sub["V"].mean()) if n else None
            by = ({s: float(g["V"].mean()) for s, g in df[df["condition"] == lv].groupby("system")} if not df.empty else {})
            rows.append({"level": lv, "n_baseline_runs": n, "baseline_vcr": v, "vcr_by_system": by})
        scored = [r for r in rows if r["baseline_vcr"] is not None]
        chosen = min(scored, key=lambda r: (abs(r["baseline_vcr"] - 0.5), levels.index(r["level"])))["level"] if scored else None
        out["defects"][d] = {"levels": rows, "chosen": chosen, "complete": all(r["n_baseline_runs"] for r in rows)}
    return out


def stage_tier2_calibration(paths: Paths, cfg: dict, clock: SessionClock, server, log=print,
                            which: str = "calibrate") -> dict:
    """Tier-2 calibration pilot (development tasks, backbone A, pilot limits). Before any agent runs, the Tier-2
    evaluator fixtures must pass and the oracle solver must reproduce the hidden reference on every instance."""
    exp, reps, levels_map, sfx, key = CALIBRATIONS[which]
    st = state(paths)
    if st["stages"].get("pilot") != "done":
        raise RuntimeError("Tier-2 calibration runs after the main pilot (E0)")
    runs = R.experiment_runs(exp, reps)
    if not (paths.outputs / f"tier2_solvability{sfx}.json").exists():
        log("== Tier-2 evaluator fixtures ==")
        fx = FX.run_evaluator_fixtures(paths, log=log, fixtures=FX.TIER2_FIXTURES,
                                       out_name=f"evaluator_fixtures_tier2{sfx}.json")
        if not fx["all_passed"]:
            raise RuntimeError("Tier-2 evaluator fixtures failed; fix before running agents")
        keys = sorted({(r["suite"], r["family"], r["template"], r["condition"], r["repetition"]) for r in runs})
        _prepare(paths, runs, cfg, log)
        sol = FX.oracle_solvability(paths, keys, log)
        if not sol["all_solvable"]:
            raise RuntimeError(f"oracle could not solve {len(sol['failures'])} Tier-2 instances: {sol['failures'][:5]}")
        write_json(paths.outputs / f"tier2_solvability{sfx}.json", sol)
    cfg["limits"] = dict(PILOT_LIMITS)
    if R.Runner(paths, cfg, clock).pending(runs) and clock.may_start_new(120):
        start_llm(paths, cfg, server, "A", frozen=False, log=log)
        run_experiment(paths, cfg, clock, runs, exp, log)
        stop_llm(paths, server, exp)
    df = A.records_df(R.load_records(paths, exp))
    cal = tier2_calibration(df, levels_map)
    cal.update({"experiment": exp, "repetitions": reps})
    write_json(paths.manifests / f"tier2_calibration{sfx}.json", cal)
    pending = len(R.Runner(paths, cfg, clock).pending(runs))
    refs = REF.build_references(paths, "development", ["D5", "D6"], TEMPLATES, [0, 1], log)
    lines = ["## Tier-2 calibration (prespecified rule)", f"Rule: {cal['rule']}. Runs pending: {pending} of {len(runs)}.", ""]
    for d, v in cal["defects"].items():
        lines.append(f"- {d}: chosen level **{v['chosen']}** ({'complete' if v['complete'] else 'INCOMPLETE'}); " + "; ".join(
            f"{r['level']}: S0+M0 VCR {r['baseline_vcr'] if r['baseline_vcr'] is None else round(r['baseline_vcr'], 3)} "
            f"(n={r['n_baseline_runs']})" for r in v["levels"]))
    banner = PILOT_BANNER + f"\n\n> Tier-2 calibration pilot {exp} (main-plan-v2.1), recorded separately from E0."
    title = f"Tier2{sfx} calibration pilot {exp} report"
    text = A.report(df, title, paths.reports, paths.figures, refs, banner, draws=2000,
                    extra_sections=["\n".join(lines) + "\n", ceiling_check(df)]) if not df.empty else "\n".join(lines)
    (paths.reports / f"pilot_tier2{sfx}.md").write_text(text)
    if pending:
        log(f"Tier-2 calibration incomplete ({pending} runs pending); run STAGE = '{which}' again to continue")
    else:
        st["stages"][key] = "done"
    save_state(paths, st)
    log(f"Tier-2 calibration report written: {paths.reports / f'pilot_tier2{sfx}.md'}")
    return cal


def stage_pilot_supplement(paths: Paths, cfg: dict, clock: SessionClock, server, log=print) -> dict:
    """Supplementary pilot E0S: development tasks under C1-C5 (backbone A, pilot limits). Recorded and reported
    separately from E0; it does not change the freeze proposal."""
    st = state(paths)
    if st["stages"].get("pilot") != "done":
        raise RuntimeError("the supplementary pilot runs after the main pilot (E0)")
    cfg["limits"] = dict(PILOT_LIMITS)
    plan = [("E0S", "A"), ("E0SB", "B")]
    for exp, backbone in plan:
        runs = R.experiment_runs(exp, [0, 1])
        if not R.Runner(paths, cfg, clock).pending(runs):
            continue
        if not clock.may_start_new(120):
            log("not enough session time left to start the next supplementary block")
            break
        start_llm(paths, cfg, server, backbone, frozen=False, log=log)
        run_experiment(paths, cfg, clock, runs, exp, log)
        stop_llm(paths, server, exp)
    if any(R.Runner(paths, cfg, clock).pending(R.experiment_runs(e, [0, 1])) for e, _ in plan):
        log("supplementary pilot incomplete; run STAGE = 'supplement' again to continue")
        save_state(paths, st)
        return st["stages"]
    refs = REF.build_references(paths, "development", ["D5", "D6"], TEMPLATES, [0, 1], log)
    banner = PILOT_BANNER + "\n\n> Supplementary pilot, recorded separately from E0 (Section 12)."
    df = A.records_df(R.load_records(paths, "E0S"))
    text = A.report(df, "Supplementary pilot E0S report (backbone A, C1-C5)", paths.reports, paths.figures, refs, banner,
                    draws=2000, extra_sections=[ceiling_check(df)])
    dfb = A.records_df(R.load_records(paths, "E0SB"))
    text += "\n\n" + A.report(dfb, "BackboneB supplementary pilot E0SB report (M0, SQP, MQP; C0-C6)", paths.reports,
                              paths.figures, refs, banner, draws=2000)
    (paths.reports / "pilot_supplement.md").write_text(text)
    st["stages"]["pilot_supplement"] = "done"
    save_state(paths, st)
    log(f"supplementary pilot report written: {paths.reports / 'pilot_supplement.md'}")
    return st["stages"]


def pilot_report(paths: Paths, cfg: dict, log=print) -> dict:
    df = A.records_df(R.load_records(paths, "E0"))
    refs = REF.build_references(paths, "development", ["D5", "D6"], TEMPLATES, [0, 1], log)
    stage_wall = sum(e.get("wall_seconds", 0) for e in read_jsonl(paths.outputs / "stage_log.jsonl") if e["label"] == "E0")
    tp = PW.throughput(df, stage_wall, cfg["concurrency"])
    power = PW.power_analysis(df, paths.outputs)
    cal = PW.calibrate_limits(df)
    gpus = 1 if cfg.get("mode") == "crc" else 2
    est = {r: PW.session_estimates(tp, r, gpus=gpus) for r in (3, 4, 5, 6)}
    feasible = [g for g in power["grid"] if g["sd_block_logit"] == 0.5 and g["power"] >= 0.8]
    rec_reps = min([g["reps"] for g in feasible], default=3)
    proposal = {"limits": cal["limits"], "calibration": cal, "recommended_repetitions": list(range(rec_reps)),
                "throughput": tp, "estimates": est, "power": power, "created": now_iso(),
                "note": "Edit FREEZE_REPETITIONS / FREEZE_LIMIT_OVERRIDES in the config cell to deviate; overrides are recorded."}
    write_json(paths.manifests / "freeze_proposal.json", proposal)
    banner = PILOT_BANNER + ("\n\n" + MOCK_BANNER if cfg["llm"]["mode"] == "mock" else "")
    extra = ["## 7. Usage percentiles (agentic runs ending SUBMITTED or ABSTAINED)\n" + A.md_table(A.usage_percentiles(df), "{:.0f}"),
             "## 8. Budget exhaustion\n" + A.md_table(df[df["system"] != "F"].groupby("system")["terminal"]
                                                      .apply(lambda t: (t == "BUDGET_EXCEEDED").mean()).to_frame("budget_exceeded_rate")),
             "## 9. Throughput and run-time estimates\n" + "```\n" + pd.Series(tp).to_string() + "\n```\n" +
             A.md_table(pd.DataFrame([{"repetitions": r, **v["runs"], **{k: v.get(k) for k in ("estimated_hours", "estimated_sessions", "estimated_gpu_hours")}} for r, v in est.items()])),
             "## 10. Power simulation (10-point VCR improvement, planned paired analysis)\n" + A.md_table(pd.DataFrame(power["grid"])) +
             f"\nAssumptions: {power['assumptions']}\n",
             "## 11. Freeze proposal\n" + f"Frozen limits by the prespecified rule: `{cal['limits']}` (n={cal['n_runs']}).\n\n"
             f"Protocol-text limits: `{PROTOCOL_LIMITS}`.\n\nRecommended repetitions: {list(range(rec_reps))}.\n",
             "## 12. Evaluator fixtures\n" + A.md_table(pd.DataFrame(read_json(paths.outputs / "evaluator_fixtures.json")["fixtures"]))]
    b = A.records_df(R.load_records(paths, "E0B"))
    if not b.empty:
        extra.append("## 13. Backbone-B smoke test (unscored)\n" + A.md_table(b.groupby("system").agg(
            runs=("run_id", "size"), verified=("V", "sum"), terminal=("terminal", lambda t: ", ".join(sorted(set(t)))))))
    exc = int(df["exceptions"].sum()) if not df.empty else 0
    extra.append(f"## 14. Unexpected agent-loop exceptions\n{exc} runs recorded an internal exception (should be 0).\n")
    extra.append(ceiling_check(df))
    text = A.report(df, "Pilot E0 report", paths.reports, paths.figures, refs, banner, draws=2000, extra_sections=extra)
    (paths.reports / "pilot.md").write_text(text)
    log(f"pilot report written: {paths.reports / 'pilot.md'}")
    return proposal


# --------------------------------------------------------------------------- freeze
def stage_freeze(paths: Paths, cfg: dict, pkg_dir: Path, confirm: bool, reps_override=None, limit_overrides=None,
                 enable_e7: bool = False, log=print) -> dict | None:
    st = state(paths)
    if (paths.manifests / "freeze.json").exists():
        log("protocol already frozen")
        return read_json(paths.manifests / "freeze.json")
    if st["stages"].get("pilot") != "done":
        raise RuntimeError("freeze requires a completed pilot")
    if (paths.manifests / "tier2_calibration_v2.json").exists():  # main-plan-v2.1 design
        prop = freeze_proposal_v21(paths, cfg, log)
        cfg["tier2_conditions"] = list(prop["tier2_conditions"])
    else:
        prop = read_json(paths.manifests / "freeze_proposal.json")
    if not confirm:
        log("Freeze proposal (set FREEZE_CONFIRMED = True to accept):")
        log(f"  limits: {prop['limits']}\n  recommended repetitions: {prop['recommended_repetitions']}")
        for r, e in prop["estimates"].items():
            log(f"  reps={r}: {e}")
        return None
    limits = dict(prop["limits"])
    overrides = {}
    for k, v in (limit_overrides or {}).items():
        overrides[k] = {"proposed": limits.get(k), "frozen": v}
        limits[k] = v
    reps = list(reps_override) if reps_override else prop["recommended_repetitions"]
    cfg["limits"] = limits
    cfg["repetitions"] = reps
    cfg["optional_budget_experiment"] = bool(enable_e7)
    write_json(paths.configs / "study.json", cfg)
    # build every formal instance once and record its content digest
    formal = formal_runs(cfg)
    _prepare(paths, formal, cfg, log)
    # ABC II.7-II.8 on the evaluation portfolio: the oracle must solve every formal Tier-2 instance before the freeze
    t2 = set(cfg.get("tier2_conditions") or [])
    t2_keys = sorted({(r["suite"], r["family"], r["template"], r["condition"], r["repetition"])
                      for r in formal if r["condition"] in t2})
    sol = FX.oracle_solvability(paths, t2_keys, log) if t2_keys else {"instances": 0, "failures": [], "all_solvable": True}
    write_json(paths.outputs / "tier2_solvability_formal.json", sol)
    if not sol["all_solvable"]:
        raise RuntimeError(f"oracle could not solve {len(sol['failures'])} formal Tier-2 instances "
                           f"{sol['failures'][:5]}; the protocol is NOT frozen")
    lock = read_json(paths.configs / "models.lock.json") if (paths.configs / "models.lock.json").exists() else {"mock": True}
    man = PW.write_freeze(paths, pkg_dir, cfg, {**prop, "overrides": overrides, "repetitions": reps}, lock)
    lines = ["# Protocol freeze", "", f"Created {man['created']}.", f"Protocol hash `{man['protocol_hash']}`; code hash `{man['code_hash']}`.",
             f"Limits: `{limits}`.", f"Repetitions: {reps}. Optional E7: {enable_e7}.",
             f"Tier-2 conditions (main-plan-v2.1): {cfg.get('tier2_conditions') or 'none'}.",
             f"Overrides of the prespecified rule: {overrides or 'none'}.", f"Formal runs scheduled: {len(formal)}.",
             f"Oracle solvability of formal Tier-2 instances: {sol['instances'] - len(sol['failures'])}/{sol['instances']}.",
             f"LLM mode: {cfg['llm']['mode']}.", "", "Primary analysis: " + man["primary"],
             "Secondary (Holm): " + ", ".join(man["secondary_holm_family"])]
    (paths.reports / "protocol_freeze.md").write_text("\n".join(lines) + "\n")
    st["stages"]["freeze"] = "done"
    save_state(paths, st)
    log("\n".join(lines))
    return man


FORMAL_PILOT_SOURCES = ("E0", "E0S", "E0X2")  # backbone-A pilots run on the conditions of the frozen design


def _stage_rate(paths: Paths, labels: tuple) -> float | None:
    """Measured seconds per run for pilot stages (latest complete stage_log entry per label)."""
    rows = read_jsonl(paths.outputs / "stage_log.jsonl") if (paths.outputs / "stage_log.jsonl").exists() else []
    wall, n = 0.0, 0
    for lab in labels:
        ent = [e for e in rows if e.get("label") == lab and e.get("completed", 0) >= 50]
        if ent:
            wall += ent[-1]["wall_seconds"]
            n += ent[-1]["completed"]
    return wall / n if n else None


def freeze_proposal_v21(paths: Paths, cfg: dict, log=print) -> dict:
    """main-plan-v2.1 freeze proposal. The frozen Tier-2 levels come from the second calibration (E0X2) by the
    prespecified rule. Limits, power and run time are recomputed by the same prespecified rules from the pilot runs
    whose conditions belong to the frozen design (Tier 1 C0-C6 plus the frozen Tier-2 levels; backbone A)."""
    cal2 = read_json(paths.manifests / "tier2_calibration_v2.json")
    if not all(v["complete"] and v["chosen"] for v in cal2["defects"].values()):
        raise RuntimeError("the second Tier-2 calibration (E0X2) is incomplete; run STAGE = 'calibrate2' first")
    chosen = [v["chosen"] for v in cal2["defects"].values()]
    design = list(CONDITIONS) + chosen
    df = A.records_df(sum((R.load_records(paths, e) for e in FORMAL_PILOT_SOURCES), []))
    df = df[df["condition"].isin(design) & (df["backbone"].isin(["A", "none"]))]
    lim = PW.calibrate_limits(df)
    power = PW.power_analysis(df, paths.outputs, n_conditions=len(design), out_name="power_simulation_v21.json")
    feasible = [g for g in power["grid"] if g["sd_block_logit"] == 0.5 and g["power"] >= 0.8]
    rec_reps = max(3, min([g["reps"] for g in feasible], default=3))
    spr1, spr2, sprb = _stage_rate(paths, ("E0", "E0S")), _stage_rate(paths, ("E0X2",)), _stage_rate(paths, ("E0SB",))
    gpus = 1 if cfg.get("mode") == "crc" else 2
    est = {r: PW.formal_estimates(spr1, spr2, r, len(CONDITIONS), len(chosen), sprb, gpus) for r in (3, 4, 5, 6)}
    old = paths.manifests / "freeze_proposal.json"
    keep = paths.manifests / "freeze_proposal_E0only.json"
    if old.exists() and not keep.exists():
        shutil.copy2(old, keep)
    prop = {"version": "v2.1", "tier2_conditions": chosen, "design_conditions": design,
            "pilot_sources": list(FORMAL_PILOT_SOURCES), "n_pilot_runs": int(len(df)),
            "limits": lim["limits"], "calibration": lim, "recommended_repetitions": list(range(rec_reps)),
            "estimates": est, "power": power, "tier2_calibration": cal2, "created": now_iso(),
            "note": "Edit FREEZE_REPETITIONS / FREEZE_LIMIT_OVERRIDES in the config cell to deviate; overrides are recorded."}
    write_json(old, prop)
    lines = ["# Freeze proposal (main-plan-v2.1)", "",
             f"Frozen Tier-2 conditions (prespecified rule on E0X2): {', '.join(chosen)}.",
             f"Design conditions: {', '.join(design)}.",
             f"Pilot runs used for limits and power: {len(df)} (sources {', '.join(FORMAL_PILOT_SOURCES)}, design conditions only).",
             f"Limits ({lim['rule']}): `{lim['limits']}`; p95 `{ {k: round(v) for k, v in lim['p95'].items()} }`.",
             f"Recommended repetitions: {list(range(rec_reps))}.", "", "| repetitions | runs | estimated GPU hours |", "|---|---|---|"]
    lines += [f"| {r} | {e['runs']['total']} | {e.get('estimated_gpu_hours')} |" for r, e in est.items()]
    (paths.reports / "freeze_proposal_v21.md").write_text("\n".join(lines) + "\n")
    log("\n".join(lines))
    return prop


def formal_experiment_runs(cfg: dict, exp: str) -> list:
    """Formal run list with the frozen Tier-2 conditions (main-plan-v2.1) in E1 and E4."""
    return R.experiment_runs(exp, cfg["repetitions"], cfg.get("rehearsal"), cfg.get("tier2_conditions"))


def formal_runs(cfg: dict) -> list:
    reps = cfg["repetitions"]
    reh = cfg.get("rehearsal")
    runs = formal_experiment_runs(cfg, "E1") + formal_experiment_runs(cfg, "E5")
    if cfg.get("optional_budget_experiment"):
        runs += formal_experiment_runs(cfg, "E7")
    runs += formal_experiment_runs(cfg, "E4")
    return runs


# --------------------------------------------------------------------------- formal
def stage_formal(paths: Paths, cfg: dict, clock: SessionClock, server, pkg_dir: Path, log=print) -> dict:
    st = state(paths)
    lock = read_json(paths.configs / "models.lock.json") if (paths.configs / "models.lock.json").exists() else {}
    PW.verify_freeze(paths, pkg_dir, cfg, lock, require_model_lock=cfg["llm"]["mode"] != "mock")
    reps, reh = cfg["repetitions"], cfg.get("rehearsal")
    plan = [("E1", "A"), ("E5", "A")] + ([("E7", "A")] if cfg.get("optional_budget_experiment") else []) + [("E4", "B")]
    for exp, backbone in plan:
        runs = formal_experiment_runs(cfg, exp)
        rn = R.Runner(paths, cfg, clock)
        if not rn.pending(runs):
            continue
        if not clock.may_start_new(120):
            log("not enough session time left to start the next experiment")
            break
        needs_llm = any(r["system"] != "F" for r in rn.pending(runs))
        if needs_llm:
            start_llm(paths, cfg, server, backbone, frozen=True, log=log)
        run_experiment(paths, cfg, clock, runs, exp, log)
        if needs_llm:
            stop_llm(paths, server, exp)
        if rn.pending(runs):
            log(f"{exp} not finished in this session; it resumes next session")
            save_state(paths, st)
            return {"complete": False}
    if any(R.Runner(paths, cfg, clock).pending(formal_experiment_runs(cfg, e)) for e, _ in plan):
        save_state(paths, st)
        return {"complete": False}
    # references, replay and final analysis
    fams = (reh or {}).get("families", FAMILIES)
    tmpls = (reh or {}).get("templates", TEMPLATES)
    refs = REF.build_references(paths, "evaluation", fams, tmpls, reps, log)
    e6 = stage_e6(paths, log)
    final_report(paths, cfg, refs, e6, log)
    st["stages"]["formal"] = "done"
    save_state(paths, st)
    return {"complete": True}


def stage_e6(paths: Paths, log=print) -> dict:
    out_path = paths.outputs / "e6_replay.json"
    if out_path.exists():
        return read_json(out_path)
    results = []
    for rec in R.load_records(paths, "E1") + R.load_records(paths, "E4"):
        sub = paths.submissions / rec["experiment_id"] / rec["run_id"]
        if (sub / "model.pkl").exists() and rec["terminal_state"] == "SUBMITTED":
            results.append(FX.replay_checks(paths, rec, sub, log))
    out = {"submissions_checked": len(results), "all_passed": all(r["all_passed"] for r in results) if results else None,
           "results": results}
    write_json(out_path, out)
    log(f"E6 replay/invariance: {len(results)} retained submissions checked; all passed = {out['all_passed']}")
    return out


def final_report(paths: Paths, cfg: dict, refs: dict, e6: dict, log=print):
    mock = cfg["llm"]["mode"] == "mock"
    banner = (MOCK_BANNER + "\n\n" if mock else "") + (REHEARSAL_BANNER if cfg.get("rehearsal") else "")
    e1 = A.records_df(R.load_records(paths, "E1"))
    e4 = A.records_df(R.load_records(paths, "E4"))
    e5 = A.records_df(R.load_records(paths, "E5"))
    e7 = A.records_df(R.load_records(paths, "E7"))
    extra = []
    if not e4.empty and not e1.empty:
        sub = e1[e1["system"].isin(["M0", "SQP", "MQP"]) & (e1["family"] + "-" + e1["template"]).isin(
            ["D1-T5", "D2-T2", "D3-T4", "D4-T6", "D5-T3", "D6-T1"])]
        both = pd.concat([sub.assign(bb="A"), e4.assign(bb="B")])
        t = both.groupby(["bb", "system"])["V"].agg(["size", "mean"]).unstack(0)
        t.columns = [f"{'runs' if a == 'size' else 'VCR'}_backbone_{b}" for a, b in t.columns]
        dB = A.block_differences(e4, {"MQP": 1, "M0": -1})
        extra.append("## 7. Second-backbone replication (prespecified subset; limited model robustness, not generalization)\n"
                     + A.md_table(t) + (f"\nBackbone B MQP - M0: {100 * A.estimate(dB):.1f} pp\n" if dB is not None else ""))
    if not e5.empty:
        extra.append("## 8. E5 refusal on unrecoverable tasks\n" + A.md_table(A.negative_table(e5)))
    if not e7.empty:
        extra.append("## 9. E7 optional budget sensitivity (exploratory)\n" + A.md_table(
            e7.pivot_table(index="system", columns="budget", values="V", aggfunc="mean")))
    fx = read_json(paths.outputs / "evaluator_fixtures.json") if (paths.outputs / "evaluator_fixtures.json").exists() else {}
    extra.append("## 10. Replay, invariance and evaluator-fixture audit\n"
                 f"Evaluator fixtures all passed: {fx.get('all_passed')}. E6 retained submissions checked: "
                 f"{e6.get('submissions_checked')}; all passed: {e6.get('all_passed')}.\n")
    acct = run_accounting(paths, cfg)
    extra.append("## 11. Run accounting\n" + A.md_table(pd.DataFrame(acct).T, "{:.0f}"))
    gpu = read_jsonl(paths.outputs / "gpu_accounting.jsonl")
    if gpu:
        extra.append("## 12. GPU accounting (server sessions)\n" + A.md_table(pd.DataFrame(gpu)))
    tiers = A.tier_sections(e1, draws=10000)
    if tiers:
        extra.append(tiers)
    if not e4.empty and cfg.get("tier2_conditions"):
        extra.append("## Backbone B by tier\n" + A.md_table(e4.assign(tier=e4["condition"].map(A.tier_of))
                                                         .pivot_table(index="system", columns="tier", values="V", aggfunc="mean")))
    text = A.report(e1, "Final E1 report (backbone A)", paths.reports, paths.figures, refs, banner,
                    draws=10000, extra_sections=extra)
    (paths.reports / "final_report.md").write_text(text)
    log(f"final report written: {paths.reports / 'final_report.md'}")


def run_accounting(paths: Paths, cfg: dict) -> dict:
    out = {}
    for exp in ["E0", "E0B", "E1", "E4", "E5", "E7"]:
        if exp in ("E0",):
            runs = R.experiment_runs("E0", [0, 1])
        elif exp == "E0B":
            runs = R.experiment_runs("E0B", [0])
        else:
            if exp == "E7" and not cfg.get("optional_budget_experiment"):
                continue
            runs = formal_experiment_runs(cfg, exp)
        recs = {r["run_id"] for r in R.load_records(paths, exp)}
        att = list((paths.attempts / exp).glob("*.json")) if (paths.attempts / exp).exists() else []
        out[exp] = {"scheduled": len(runs), "recorded": len(recs & {r["run_id"] for r in runs}),
                    "pending": len({r["run_id"] for r in runs} - recs), "infrastructure_attempts": len(att)}
    return out


def session_summary(paths: Paths, cfg: dict, clock: SessionClock, log=print) -> dict:
    acct = run_accounting(paths, cfg)
    st = state(paths)
    size = dir_size_bytes(paths.state) / 2**20
    nxt = "run the pilot"
    if st["stages"].get("pilot") == "done":
        nxt = "review reports/pilot.md, then set FREEZE_CONFIRMED = True and run again"
    if st["stages"].get("freeze") == "done":
        nxt = ("attach this output as input and run again to continue the formal experiments" if cfg.get("mode") == "kaggle"
               else "run again to continue the formal experiments (completed runs are kept and skipped)")
    if st["stages"].get("formal") == "done":
        nxt = "study complete: see reports/final_report.md"
    st["sessions"].append({"ended": now_iso(), "hours": round(clock.elapsed() / 3600, 2), "accounting": acct})
    save_state(paths, st)
    release_session(paths)
    summary = {"stages": st["stages"], "accounting": acct, "state_size_mb": round(size, 1), "next": nxt}
    log(pd.DataFrame(acct).T.to_string())
    note = " (Kaggle output limit 20 GB)" if cfg.get("mode") == "kaggle" else ""
    log(f"stages: {st['stages']} | saved state size: {size:.1f} MB{note}\nNEXT: {nxt}")
    return summary
