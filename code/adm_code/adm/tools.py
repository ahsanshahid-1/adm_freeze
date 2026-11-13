"""Instrumented tool layer shared by every system (Section 13). Trusted wrappers, not LLM
statements, record sources, dependencies, row counts, parameters and hashes."""
from __future__ import annotations

import json
import pickle
import threading
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import gates, modeling
from .core import (ABSTENTION_REASONS, append_jsonl, derive_seed, df_hash, dumps, json_hash, read_json,
                   sha256_file, write_json)
from .datasets import cv_splits
from .engine import CatalogView, GraphError, ResolutionError, execute, summarize, validate_graph

TOOL_NAMES = ["list_sources", "inspect_schema", "profile_data", "query_data", "materialize_features",
              "fit_evaluate", "quality_check", "provenance_check", "submit", "abstain"]
MAX_OBS_CHARS = 3500


class BudgetExceeded(Exception):
    pass


class Terminal(Exception):
    """Raised by submit/abstain to end a run."""

    def __init__(self, state: str, info: dict):
        super().__init__(state)
        self.state, self.info = state, info


class Budget:
    def __init__(self, limits: dict, clock=time.time):
        self.limits = dict(limits)
        self.clock = clock
        self.start = clock()
        self.tokens_in = 0
        self.tokens_out = 0
        self.model_calls = 0
        self.tool_calls = 0
        self.gate_calls = 0
        self.repairs = 0
        self.evaluations = 0
        self.fits = 0
        self.wait_seconds = 0.0
        self.llm_seconds = 0.0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    def active_seconds(self) -> float:
        return self.clock() - self.start - self.wait_seconds

    def exceeded(self) -> str | None:
        L = self.limits
        if self.tokens > L["aggregate_tokens"]:
            return "aggregate_tokens"
        if self.model_calls > L["model_calls"]:
            return "model_calls"
        if self.tool_calls > L["tool_calls"]:
            return "tool_calls"
        if self.active_seconds() > L["wall_seconds"]:
            return "wall_seconds"
        return None

    def check(self):
        r = self.exceeded()
        if r:
            raise BudgetExceeded(r)

    def remaining(self) -> dict:
        L = self.limits
        return {"tokens": L["aggregate_tokens"] - self.tokens, "model_calls": L["model_calls"] - self.model_calls,
                "tool_calls": L["tool_calls"] - self.tool_calls, "repairs": L["repair_cycles"] - self.repairs,
                "evaluations": L["pipeline_evaluations"] - self.evaluations,
                "seconds": round(L["wall_seconds"] - self.active_seconds(), 1)}

    def usage(self) -> dict:
        return {"input_tokens": self.tokens_in, "output_tokens": self.tokens_out, "aggregate_tokens": self.tokens,
                "model_calls": self.model_calls, "tool_calls": self.tool_calls, "gate_calls": self.gate_calls,
                "repair_cycles": self.repairs, "pipeline_evaluations": self.evaluations, "fit_count": self.fits,
                "active_seconds": round(self.active_seconds(), 3), "wait_seconds": round(self.wait_seconds, 3),
                "llm_seconds": round(self.llm_seconds, 3)}


def _truncate(obj, limit: int = MAX_OBS_CHARS) -> str:
    s = dumps(obj)
    if len(s) <= limit:
        return s
    return s[: limit - 40] + f' ..."[truncated {len(s) - limit + 40} chars]"'


class ToolSession:
    """One run's tool environment. Holds no reference to the private evaluation directory."""

    def __init__(self, run_id: str, visible: Path, trusted: Path, submission_dir: Path, system: dict,
                 budget: Budget, seeds: dict, fit_slot=None, query_timeout: float = 10.0):
        self.run_id = run_id
        self.visible, self.trusted = Path(visible), Path(trusted)
        self.sub_dir = Path(submission_dir)
        self.sub_dir.mkdir(parents=True, exist_ok=True)
        self.system = system
        self.q, self.p = bool(system["q"]), bool(system["p"])
        self.budget = budget
        self.seeds = seeds
        self.fit_slot = fit_slot
        self.query_timeout = query_timeout
        self.contract = read_json(self.visible / "contract.json")
        self.catalog = read_json(self.visible / "catalog.json")
        self.manifest = read_json(self.visible / "visible_partition_manifest.json")
        self.labels = pd.read_parquet(self.trusted / "labels.parquet")
        self.views = {p: CatalogView(self.visible, self.catalog, p) for p in ("train", "validation")}
        self.handles: dict = {}
        self.fit_cache: dict = {}
        self.fit_results: list = []
        self.provenance: list = []
        self.prov_path = self.sub_dir / "trusted_provenance.jsonl"
        self.last_failed = False
        self.blocked_attempts: list = []
        self.gate_log: list = []
        self._duck = None
        split = self.labels[["observation_id", "partition", "fold"]].copy()
        self.cv = cv_splits(split, self.contract_rule())

    def contract_rule(self) -> str:
        return self.manifest["cv_policy"]["rule"]

    # ------------------------------------------------------------------ provenance
    def _prov(self, activity: str, **kw):
        rec = {"seq": len(self.provenance), "time": round(time.time(), 3), "activity": activity,
               "agent": f"tool:{activity}", **kw}
        self.provenance.append(rec)
        append_jsonl(self.prov_path, rec)

    # ------------------------------------------------------------------ dispatch
    def call(self, name: str, args: dict, charge: bool = True) -> dict:
        """Execute one agent-requested tool call. Returns an observation dict."""
        if name not in TOOL_NAMES:
            return {"ok": False, "error": f"unknown tool {name!r}; tools: {TOOL_NAMES}"}
        if charge:
            self.budget.tool_calls += 1
            self.budget.check()
        fn = getattr(self, "t_" + name)
        try:
            res = fn(**(args or {}))
            return {"ok": "error" not in res, **res}
        except Terminal:
            raise
        except BudgetExceeded:
            raise
        except TypeError as e:
            return {"ok": False, "error": f"bad arguments for {name}: {e}"}
        except (GraphError, ValueError, KeyError, duckdb.Error) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ------------------------------------------------------------------ tools
    def t_list_sources(self) -> dict:
        out = []
        for name, t in sorted(self.catalog["tables"].items()):
            shards: dict = {}
            for f in t["files"]:
                for s in f["shards"]:
                    shards.setdefault(s, []).append(f["version"])
            multi = sorted(s for s, v in shards.items() if len(v) > 1)
            sr = self.catalog.get("shard_representations", {}).get(name, {})
            out.append({"table": name, "grain": t["grain"], "key": t["key"], "description": t["description"],
                        "columns": list(t["columns"]), "versions": t["versions"], "files": len(t["files"]),
                        "shards": len(shards), "shards_with_multiple_candidates": len(multi),
                        "shards_with_declared_representations": len(sr)})
        auth = [{"record_id": a["record_id"], "registry": a["registry"], "table": a["table"], "as_of": a["as_of"],
                 "version": a["version"], "shards": len(a["shard_hashes"])} for a in self.catalog["authority"]]
        self._prov("list_sources")
        return {"tables": out, "authority": auth, "alias_table": self.catalog.get("alias_table"),
                "relationships": self.catalog.get("relationships", [])}

    def t_inspect_schema(self, table: str) -> dict:
        t = self.catalog["tables"].get(table)
        if t is None:
            raise KeyError(f"unknown table {table!r}")
        files = [{k: f[k] for k in ("file_id", "version", "snapshot_date", "modified", "partition", "rows")}
                 | {"shards": len(f["shards"])} for f in t["files"]]
        reps = {c: self.catalog["representations"][c] for c in t["columns"] if c in self.catalog.get("representations", {})}
        sr = self.catalog.get("shard_representations", {}).get(table, {})
        auth = [{"record_id": a["record_id"], "registry": a["registry"], "version": a["version"],
                 "as_of": a["as_of"], "shards": len(a["shard_hashes"])} for a in self.catalog["authority"] if a["table"] == table]
        self._prov("inspect_schema", used=[table])
        return {"table": table, "grain": t["grain"], "key": t["key"], "columns": t["columns"], "files": files[:16],
                "representations": reps, "shard_representations": dict(list(sr.items())[:12]),
                "shard_representations_total": len(sr), "authority": auth}

    def t_profile_data(self, table: str, policy: str = "authoritative", partition: str = "train",
                       sample_rows: int = 5) -> dict:
        if partition not in self.views:
            raise ValueError("partition must be 'train' or 'validation'")
        from .engine import resolve
        df, rec = resolve(self.views[partition], table, policy)
        sample_rows = max(0, min(int(sample_rows), 20))
        cols = {}
        for c in df.columns:
            s = df[c]
            info = {"dtype": str(s.dtype), "nulls": int(s.isna().sum()), "distinct": int(s.nunique())}
            if pd.api.types.is_numeric_dtype(s):
                info.update({"min": float(s.min()) if s.notna().any() else None,
                             "max": float(s.max()) if s.notna().any() else None,
                             "mean": float(s.mean()) if s.notna().any() else None})
            else:
                vals = s.dropna().astype(str)
                info["examples"] = vals.head(3).tolist()
                info["prefixed_values"] = int(vals.str.startswith("value:").sum())
            cols[c] = info
        dup = int(df.duplicated().sum())
        keydup = int(df["observation_id"].duplicated().sum()) if "observation_id" in df.columns and \
            self.catalog["tables"][table]["grain"] == "observation" else None
        self._prov("profile_data", used=[f"{s}:{v['file_id']}" for s, v in rec["shards"].items()], policy=policy)
        smp = df.head(sample_rows)
        return {"table": table, "partition": partition, "policy": policy, "rows": int(len(df)),
                "exact_duplicate_rows": dup, "duplicate_keys": keydup,
                "versions_loaded": sorted({v["version"] for v in rec["shards"].values()}),
                "columns": cols, "sample": smp.astype(object).where(smp.notna(), None).to_dict("records")}

    def _duckdb(self):
        if self._duck is None:
            con = duckdb.connect(":memory:")
            for name, t in self.catalog["tables"].items():
                for f in t["files"]:
                    df = pd.read_parquet(self.visible / f["path"])
                    con.register("tmp_df", df)
                    con.execute(f'CREATE TABLE "{f["file_id"]}" AS SELECT * FROM tmp_df')
                    con.unregister("tmp_df")
            con.execute("SET enable_external_access=false")
            try:
                con.execute("SET autoload_known_extensions=false")
                con.execute("SET autoinstall_known_extensions=false")
            except duckdb.Error:
                pass
            con.execute("SET lock_configuration=true")
            self._duck = con
        return self._duck

    def t_query_data(self, sql: str, max_rows: int = 50) -> dict:
        s = str(sql).strip().rstrip(";")
        low = s.lower()
        if not (low.startswith("select") or low.startswith("with")):
            raise ValueError("only SELECT/WITH queries over registered file tables are permitted")
        if ";" in s:
            raise ValueError("a single statement is permitted")
        con = self._duckdb()
        timer = threading.Timer(self.query_timeout, con.interrupt)
        timer.start()
        try:
            rel = con.execute(s)
            cols = [d[0] for d in rel.description]
            rows = rel.fetchmany(max(1, min(int(max_rows), 50)))
        finally:
            timer.cancel()
        self._prov("query_data", sql=s[:500])
        return {"columns": cols, "rows": [list(r) for r in rows], "row_count_returned": len(rows),
                "tables_hint": "Tables are named by file_id, e.g. observations__v2__train."}

    def t_materialize_features(self, graph: dict) -> dict:
        repair = self.last_failed
        if repair:
            if self.budget.repairs >= self.budget.limits["repair_cycles"]:
                return {"error": "repair limit reached: submit the best valid artifact or abstain",
                        "repairs_used": self.budget.repairs}
            self.budget.repairs += 1
        try:
            validate_graph(graph)
            frames, traces = {}, {}
            for p, v in self.views.items():
                frames[p], traces[p] = execute(graph, v)
        except ResolutionError as e:
            self.last_failed = True
            self._prov("materialize_features", status="error", error=str(e)[:300], reason=e.reason)
            return {"materialized": False, "error": str(e), "resolution_failure": e.reason}
        except GraphError as e:
            self.last_failed = True
            self._prov("materialize_features", status="error", error=str(e)[:300])
            return {"materialized": False, "error": str(e)}
        hid = f"H{len(self.handles) + 1}"
        handle = {"id": hid, "graph": graph, "graph_hash": json_hash(graph), "frames": frames, "traces": traces}
        self.handles[hid] = handle
        self._prov("materialize_features", status="ok", handle=hid, graph_hash=handle["graph_hash"],
                   used=sorted({f"{l['table']}:{s}:{v['file_id']}" for t in traces.values() for l in t["loads"]
                                for s, v in l["shards"].items()})[:400],
                   generated={p: traces[p]["output_hash"] for p in traces}, repair=repair)
        out = {"materialized": True, "handle": hid,
               "summary": {p: summarize(frames[p], len(self.manifest["partitions"][p]), sample_rows=2 if p == "train" else 0)
                           for p in frames},
               "operations": {n["id"]: {k: v for k, v in n.items() if k not in ("id",)} for n in traces["train"]["nodes"]
                              if n["op"] != "project"}}
        failed = False
        gate_out = []
        if self.q:
            v = gates.quality_gate(handle, self.contract, self.catalog, self.manifest)
            self._gate(v)
            gate_out.append(v)
            failed |= not v["passed"]
        if self.p:
            v = gates.provenance_gate(handle, self.contract, self.catalog, self.provenance)
            self._gate(v)
            gate_out.append(v)
            failed |= not v["passed"]
        handle["gates"] = gate_out
        if gate_out:
            out["gate_verdicts"] = gate_out
        self.last_failed = failed
        return out

    def _gate(self, verdict: dict):
        self.budget.gate_calls += 1
        self.gate_log.append(verdict)
        self._prov("gate", gate=verdict["gate"], artifact=verdict["artifact"], passed=verdict["passed"],
                   failures=[f["check"] for f in verdict["failures"]])

    def t_fit_evaluate(self, handle: str, candidate: str) -> dict:
        if handle not in self.handles:
            raise KeyError(f"unknown handle {handle!r}; materialize_features first")
        key = (handle, candidate)
        if key in self.fit_cache:
            return {"cached": True, **self.fit_cache[key]}
        if self.budget.evaluations >= self.budget.limits["pipeline_evaluations"]:
            return {"error": "pipeline evaluation limit (6) reached", "evaluations_used": self.budget.evaluations}
        self.budget.evaluations += 1
        h = self.handles[handle]
        seed = self.seeds["estimator"]
        t_wait = time.time()
        if self.fit_slot is not None:
            self.fit_slot.acquire()
        self.budget.wait_seconds += time.time() - t_wait
        try:
            res = modeling.fit_evaluate(candidate, h["frames"]["train"], h["frames"]["validation"], self.labels,
                                        self.cv, self.contract, seed)
            status = "ok"
        except Exception as e:  # failed attempts consume an evaluation slot
            res = {"candidate": candidate, "error": f"{type(e).__name__}: {e}"}
            status = "error"
        finally:
            if self.fit_slot is not None:
                self.fit_slot.release()
        self.budget.fits += res.get("fits", 0)
        self._prov("fit_evaluate", handle=handle, candidate=candidate, status=status, fit_partitions=["train"],
                   score_partitions=["train_cv", "validation"], validation=res.get("validation"))
        res["evaluations_used"] = self.budget.evaluations
        self.fit_results.append({"handle": handle, **res})
        if status == "error":
            self.last_failed = True
            self.fit_cache[key] = res
            return res
        gate_out = []
        if self.q:
            v = gates.fit_quality_gate(res, handle)
            self._gate(v)
            gate_out.append(v)
        if self.p:
            v = gates.provenance_gate(h, self.contract, self.catalog, self.provenance, stage="fit")
            self._gate(v)
            gate_out.append(v)
        if gate_out:
            res["gate_verdicts"] = gate_out
            self.last_failed = not all(g["passed"] for g in gate_out)
        slim = {k: res[k] for k in ("candidate", "metric", "cv_mean", "validation", "validation_reason", "rows",
                                    "evaluations_used") if k in res}
        if gate_out:
            slim["gate_verdicts"] = gate_out
        self.fit_cache[key] = slim
        return slim

    def t_quality_check(self, handle: str) -> dict:
        if not self.q:
            return {"error": "quality_check is not available in this configuration"}
        h = self.handles.get(handle)
        if h is None:
            raise KeyError(f"unknown handle {handle!r}")
        return {"verdicts": [g for g in h.get("gates", []) if g["gate"] == "quality"]}

    def t_provenance_check(self, handle: str) -> dict:
        if not self.p:
            return {"error": "provenance_check is not available in this configuration"}
        h = self.handles.get(handle)
        if h is None:
            raise KeyError(f"unknown handle {handle!r}")
        return {"verdicts": [g for g in h.get("gates", []) if g["gate"] == "provenance"]}

    def t_submit(self, handle: str, candidate: str, findings: list | None = None) -> dict:
        if handle not in self.handles:
            raise KeyError(f"unknown handle {handle!r}")
        if candidate not in self.contract["candidate_models"]:
            raise ValueError(f"candidate {candidate!r} is not permitted")
        h = self.handles[handle]
        gate_out = []
        if self.q:
            v = gates.quality_gate(h, self.contract, self.catalog, self.manifest)
            v["stage"] = "submit"
            self._gate(v)
            gate_out.append(v)
        if self.p:
            v = gates.provenance_gate(h, self.contract, self.catalog, self.provenance, stage="submit", candidate=candidate)
            self._gate(v)
            gate_out.append(v)
        if gate_out and not all(g["passed"] for g in gate_out):
            self.last_failed = True
            self._prov("submit", status="rejected_by_gates", handle=handle, candidate=candidate)
            return {"submitted": False, "error": "final gate checks failed; repair or abstain", "gate_verdicts": gate_out}
        seed = self.seeds["estimator"]
        t_wait = time.time()
        if self.fit_slot is not None:
            self.fit_slot.acquire()
        self.budget.wait_seconds += time.time() - t_wait
        try:
            model, info = modeling.refit(candidate, h["frames"]["train"], h["frames"]["validation"], self.labels,
                                         self.contract, seed)
        except Exception as e:
            self.last_failed = True
            self._prov("submit", status="refit_error", handle=handle, candidate=candidate, error=str(e)[:300])
            return {"submitted": False, "error": f"final refit failed: {type(e).__name__}: {e}"}
        finally:
            if self.fit_slot is not None:
                self.fit_slot.release()
        self.budget.fits += 1
        clean_findings = []
        for f in (findings or [])[:50]:
            if isinstance(f, dict):
                clean_findings.append({k: str(v)[:200] for k, v in f.items()})
            else:
                clean_findings.append({"finding": str(f)[:200]})
        files = {}
        write_json(self.sub_dir / "graph.json", h["graph"])
        with open(self.sub_dir / "model.pkl", "wb") as fh:
            pickle.dump(model, fh, protocol=4)
        write_json(self.sub_dir / "model_choice.json", {"candidate": candidate, "handle": handle,
                                                         "effective_params": modeling.effective_params(candidate), **info})
        write_json(self.sub_dir / "findings.json", {"findings": clean_findings,
                                                     "operations": {p: t["operations"] for p, t in h["traces"].items()}})
        for fn in ("graph.json", "model.pkl", "model_choice.json", "findings.json"):
            files[fn] = sha256_file(self.sub_dir / fn)
        bundle = {"run_id": self.run_id, "handle": handle, "candidate": candidate, "graph_hash": h["graph_hash"],
                  "files": files, "visible_output_hashes": {p: t["output_hash"] for p, t in h["traces"].items()},
                  "fit_partitions": info["fit_partitions"]}
        write_json(self.sub_dir / "bundle.json", bundle)
        self._prov("submit", status="ok", handle=handle, candidate=candidate, bundle_hash=json_hash(bundle),
                   fit_partitions=info["fit_partitions"])
        raise Terminal("SUBMITTED", {"handle": handle, "candidate": candidate})

    def t_abstain(self, reason: str, detail: str = "") -> dict:
        if reason not in ABSTENTION_REASONS:
            raise ValueError(f"reason must be one of {ABSTENTION_REASONS}")
        self._prov("abstain", reason=reason, detail=str(detail)[:300])
        raise Terminal("ABSTAINED", {"reason": reason, "detail": str(detail)[:300]})

    def close(self):
        if self._duck is not None:
            try:
                self._duck.close()
            except Exception:
                pass
            self._duck = None
