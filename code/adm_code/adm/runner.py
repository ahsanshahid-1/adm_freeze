"""Experiment manifests, scheduling, per-run worker processes, evaluation and resumable records."""
from __future__ import annotations

import gzip
import json
import multiprocessing as mp
import os
import random
import resource
import shutil
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .core import (AGENTIC_SYSTEMS, CONDITIONS, FAMILIES, NEGATIVE_CONDITIONS, REPLICATION_SYSTEMS,
                   REPLICATION_TASKS, SYSTEM_SPEC, SYSTEMS, TEMPLATES, TIER2_CONDITIONS, TIER2_DESIGN, Paths, SessionClock,
                   derive_seed, dumps,
                   instance_dirs, now_iso, read_json, write_json, write_json_once, sha256_tree, json_hash, small_seed)

THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
               "VECLIB_MAXIMUM_THREADS")


def set_thread_caps(n: int = 1) -> None:
    """Numerical-library threads are capped consistently for every worker (Section 10.2)."""
    for v in THREAD_VARS:
        os.environ[v] = str(n)


# --------------------------------------------------------------------------- manifests
def run_id(r: dict) -> str:
    bid = f"-{r['budget_profile']}" if r.get("budget_profile", "standard") != "standard" else ""
    return f"{r['experiment']}-{r['family']}-{r['template']}-{r['condition']}-r{r['repetition']}-{r['system']}-{r['backbone']}{bid}"


def _block(exp, suite, fam, tmpl, cond, rep, systems, backbone, budget="standard"):
    rng = random.Random(derive_seed("agent", fam, f"{fam}-{tmpl}", rep, f"order:{exp}:{cond}:{budget}"))
    order = list(systems)
    rng.shuffle(order)
    out = []
    for k, s in enumerate(order):
        r = {"experiment": exp, "suite": suite, "family": fam, "template": tmpl, "condition": cond, "repetition": rep,
             "system": s, "backbone": backbone if s != "F" else "none", "block": f"{exp}/{fam}-{tmpl}/{cond}/r{rep}/{budget}",
             "order_in_block": k, "budget_profile": budget}
        r["run_id"] = run_id(r)
        out.append(r)
    return out


def experiment_runs(exp: str, repetitions: list, rehearsal: dict | None = None, tier2: list | None = None) -> list:
    """Run lists for each experiment (Section 12). ``rehearsal`` restricts the design for local testing.
    ``tier2`` lists the frozen Tier-2 conditions (main-plan-v2.1 Section 7.6) added to E1 and E4."""
    fams, tmpls, conds = FAMILIES, TEMPLATES, CONDITIONS
    if rehearsal:
        fams, tmpls, conds = rehearsal.get("families", fams), rehearsal.get("templates", tmpls), rehearsal.get("conditions", conds)
    conds = list(conds) + [c for c in (tier2 or []) if c not in conds]
    runs = []
    if exp == "E0S":  # supplementary pilot (recorded separately, Section 12 E0): development tasks under C1-C5
        for fam in ["D5", "D6"]:
            for t in TEMPLATES:
                for c in ["C1", "C2", "C3", "C4", "C5"]:
                    for r in repetitions:
                        runs += _block("E0S", "development", fam, t, c, r, SYSTEMS, "A")
        return runs
    if exp == "E0X":  # Tier-2 calibration pilot: development tasks, X1-X3 at three levels, one repetition, backbone A.
        # Template is the outer loop so that a partial session still covers every defect and level evenly.
        for t in TEMPLATES:
            for fam in ["D5", "D6"]:
                for c in TIER2_CONDITIONS:
                    for r in repetitions:
                        runs += _block("E0X", "development", fam, t, c, r, SYSTEMS, "A")
        return runs
    if exp == "E0X2":  # second Tier-2 calibration (X2, X3, X4 at three levels), backbone A, repetitions 1 and 2
        for t in TEMPLATES:
            for r in repetitions:
                for fam in ["D5", "D6"]:
                    for c in TIER2_DESIGN:
                        runs += _block("E0X2", "development", fam, t, c, r, SYSTEMS, "A")
        return runs
    if exp == "E0SB":  # supplementary pilot, backbone B: development tasks, C0-C6, replication systems (E4 headroom)
        for fam in ["D5", "D6"]:
            for t in TEMPLATES:
                for c in CONDITIONS:
                    for r in repetitions:
                        runs += _block("E0SB", "development", fam, t, c, r, REPLICATION_SYSTEMS, "B")
        return runs
    if exp == "E0B":  # unscored backbone-B smoke test during the pilot
        for fam, t, c in [("D5", "T2", "C0"), ("D6", "T4", "C6")]:
            runs += _block("E0B", "development", fam, t, c, 0, REPLICATION_SYSTEMS, "B")
        return runs
    if exp == "E0":
        for fam in ["D5", "D6"]:
            for t in TEMPLATES if not rehearsal else tmpls:
                for c in ["C0", "C6"]:
                    for r in [0, 1]:
                        runs += _block("E0", "development", fam, t, c, r, SYSTEMS, "A")
    elif exp == "E1":
        for r in repetitions:
            for fam in fams:
                for t in tmpls:
                    for c in conds:
                        runs += _block("E1", "evaluation", fam, t, c, r, SYSTEMS, "A")
    elif exp in ("E4", "E5", "E7"):
        tasks = [x for x in REPLICATION_TASKS if (x.split("-")[0] in fams and x.split("-")[1] in tmpls)] if rehearsal else REPLICATION_TASKS
        for r in repetitions:
            for tk in tasks:
                fam, t = tk.split("-")
                if exp == "E4":
                    for c in conds:
                        runs += _block("E4", "evaluation", fam, t, c, r, REPLICATION_SYSTEMS, "B")
                elif exp == "E5":
                    for c in NEGATIVE_CONDITIONS:
                        runs += _block("E5", "evaluation", fam, t, c, r, SYSTEMS, "A")
                else:
                    for c in ["C0", "C2", "C6"]:  # E7 budget sensitivity stays on Tier 1 (unchanged design)
                        if r > 1:
                            continue
                        for b in ["half", "double"]:
                            runs += _block("E7", "evaluation", fam, t, c, r, REPLICATION_SYSTEMS, "A", b)
    return runs


def budget_for(limits: dict, profile: str) -> dict:
    if profile == "standard":
        return dict(limits)
    f = 0.5 if profile == "half" else 2.0
    out = dict(limits)
    for k in ("aggregate_tokens", "model_calls", "tool_calls", "wall_seconds"):
        out[k] = int(round(limits[k] * f))
    return out  # pipeline_evaluations and repair_cycles unchanged


def run_seeds(r: dict) -> dict:
    tk = f"{r['family']}-{r['template']}"
    return {"corruption": derive_seed("corruption", r["family"], tk, r["repetition"], r["condition"]),
            "estimator": small_seed(derive_seed("estimator", r["family"], tk, r["repetition"], r["condition"])),
            "agent": small_seed(derive_seed("agent", r["family"], tk, r["repetition"], r["condition"])),
            "split": derive_seed("split", r["family"], r["suite"], r["repetition"], "outer")}


# --------------------------------------------------------------------------- worker
def worker_main(job_path: str, result_path: str, fit_slot) -> None:
    """Executed in a fresh spawned process for each run."""
    t0 = time.time()
    try:
        job = read_json(job_path)
        from .agents import execute_run
        from .core import Paths, instance_dirs
        from .llm import MockLLM, VLLMClient
        from .tools import Budget, ToolSession
        r = job["run"]
        paths = Paths.from_dict(job["paths"])
        dirs = instance_dirs(paths, r["suite"], r["family"], r["template"], r["condition"], r["repetition"])
        spec = SYSTEM_SPEC[r["system"]]
        budget = Budget(job["limits"])
        sub_dir = Path(job["submission_dir"])
        if sub_dir.exists():
            shutil.rmtree(sub_dir)
        session = ToolSession(r["run_id"], dirs["visible"], dirs["trusted"], sub_dir, spec, budget, job["seeds"],
                              fit_slot=fit_slot)
        llm = None
        if spec["planner"] != "fixed":
            if job["llm"]["mode"] == "mock":
                llm = MockLLM(job["seeds"]["agent"] + hash_system(r["system"]), invalid_rate=job["llm"].get("invalid_rate", 0.03))
            else:
                llm = VLLMClient(job["llm"]["base_url"], job["llm"]["served_model"], job["generation"],
                                 job["llm"].get("structured_mode", "response_format"))
        out = execute_run(session, r["system"], spec, llm, job["generation"], job["seeds"]["agent"])
        trace = out.pop("trace")
        tp = Path(job["trace_path"])
        tp.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(tp, "wt", encoding="utf-8") as f:
            for e in trace:
                f.write(dumps(e) + "\n")
        out["usage"] = budget.usage()
        out["exception_events"] = sum(1 for e in trace if e.get("event") == "exception")
        out["peak_worker_memory_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 if sys.platform != "darwin" else 1024 * 1024)
        out["worker_seconds"] = round(time.time() - t0, 3)
        write_json(result_path, out)
    except Exception:
        write_json(result_path, {"terminal_state": "INFRASTRUCTURE_ERROR", "error": traceback.format_exc()[-3000:],
                                 "usage": {}, "worker_crash": True})


def hash_system(code: str) -> int:
    # mock only: differentiate personas between systems deterministically
    return sum(ord(c) * (i + 1) for i, c in enumerate(code)) * 7919


# --------------------------------------------------------------------------- scheduler
class Runner:
    def __init__(self, paths: Paths, config: dict, clock: SessionClock, log=print):
        self.paths, self.cfg, self.clock, self.log = paths, config, clock, log
        set_thread_caps()
        self.ctx = mp.get_context("spawn")
        self.fit_slot = self.ctx.Semaphore(config.get("fit_slots", 3))
        self.jobs_dir = paths.work / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def record_path(self, r: dict) -> Path:
        return self.paths.runs / r["experiment"] / f"{r['run_id']}.json"

    def attempts(self, r: dict) -> list:
        d = self.paths.attempts / r["experiment"]
        return sorted(d.glob(f"{r['run_id']}__a*.json")) if d.exists() else []

    def stale_markers(self, runs: list):
        """A start marker without a result means the previous session ended abruptly: record it as an
        infrastructure attempt so that it is retried at most once (Section 13.4)."""
        for r in runs:
            d = self.paths.attempts / r["experiment"]
            for m in (d.glob(f"{r['run_id']}__a*.started") if d.exists() else []):
                res = m.with_suffix(".json")
                if not res.exists() and not self.record_path(r).exists():
                    write_json(res, {"run_id": r["run_id"], "terminal_state": "INFRASTRUCTURE_ERROR",
                                     "error": "session ended while the run was in progress", "attempt": m.stem.split("__a")[-1]})
                m.unlink(missing_ok=True)

    def pending(self, runs: list) -> list:
        out = []
        for r in runs:
            if self.record_path(r).exists():
                continue
            out.append(r)
        return out

    def _job(self, r: dict, attempt: int) -> dict:
        llm = self.cfg["llm"]
        lim = budget_for(self.cfg["limits"], r.get("budget_profile", "standard"))
        return {"run": r, "paths": self.paths.to_dict(), "limits": lim, "generation": self.cfg["generation"],
                "seeds": run_seeds(r),
                "llm": {**llm, "served_model": llm.get("served_models", {}).get(r["backbone"], llm.get("served_model"))},
                "submission_dir": str(self.paths.work / "submissions" / r["run_id"]),
                "trace_path": str(self.paths.traces / r["experiment"] / f"{r['run_id']}__a{attempt}.jsonl.gz"),
                "attempt": attempt}

    def execute(self, runs: list, concurrency: int, evaluator_workers: int = 1, on_progress=None,
                retain_ids: set | None = None) -> dict:
        from .evaluator import evaluate_safe
        self.retain_ids = set(retain_ids or ())
        self.stale_markers(runs)
        todo = self.pending(runs)
        stats = {"scheduled": len(runs), "pending_at_start": len(todo), "completed": 0, "infra_attempts": 0,
                 "stopped_for_time": False}
        if not todo:
            return stats
        active: dict = {}
        queue = list(todo)
        eval_pool = ProcessPoolExecutor(max_workers=evaluator_workers, mp_context=self.ctx)
        eval_futs: dict = {}
        avg_dur = [self.cfg["limits"]["wall_seconds"] / 4]
        t_last = time.time()
        try:
            while queue or active or eval_futs:
                # dispatch
                while queue and len(active) < concurrency:
                    if not self.clock.may_start_new(min(avg_dur[0], self.cfg["limits"]["wall_seconds"])):
                        stats["stopped_for_time"] = True
                        queue = []
                        break
                    r = queue.pop(0)
                    att = len(self.attempts(r)) + 1
                    job = self._job(r, att)
                    jp = self.jobs_dir / f"{r['run_id']}__a{att}.job.json"
                    rp = self.jobs_dir / f"{r['run_id']}__a{att}.result.json"
                    rp.unlink(missing_ok=True)
                    write_json(jp, job)
                    marker = self.paths.attempts / r["experiment"] / f"{r['run_id']}__a{att}.started"
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text(now_iso())
                    p = self.ctx.Process(target=worker_main, args=(str(jp), str(rp), self.fit_slot), daemon=True)
                    p.start()
                    active[r["run_id"]] = {"run": r, "proc": p, "start": time.time(), "attempt": att, "job": job,
                                           "result": rp, "marker": marker, "queued_at": now_iso()}
                # collect finished runs
                for rid in list(active):
                    a = active[rid]
                    p = a["proc"]
                    hard = a["job"]["limits"]["wall_seconds"] * 1.5 + 180
                    killed = None
                    if p.is_alive():
                        if time.time() - a["start"] > hard:
                            killed = "run exceeded the hard wall-clock guard"
                        elif self.clock.must_stop():
                            killed = "session time limit reached"
                        if killed:
                            p.kill()
                            p.join(10)
                        else:
                            continue
                    p.join(1)
                    del active[rid]
                    res = read_json(a["result"]) if a["result"].exists() else {
                        "terminal_state": "INFRASTRUCTURE_ERROR", "error": killed or "worker exited without a result", "usage": {}}
                    if killed and res.get("terminal_state") != "INFRASTRUCTURE_ERROR":
                        res = {"terminal_state": "INFRASTRUCTURE_ERROR", "error": killed, "usage": res.get("usage", {})}
                    dur = time.time() - a["start"]
                    avg_dur[0] = 0.8 * avg_dur[0] + 0.2 * dur
                    res["wall_including_queue_seconds"] = round(dur, 3)
                    self._finish(a, res, eval_pool, eval_futs, evaluate_safe, stats, queue)
                # collect evaluations
                for rid in list(eval_futs):
                    fut, a, res = eval_futs[rid]
                    if fut.done():
                        del eval_futs[rid]
                        try:
                            ev = fut.result()
                        except Exception as e:
                            ev = {"run_id": rid, "external_failure_codes": ["EVALUATOR_ERROR"], "evaluator_error": str(e)[:500],
                                  "verified_completion": 0}
                        self._write_record(a, res, ev)
                        stats["completed"] += 1
                if on_progress and time.time() - t_last > 30:
                    t_last = time.time()
                    on_progress(stats, len(queue), len(active), len(eval_futs))
                if self.clock.must_stop() and not active:
                    # leave remaining evaluations to complete quickly
                    pass
                time.sleep(0.2)
        finally:
            eval_pool.shutdown(wait=True, cancel_futures=False)
        return stats

    def _finish(self, a, res, eval_pool, eval_futs, evaluate_safe, stats, queue):
        r = a["run"]
        a["marker"].unlink(missing_ok=True)
        if res.get("terminal_state") == "INFRASTRUCTURE_ERROR":
            stats["infra_attempts"] += 1
            att_path = self.paths.attempts / r["experiment"] / f"{r['run_id']}__a{a['attempt']}.json"
            write_json(att_path, {"run_id": r["run_id"], "attempt": a["attempt"], **{k: v for k, v in res.items() if k != "gate_log"}})
            n_att = len(self.attempts(r))
            if n_att < 2 and not self.clock.must_stop():
                queue.insert(0, r)  # one automatic retry with the same frozen inputs
                return
            if n_att < 2:
                return  # retried next session
        dirs = instance_dirs(self.paths, r["suite"], r["family"], r["template"], r["condition"], r["repetition"])
        neg = None
        if r["condition"] in NEGATIVE_CONDITIONS:
            neg = "REQUIRED_SOURCE_MISSING" if r["condition"] == "N1" else "AMBIGUOUS_AUTHORITY"
        job = {"run_id": r["run_id"], "terminal_state": res.get("terminal_state"),
               "abstention_reason": res.get("abstention_reason"),
               "instance": {k: str(v) for k, v in dirs.items()}, "submission_dir": a["job"]["submission_dir"],
               "usage": res.get("usage", {}), "limits": a["job"]["limits"], "negative": neg,
               "retain_model": r["run_id"] in getattr(self, "retain_ids", set())}
        eval_futs[r["run_id"]] = (eval_pool.submit(evaluate_safe, job), a, res)

    def _write_record(self, a: dict, res: dict, ev: dict):
        r = a["run"]
        job = a["job"]
        u = res.get("usage", {}) or {}
        llm = self.cfg["llm"]
        model_lock = self.cfg.get("model_lock", {}).get(r["backbone"], {})
        rec = {
            "run_id": r["run_id"], "protocol_hash": self.cfg.get("protocol_hash"), "code_hash": self.cfg.get("code_hash"),
            "experiment_id": r["experiment"], "suite": r["suite"], "dataset_id": r["family"],
            "task_id": f"{r['family']}-{r['template']}", "template_id": r["template"], "condition_id": r["condition"],
            "repetition_id": r["repetition"], "system_id": r["system"], "backbone_id": r["backbone"],
            "budget_profile": r.get("budget_profile", "standard"), "block": r["block"], "order_in_block": r["order_in_block"],
            "llm_mode": llm["mode"], "model_revision": model_lock.get("revision"), "model_repo": model_lock.get("repo"),
            "tokenizer_hash": model_lock.get("tokenizer_hash"),
            "data_hashes": self.cfg.get("instance_hashes", {}).get(f"{r['suite']}/{r['family']}-{r['template']}/{r['condition']}/r{r['repetition']}"),
            "split_hash": self.cfg.get("split_hashes", {}).get(f"{r['suite']}/{r['family']}/r{r['repetition']}", {}).get("hash"),
            "corruption_seed": job["seeds"]["corruption"], "estimator_seed": job["seeds"]["estimator"],
            "agent_seed": job["seeds"]["agent"], "start_time": a["queued_at"], "attempt": a["attempt"],
            "infrastructure_retry_count": a["attempt"] - 1,
            "terminal_state": res.get("terminal_state"), "abstention_reason": res.get("abstention_reason"),
            "run_error": res.get("error"), "exception_events": res.get("exception_events", 0),
            "verified_completion": ev.get("verified_completion"), "external_failure_codes": ev.get("external_failure_codes"),
            "first_failure": ev.get("first_failure"),
            "correct_refusal": ev.get("correct_refusal"), "false_submission": ev.get("false_submission"),
            "selected_candidate": (res.get("submission") or {}).get("candidate"),
            "test_metrics": ev.get("test_metrics"), "test_prediction_coverage": ev.get("test_prediction_coverage"),
            "test_value_match_rate": ev.get("test_value_match_rate"), "record_integrity_rate": ev.get("record_integrity_rate"),
            "data_management": ev.get("data_management"), "version_selection_correct": ev.get("version_selection_correct"),
            "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
            "aggregate_tokens": u.get("aggregate_tokens"), "model_calls": u.get("model_calls"),
            "tool_calls": u.get("tool_calls"), "gate_calls": u.get("gate_calls"), "repair_cycles": u.get("repair_cycles"),
            "pipeline_evaluations": u.get("pipeline_evaluations"), "fit_count": u.get("fit_count"),
            "active_seconds": u.get("active_seconds"), "queue_seconds": u.get("wait_seconds"),
            "llm_seconds": u.get("llm_seconds"), "wall_including_queue_seconds": res.get("wall_including_queue_seconds"),
            "peak_worker_memory_mb": res.get("peak_worker_memory_mb"),
            "server_gpu_seconds": None, "server_gpu_seconds_reason": "shared server; see per-experiment GPU accounting",
            "monetary_cost": None, "monetary_cost_reason": f"{self.cfg.get('mode', 'kaggle')} compute has no per-run tariff; GPU-seconds reported instead",
            "replay_status": ev.get("replay_status"), "evaluator_seconds": ev.get("evaluator_seconds"),
            "gate_log": res.get("gate_log"), "limits": job["limits"],
            "predicates": ev.get("predicates"), "evaluator_error": ev.get("evaluator_error"),
            "trace_path": str(Path(job["trace_path"]).relative_to(self.paths.state)),
        }
        # persist the small submission artifacts; the pickled model is deleted after evaluation
        sub = Path(job["submission_dir"])
        keep = self.paths.submissions / r["experiment"] / r["run_id"]
        if sub.exists():
            keep.mkdir(parents=True, exist_ok=True)
            for fn in ("bundle.json", "graph.json", "model_choice.json", "findings.json", "trusted_provenance.jsonl",
                       "test_predictions.parquet", "model.pkl"):
                if (sub / fn).exists():
                    shutil.copy2(sub / fn, keep / fn)
            shutil.rmtree(sub, ignore_errors=True)
        write_json_once(self.record_path(r), rec)


def load_records(paths: Paths, experiment: str | None = None) -> list:
    out = []
    roots = [paths.runs / experiment] if experiment else sorted(paths.runs.glob("*"))
    for d in roots:
        if d.is_dir():
            for p in sorted(d.glob("*.json")):
                out.append(read_json(p))
    return out
