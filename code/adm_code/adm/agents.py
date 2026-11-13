"""Agent state machines: fixed workflow F, single agent (S0/SQP) and three-role team (M0/MQ/MP/MQP)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import modeling
from .core import dumps
from .fixed import contract_graph
from .llm import ROLE_ACTIONS, LLMError
from .tools import BudgetExceeded, Terminal, ToolSession, _truncate

PROMPT_DIR = Path(__file__).parent / "prompts"
WORKER_STEP_CAP = 12
MAX_CONSECUTIVE_INVALID = 3
CHARS_PER_TOKEN = 2.8  # conservative for JSON-heavy text; overflows are also handled by re-trimming


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text()


def est_tokens(s: str) -> int:
    return int(len(s) / CHARS_PER_TOKEN) + 4


class InfrastructureFailure(Exception):
    pass


class Conversation:
    """Role-specific history with deterministic trimming to the context window."""

    def __init__(self, system: str, task: str):
        self.system, self.task = system, task
        self.entries: list = []   # alternating assistant/user dicts with 'summary'

    def add_assistant(self, text: str, summary: str):
        self.entries.append({"role": "assistant", "content": text, "summary": summary})

    def add_user(self, text: str):
        if self.entries and self.entries[-1]["role"] == "user":
            self.entries[-1]["content"] += "\n\n" + text
        elif not self.entries:
            self.task = self.task + "\n\n" + text
        else:
            self.entries.append({"role": "user", "content": text})

    def render(self, max_prompt_tokens: int) -> list:
        fixed = est_tokens(self.system) + est_tokens(self.task) + 200
        budget = max_prompt_tokens - fixed
        pairs = []
        i = 0
        while i < len(self.entries):
            a = self.entries[i]
            u = self.entries[i + 1] if i + 1 < len(self.entries) else None
            pairs.append((a, u))
            i += 2
        keep = []
        for a, u in reversed(pairs):
            cost = est_tokens(a["content"]) + (est_tokens(u["content"]) if u else 0)
            if cost > budget and keep:
                break
            if cost > budget and not keep:
                # always keep the latest turn, truncating it if needed
                u = dict(u) if u else None
                if u:
                    u["content"] = u["content"][: max(400, int(budget * CHARS_PER_TOKEN) - len(a["content"]))]
                keep.insert(0, (a, u))
                break
            keep.insert(0, (a, u))
            budget -= cost
        omitted = pairs[: len(pairs) - len(keep)]
        task = self.task
        if omitted:
            task += "\n\nEarlier steps (details omitted to fit the context window):\n" + "\n".join(
                f"- {a['summary']}" for a, _ in omitted)
        msgs = [{"role": "system", "content": self.system}, {"role": "user", "content": task}]
        for a, u in keep:
            msgs.append({"role": "assistant", "content": a["content"]})
            if u:
                msgs.append({"role": "user", "content": u["content"]})
        return msgs


def parse_action(text: str, role: str) -> tuple[dict | None, str | None]:
    s = (text or "").strip()
    obj = None
    try:
        obj = json.loads(s)
    except Exception:
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            try:
                obj = json.loads(s[a:b + 1])
            except Exception:
                obj = None
    if not isinstance(obj, dict):
        return None, "response is not a JSON object"
    act = obj.get("action")
    if act not in ROLE_ACTIONS[role]:
        return None, f"action must be one of {ROLE_ACTIONS[role]}"
    args = obj.get("args", {})
    if not isinstance(args, dict):
        return None, "args must be an object"
    return {"thought": str(obj.get("thought", ""))[:600], "action": act, "args": args}, None


class AgentRun:
    def __init__(self, session: ToolSession, llm, system_code: str, spec: dict, generation: dict, agent_seed: int,
                 trace: list):
        self.s = session
        self.llm = llm
        self.code = system_code
        self.spec = spec
        self.gen = generation
        self.seed = agent_seed
        self.trace = trace
        self.calls = 0
        self.max_prompt = generation["max_context_tokens"] - generation["max_output_tokens_per_call"] - 256
        c = session.contract
        contract_md = (session.visible / "contract.md").read_text()
        gates_line = (f"Configuration: quality gates are {'ON' if spec['q'] else 'OFF'}; provenance gates are "
                      f"{'ON' if spec['p'] else 'OFF'}. When a gate is ON, verdicts are attached automatically to "
                      "materialize, fit and submit observations.")
        self.task_text = (f"{contract_md}\n{gates_line}\n\nMachine-readable contract:\n<contract_json>{dumps(c)}</contract_json>")
        self.common = load_prompt("common")

    # ---------------------------------------------------------------- model calls
    def ask(self, role: str, conv: Conversation) -> dict:
        invalid = 0
        while True:
            b = self.s.budget
            if b.model_calls + 1 > b.limits["model_calls"]:
                raise BudgetExceeded("model_calls")
            if b.active_seconds() > b.limits["wall_seconds"]:
                raise BudgetExceeded("wall_seconds")
            seed = (self.seed + self.calls) % (2**31 - 1)
            res = None
            prompt_budget = self.max_prompt
            failures = 0
            while res is None:
                msgs = conv.render(prompt_budget)
                try:
                    res = self.llm.complete(msgs, role, seed)
                except LLMError as e:
                    self.trace.append({"event": "llm_error", "role": role, "error": str(e)[:300], "attempt": failures,
                                       "prompt_budget": prompt_budget})
                    if e.context_overflow and prompt_budget > 3000:
                        prompt_budget = int(prompt_budget * 0.8)  # the token estimate was too low: trim further
                        continue
                    failures += 1
                    if failures >= 3:
                        raise InfrastructureFailure(str(e))
                    time.sleep(5 * failures)
            self.calls += 1
            b.model_calls += 1
            b.tokens_in += res["input_tokens"]
            b.tokens_out += res["output_tokens"]
            b.llm_seconds += res["seconds"]
            act, err = parse_action(res["text"], role)
            self.trace.append({"event": "model", "role": role, "call": self.calls, "input_tokens": res["input_tokens"],
                               "output_tokens": res["output_tokens"], "cached_tokens": res.get("cached_tokens", 0),
                               "seconds": round(res["seconds"], 3), "finish_reason": res.get("finish_reason"),
                               "text": res["text"][:4000], "parse_error": err})
            b.check()
            if act is not None:
                return act
            invalid += 1
            conv.add_assistant(res["text"][:300], f"invalid response ({err})")
            conv.add_user("Observation (format_error):\n" + dumps({"error": err, "hint": "Reply with one JSON object "
                                                                   '{"thought": ..., "action": ..., "args": {...}}'}))
            if invalid >= MAX_CONSECUTIVE_INVALID:
                raise _ExecutionError(f"{invalid} consecutive invalid responses")

    def tool(self, role: str, act: dict, conv: Conversation) -> dict:
        name = act["action"]
        obs = self.s.call(name, act["args"])
        self.trace.append({"event": "tool", "role": role, "tool": name, "args": _slim_args(act["args"]),
                           "ok": obs.get("ok"), "obs": _truncate(obs, 2500)})
        conv.add_assistant(dumps(act), f"{role}: {name}({_short(act['args'])}) -> {'ok' if obs.get('ok') else 'error'}"
                           + (f" handle={obs.get('handle')}" if obs.get("handle") else "")
                           + (f" val={obs.get('validation')}" if obs.get("validation") is not None else ""))
        conv.add_user(f"Observation ({name}) | remaining budget {dumps(self.s.budget.remaining())}:\n" + _truncate(obs))
        return obs

    # ---------------------------------------------------------------- single agent
    def run_single(self):
        conv = Conversation(self.common + "\n" + load_prompt("single"), self.task_text)
        while True:
            act = self.ask("single", conv)
            self.tool("single", act, conv)

    # ---------------------------------------------------------------- multi agent
    def run_multi(self):
        coord = Conversation(self.common + "\n" + load_prompt("coordinator"), self.task_text)
        workers = {r: Conversation(self.common + "\n" + load_prompt(r), self.task_text) for r in ("data_manager", "miner")}
        board = {"handles": {}, "evaluations": {}, "reports": []}
        while True:
            act = self.ask("coordinator", coord)
            if act["action"] == "delegate":
                role = act["args"].get("role")
                instr = str(act["args"].get("instruction", ""))[:1500]
                if role not in workers:
                    obs = {"ok": False, "error": "role must be data_manager or miner"}
                    coord.add_assistant(dumps(act), "coordinator: invalid delegate")
                    coord.add_user("Observation (delegate):\n" + dumps(obs))
                    continue
                self.trace.append({"event": "delegate", "role": role, "instruction": instr[:500]})
                report = self.run_worker(role, workers[role], instr, board)
                board["reports"].append({"from": role, **{k: report.get(k) for k in ("summary", "handle", "candidate", "problem")}})
                coord.add_assistant(dumps(act), f"coordinator: delegate {role} -> report handle={report.get('handle')} "
                                                f"candidate={report.get('candidate')} problem={report.get('problem')}")
                coord.add_user(f"Observation (report from {role}) | remaining budget {dumps(self.s.budget.remaining())}:\n"
                               + _truncate({"report_from": role, **report, "blackboard": _board(board)}))
            else:
                obs = self.tool("coordinator", act, coord)
                _update_board(board, act, obs)

    def run_worker(self, role: str, conv: Conversation, instruction: str, board: dict) -> dict:
        conv.add_user(f"Instruction from coordinator: {instruction}\nShared blackboard: {dumps(_board(board))}")
        for _ in range(WORKER_STEP_CAP):
            act = self.ask(role, conv)
            if act["action"] == "report":
                a = act["args"]
                rep = {"summary": str(a.get("summary", ""))[:600], "handle": a.get("handle"),
                       "candidate": a.get("candidate"), "problem": a.get("problem")}
                conv.add_assistant(dumps(act), f"{role}: report")
                return rep
            obs = self.tool(role, act, conv)
            _update_board(board, act, obs)
        return {"summary": f"{role} reached its {WORKER_STEP_CAP}-step delegation cap", "handle": None,
                "candidate": None, "problem": None}


class _ExecutionError(Exception):
    pass


def _short(args: dict) -> str:
    s = dumps({k: (v if k != "graph" else f"<graph {len(v.get('nodes', [])) if isinstance(v, dict) else '?'} nodes>")
               for k, v in (args or {}).items()})
    return s[:160]


def _slim_args(args: dict) -> dict:
    return json.loads(dumps(args))


def _board(board: dict) -> dict:
    return {"handles": board["handles"], "evaluations": board["evaluations"], "last_reports": board["reports"][-3:]}


def _update_board(board: dict, act: dict, obs: dict):
    if act["action"] == "materialize_features" and obs.get("handle"):
        gv = obs.get("gate_verdicts")
        board["handles"][obs["handle"]] = {"rows": {p: v.get("rows") for p, v in obs.get("summary", {}).items()},
                                           "gates_passed": (all(g["passed"] for g in gv) if gv else None)}
    if act["action"] == "fit_evaluate" and obs.get("candidate"):
        board["evaluations"][f"{act['args'].get('handle')}/{obs['candidate']}"] = obs.get("validation")


# --------------------------------------------------------------------------- drivers
def run_fixed(session: ToolSession, trace: list):
    c, cat = session.contract, session.catalog
    graph = contract_graph(c, cat)
    obs = session.call("materialize_features", {"graph": graph})
    trace.append({"event": "tool", "role": "F", "tool": "materialize_features", "ok": obs.get("ok"), "obs": _truncate(obs, 2500)})
    if not obs.get("materialized"):
        reason = obs.get("resolution_failure") or "CONTRACT_UNSATISFIABLE"
        session.call("abstain", {"reason": reason, "detail": str(obs.get("error", ""))[:200]})
    if any(not g["passed"] for g in obs.get("gate_verdicts", [])):
        session.call("abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "fixed workflow gates failed"})
    h = obs["handle"]
    results = []
    for cid in c["candidate_models"]:
        r = session.call("fit_evaluate", {"handle": h, "candidate": cid})
        trace.append({"event": "tool", "role": "F", "tool": "fit_evaluate", "ok": r.get("ok"), "obs": _truncate(r, 800)})
        if r.get("ok"):
            results.append(r)
    best = modeling.select_best(results, c["selection_metric"])
    if best is None:
        session.call("abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "no candidate could be evaluated"})
    r = session.call("submit", {"handle": h, "candidate": best, "findings": [{"type": "fixed_workflow", "detail": "contract-driven"}]})
    trace.append({"event": "tool", "role": "F", "tool": "submit", "ok": r.get("ok"), "obs": _truncate(r, 1500)})
    session.call("abstain", {"reason": "CONTRACT_UNSATISFIABLE", "detail": "submission rejected"})


def execute_run(session: ToolSession, system_code: str, spec: dict, llm, generation: dict, agent_seed: int) -> dict:
    """Run one system on one task instance until a terminal state."""
    trace: list = []
    out = {"terminal_state": None, "abstention_reason": None, "error": None, "submission": None}
    try:
        if spec["planner"] == "fixed":
            run_fixed(session, trace)
        else:
            ar = AgentRun(session, llm, system_code, spec, generation, agent_seed, trace)
            ar.run_single() if spec["planner"] == "single" else ar.run_multi()
    except Terminal as t:
        out["terminal_state"] = t.state
        if t.state == "ABSTAINED":
            out["abstention_reason"] = t.info["reason"]
        else:
            out["submission"] = t.info
    except BudgetExceeded as e:
        out["terminal_state"] = "BUDGET_EXCEEDED"
        out["error"] = f"limit exceeded: {e}"
    except InfrastructureFailure as e:
        out["terminal_state"] = "INFRASTRUCTURE_ERROR"
        out["error"] = str(e)[:500]
    except _ExecutionError as e:
        out["terminal_state"] = "EXECUTION_ERROR"
        out["error"] = str(e)[:500]
    except Exception as e:  # unexpected failure inside the agent loop is an execution error of the run
        import traceback
        out["terminal_state"] = "EXECUTION_ERROR"
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        trace.append({"event": "exception", "traceback": traceback.format_exc()[-3000:]})
    finally:
        session.close()
    out["trace"] = trace
    out["blocked_attempts"] = session.blocked_attempts
    out["gate_log"] = [{"gate": g["gate"], "artifact": g["artifact"], "stage": g.get("stage", "materialize"),
                        "passed": g["passed"], "failures": [f["check"] for f in g["failures"]]} for g in session.gate_log]
    return out
