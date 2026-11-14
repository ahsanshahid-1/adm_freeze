"""Language-model clients: an OpenAI-compatible vLLM client with schema-constrained JSON, and a
scripted MockLLM used to test the full pipeline without a GPU (mock results are never study results)."""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request

from .core import dumps
from .fixed import contract_graph

ROLE_ACTIONS = {
    "single": ["list_sources", "inspect_schema", "profile_data", "query_data", "materialize_features", "fit_evaluate",
               "quality_check", "provenance_check", "submit", "abstain"],
    "coordinator": ["delegate", "list_sources", "inspect_schema", "profile_data", "query_data", "materialize_features",
                    "fit_evaluate", "quality_check", "provenance_check", "submit", "abstain"],
    "data_manager": ["list_sources", "inspect_schema", "profile_data", "query_data", "materialize_features",
                     "quality_check", "provenance_check", "report"],
    "miner": ["fit_evaluate", "quality_check", "provenance_check", "report"],
}


def action_schema(role: str) -> dict:
    return {"type": "object",
            "properties": {"thought": {"type": "string"},
                           "action": {"type": "string", "enum": ROLE_ACTIONS[role]},
                           "args": {"type": "object"}},
            "required": ["thought", "action", "args"], "additionalProperties": False}


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 3.2))


class LLMError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status

    @property
    def context_overflow(self) -> bool:
        m = str(self).lower()
        return self.status == 400 and ("context" in m or "maximum" in m or "too long" in m or "max_model_len" in m)


class VLLMClient:
    """Calls a local vLLM OpenAI-compatible server."""

    def __init__(self, base_url: str, model: str, generation: dict, structured_mode: str = "response_format",
                 timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.gen = generation
        self.mode = structured_mode
        self.timeout = timeout

    def _post(self, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        last = None
        for attempt in range(3):  # transient connection resets are retried; HTTP errors are not
            req = urllib.request.Request(self.base_url + "/v1/chat/completions", data=data,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:500]
                raise LLMError(f"HTTP {e.code}: {body}", e.code) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                time.sleep(1 + 2 * attempt)
        raise LLMError(f"connection error: {last}")

    def complete(self, messages: list, role: str, seed: int) -> dict:
        payload = {"model": self.model, "messages": messages, "temperature": self.gen["temperature"],
                   "top_p": self.gen["top_p"], "top_k": self.gen["top_k"],
                   "max_tokens": self.gen["max_output_tokens_per_call"], "seed": int(seed)}
        if "enable_thinking" in self.gen:
            payload["chat_template_kwargs"] = {"enable_thinking": bool(self.gen["enable_thinking"])}
        schema = action_schema(role)
        if self.mode == "response_format":
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": f"{role}_action", "schema": schema, "strict": True}}
        elif self.mode == "structured_outputs":
            payload["structured_outputs"] = {"json": schema}
        elif self.mode == "guided_json":
            payload["guided_json"] = schema
        t0 = time.time()
        resp = self._post(payload)
        dt = time.time() - t0
        ch = resp["choices"][0]
        usage = resp.get("usage") or {}
        return {"text": ch["message"].get("content") or "", "input_tokens": int(usage.get("prompt_tokens", 0)),
                "output_tokens": int(usage.get("completion_tokens", 0)), "seconds": dt,
                "finish_reason": ch.get("finish_reason"),
                "cached_tokens": int(((usage.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0)}


# --------------------------------------------------------------------------- mock
MOCK_MISTAKES = {
    "latest_policy": 0.30, "skip_alias": 0.25, "skip_dedupe": 0.25, "skip_parse": 0.20, "skip_canonical": 0.30,
    "sample_std": 0.30, "keep_excluded": 0.15, "drop_missing": 0.10,
}
GATE_FIXES = {
    "authority": ["latest_policy"], "record_coverage": ["skip_alias", "drop_missing"], "key_uniqueness": ["skip_dedupe"],
    "numeric_types": ["skip_parse"], "canonical_units": ["skip_canonical"], "value_ranges": ["skip_canonical"],
    "aggregate": ["sample_std"], "excluded_predictors": ["keep_excluded"], "required_columns": ["keep_excluded"],
    "missing_value_policy": ["drop_missing"], "label_match": ["skip_alias"], "validation_coverage": ["skip_alias", "skip_dedupe"],
}


class MockLLM:
    """Deterministic scripted policy that reads the conversation and emits schema-valid actions.

    Each run draws a set of workflow mistakes. Ordinary execution errors and (when the configuration has
    them) gate verdicts let it repair specific mistakes, so the full pipeline exercises passes, failures,
    repairs, refusals and false submissions. It exists only to test plumbing."""

    def __init__(self, seed: int, invalid_rate: float = 0.03):
        self.rng = random.Random(seed)
        self.mistakes = {k for k, p in MOCK_MISTAKES.items() if self.rng.random() < p}
        self.invalid_rate = invalid_rate
        self.contract = None
        self.catalog_tables = None
        self.handle = None
        self.evals: dict = {}
        self.plan = ["CL3", "CL5", "CL1"]
        self.phase: dict = {}
        self.repairs = 0
        self.abstain_reason = None

    @staticmethod
    def _last_obs(messages: list) -> dict | None:
        for m in reversed(messages):
            if m["role"] != "user":
                continue
            # a user message may hold several merged observations; use the last real (non-format) one
            chunks = [c for c in m["content"].split("\n\n") if c.startswith("Observation") and
                      not c.startswith("Observation (format_error)")]
            if not chunks and "Observation (format_error)" in m["content"]:
                continue
            if chunks:
                try:
                    return json.loads(chunks[-1].split("\n", 1)[1])
                except Exception:
                    return None
            return None
        return None

    def _contract(self, messages):
        if self.contract is None:
            for m in messages:
                mm = re.search(r"<contract_json>(.*?)</contract_json>", m["content"], re.S)
                if mm:
                    self.contract = json.loads(mm.group(1))
                    break
        return self.contract


    def _graph(self) -> dict:
        g = contract_graph(self.contract, {"tables": self.catalog_tables})
        M = self.mistakes
        alias, nodes = {}, []
        for n in g["nodes"]:
            n = dict(n)
            for r in ("input", "left", "right"):
                if r in n:
                    n[r] = alias.get(n[r], n[r])
            op = n["op"]
            if (op == "map_alias" and "skip_alias" in M) or (op == "dedupe" and "skip_dedupe" in M) or \
               (op == "parse_numeric" and "skip_parse" in M) or (op == "to_canonical" and "skip_canonical" in M):
                alias[n["id"]] = n["input"]
                continue
            if op == "load" and "latest_policy" in M:
                n["policy"] = "latest_modified"
            if op == "aggregate" and "sample_std" in M:
                n["stats"] = ["mean", "sample_std", "count"]
            if op == "project" and n["id"] == "features":
                if "keep_excluded" in M:
                    ex = [c for c in self.contract["excluded_predictors"] if c not in ("observation_id", "profile_key", "_shard")]
                    if ex:
                        n["columns"] = n["columns"] + ex[:1]
                if "drop_missing" in M:
                    nodes.append({"id": "dropna", "op": "drop_missing_rows", "input": n["input"]})
                    n["input"] = "dropna"
            nodes.append(n)
        return {"nodes": nodes, "output": alias.get(g["output"], g["output"])}

    def _apply_feedback(self, obs: dict | None) -> bool:
        if not obs:
            return False
        texts = [f["check"] + " " + f.get("detail", "") for v in (obs.get("gate_verdicts") or []) for f in v.get("failures", [])]
        if obs.get("error"):
            texts.append(str(obs["error"]))
        fixed = False
        for t in texts:
            keys = [k for k in GATE_FIXES if k in t]
            if "parse_numeric" in t or "non-numeric" in t or "not numeric" in t:
                keys.append("numeric_types")
            for k in keys:
                for m in GATE_FIXES[k]:
                    if m in self.mistakes:
                        self.mistakes.discard(m)
                        fixed = True
        return fixed

    @staticmethod
    def _act(thought, action, args):
        return {"thought": thought, "action": action, "args": args}

    def _cands(self):
        return list((self.contract or {}).get("candidate_models", ["CL1"]))

    def _best(self):
        metric = (self.contract or {}).get("selection_metric", "average_precision")
        if self.evals:
            return (min if metric in ("rmse", "mae") else max)(sorted(self.evals), key=self.evals.get)
        return self._cands()[0]

    def _data_step(self, role: str, obs: dict | None):
        """Shared by the single agent and the data manager. Returns an action or None to continue."""
        st = self.phase.get(role, "start")
        if st == "start":
            self.phase[role] = "listed"
            return self._act("List the catalog.", "list_sources", {})
        if st == "listed" and obs and "tables" in obs:
            self.phase[role] = "materialize"
            return self._act("Build the feature graph from the contract.", "materialize_features", {"graph": self._graph()})
        if st == "materialize" and obs is not None and ("materialized" in obs or "repairs_used" in obs):
            if obs.get("resolution_failure"):
                r = obs["resolution_failure"]
                if role == "data_manager":
                    return self._act("Authority cannot be resolved.", "report",
                                     {"summary": str(obs.get("error", ""))[:200], "handle": None, "problem": r})
                return self._act("Authority cannot be resolved.", "abstain", {"reason": r, "detail": str(obs.get("error", ""))[:200]})
            if "repair limit" in str(obs.get("error", "")):
                self.phase[role] = "data_done"
                return None
            if obs.get("materialized"):
                self.handle = obs["handle"]
            bad = [v for v in (obs.get("gate_verdicts") or []) if not v["passed"]]
            if (bad or not obs.get("materialized")) and self._apply_feedback(obs):
                return self._act("Repair the graph using the feedback.", "materialize_features", {"graph": self._graph()})
            if not obs.get("materialized") and self.handle is None:
                if role == "data_manager":
                    return self._act("No valid handle.", "report", {"summary": str(obs.get("error", ""))[:200], "handle": None,
                                                                   "problem": "CONTRACT_UNSATISFIABLE"})
                return self._act("No valid handle.", "abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": str(obs.get("error", ""))[:200]})
            self.phase[role] = "data_done"
            return None
        return None

    def decide(self, messages: list, role: str) -> dict:
        self._contract(messages)
        obs = self._last_obs(messages)
        if obs and isinstance(obs.get("tables"), list):
            self.catalog_tables = {t["table"]: {"grain": t["grain"], "columns": {c: "x" for c in t["columns"]}}
                                   for t in obs["tables"]}
        if role == "coordinator":
            if obs and obs.get("report_from") == "data_manager":
                if obs.get("problem"):
                    reason = obs["problem"] if obs["problem"] in ("REQUIRED_SOURCE_MISSING", "AMBIGUOUS_AUTHORITY") else "CONTRACT_UNSATISFIABLE"
                    return self._act("The data cannot satisfy the contract.", "abstain", {"reason": reason, "detail": obs.get("summary", "")})
                self.handle = obs.get("handle") or self.handle
                self.phase["miner_attempts"] = 0
                self.evals = {}
                return self._act("Features ready; ask the miner.", "delegate",
                                 {"role": "miner", "instruction": f"Evaluate candidates on {self.handle} and recommend one."})
            if obs and obs.get("report_from") == "miner":
                if obs.get("candidate") is None:
                    if self.repairs >= 2:
                        return self._act("Modeling keeps failing.", "abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "no valid model"})
                    self.repairs += 1
                    self.phase["data_manager"] = "repair"
                    return self._act("Modeling failed; repair features.", "delegate",
                                     {"role": "data_manager", "instruction": "Repair the feature graph: " + str(obs.get("summary"))[:300]})
                return self._act("Submit the recommended model.", "submit",
                                 {"handle": obs.get("handle") or self.handle, "candidate": obs["candidate"],
                                  "findings": [{"type": "summary", "detail": str(obs.get("summary", ""))[:100]}]})
            if obs and obs.get("submitted") is False:
                if self._apply_feedback(obs) and self.repairs < 2:
                    self.repairs += 1
                    self.phase["data_manager"] = "repair"
                    self.phase["miner_attempts"] = 0
                    return self._act("Gate rejected the submission; repair.", "delegate",
                                     {"role": "data_manager", "instruction": "Repair the graph using: " + str(obs)[:300]})
                return self._act("Gates cannot be satisfied.", "abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "final gates failed"})
            return self._act("Start with data preparation.", "delegate",
                             {"role": "data_manager", "instruction": "Discover sources and materialize a contract-compliant handle."})
        if role == "data_manager":
            if self.phase.get("data_manager") == "repair":
                self.phase["data_manager"] = "materialize"
                return self._act("Rebuild the graph.", "materialize_features", {"graph": self._graph()})
            a = self._data_step(role, obs)
            if a:
                return a
            return self._act("Report the handle.", "report", {"summary": f"materialized {self.handle}", "handle": self.handle, "problem": None})
        if role == "single":
            if self.phase.get("single") != "data_done":
                a = self._data_step(role, obs)
                if a:
                    return a
                if self.phase.get("single") != "data_done":
                    return self._act("Continue.", "list_sources", {})
            if obs and obs.get("submitted") is False:
                if self._apply_feedback(obs):
                    self.phase["single"] = "materialize"
                    self.evals = {}
                    self.phase["single_attempts"] = 0
                    return self._act("Repair after gate rejection.", "materialize_features", {"graph": self._graph()})
                return self._act("Gates cannot be satisfied.", "abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "final gates failed"})
        if role in ("single", "miner"):
            if role == "miner":
                for m in reversed(messages):
                    if m["role"] == "user" and not m["content"].startswith("Observation"):
                        h = re.findall(r"\bH\d+\b", m["content"])
                        if h:
                            self.handle = h[-1]
                        break
            if obs and obs.get("candidate") and obs.get("validation") is not None:
                self.evals[obs["candidate"]] = obs["validation"]
            if obs and "non-numeric" in str(obs.get("error", "")):
                if role == "single" and self._apply_feedback(obs):
                    self.phase["single"] = "materialize"
                    return self._act("Parse numeric columns.", "materialize_features", {"graph": self._graph()})
                if role == "miner":
                    self._apply_feedback(obs)
                    return self._act("Features are not numeric.", "report", {"summary": str(obs["error"])[:200], "handle": self.handle, "candidate": None})
            plan = [c for c in self._cands() if c[-1] in "351"]
            plan = sorted(plan, key=lambda c: "351".index(c[-1]))
            key = role + "_attempts"
            todo = [c for c in plan if c not in self.evals]
            if todo and self.phase.get(key, 0) < 3:
                self.phase[key] = self.phase.get(key, 0) + 1
                return self._act("Evaluate a candidate.", "fit_evaluate", {"handle": self.handle, "candidate": todo[0]})
            best = self._best()
            if role == "miner":
                return self._act("Recommend the best candidate.", "report",
                                 {"summary": f"best {best} {self.evals.get(best)}", "handle": self.handle, "candidate": best if self.evals else None})
            return self._act("Submit the best candidate.", "submit",
                             {"handle": self.handle, "candidate": best, "findings": [{"type": "summary", "detail": "mock"}]})
        return self._act("Fallback.", "list_sources", {})

    def complete(self, messages: list, role: str, seed: int) -> dict:
        prompt_chars = sum(len(m["content"]) for m in messages)
        if self.rng.random() < self.invalid_rate:
            text = '{"thought": "unterminated'
        else:
            text = dumps(self.decide(messages, role))
        return {"text": text, "input_tokens": max(1, int(prompt_chars / 3.2)), "output_tokens": estimate_tokens(text),
                "seconds": 0.0, "finish_reason": "stop", "cached_tokens": 0}
