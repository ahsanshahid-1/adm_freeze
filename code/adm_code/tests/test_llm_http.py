"""The vLLM client and preflight against a local fake OpenAI-compatible server (no GPU needed)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer

import pytest

from adm import tasks as T
from adm.agents import execute_run
from adm.core import GENERATION, PILOT_LIMITS, SYSTEM_SPEC, instance_dirs
from adm.llm import MockLLM, VLLMClient
from adm.serving import Server
from adm.tools import Budget, ToolSession

STATE = {"requests": [], "max_chars": 10 ** 9, "mock": None, "reject_response_format": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        STATE["requests"].append(body)
        chars = sum(len(m["content"]) for m in body["messages"])
        if STATE["reject_response_format"] and "response_format" in body:
            return self._send(400, {"error": "response_format not supported"})
        if chars > STATE["max_chars"]:
            return self._send(400, {"error": f"This model's maximum context length is 16384 tokens; prompt has {chars}"})
        user = body["messages"][-1]["content"]
        if "inspect_schema" in user and "Call" in user:
            text = json.dumps({"thought": "ok", "action": "inspect_schema", "args": {"table": "observations"}})
        elif "Choose" in user:
            text = json.dumps({"thought": "17+25=42", "action": "list_sources", "args": {}})
        else:
            role = body["response_format"]["json_schema"]["name"].replace("_action", "") if "response_format" in body else "single"
            text = STATE["mock"].complete(body["messages"], role, 0)["text"]
        self._send(200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": chars // 3, "completion_tokens": len(text) // 3}})

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


class _Server(HTTPServer):
    request_queue_size = 64
    daemon_threads = True


@pytest.fixture(scope="module")
def fake_server():
    srv = _Server(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()


def test_preflight_detects_structured_mode(fake_server, tmp_path):
    s = Server(tmp_path / "env", tmp_path / "m", tmp_path / "c", tmp_path / "l", log=lambda *a: None)
    s.port = fake_server
    STATE["reject_response_format"] = True
    pf = s.preflight("A", GENERATION)
    assert pf["ok"] and pf["structured_mode"] == "structured_outputs" and pf["args_test"]["passed"]
    STATE["reject_response_format"] = False
    pf = s.preflight("A", GENERATION)
    assert pf["ok"] and pf["structured_mode"] == "response_format" and pf["throughput"]["valid_json"] == 8


def test_agent_run_over_http_with_context_retrim(fake_server, paths, tmp_path):
    T.build_instance(paths, "development", "D5", "T3", "C6", 1)
    d = instance_dirs(paths, "development", "D5", "T3", "C6", 1)
    STATE["mock"] = MockLLM(11, invalid_rate=0.0)
    STATE["max_chars"] = 30000  # forces the client to hit a context-length error and re-trim
    STATE["requests"].clear()
    sess = ToolSession("h", d["visible"], d["trusted"], tmp_path / "sub", SYSTEM_SPEC["MQP"], Budget(dict(PILOT_LIMITS)),
                       {"estimator": 3, "agent": 4})
    client = VLLMClient(f"http://127.0.0.1:{fake_server}", "A", GENERATION, "response_format")
    out = execute_run(sess, "MQP", SYSTEM_SPEC["MQP"], client, GENERATION, 5)
    STATE["max_chars"] = 10 ** 9
    assert out["terminal_state"] in ("SUBMITTED", "ABSTAINED"), out
    req = STATE["requests"][0]
    assert req["response_format"]["type"] == "json_schema" and req["seed"] >= 0 and req["max_tokens"] == 1024
    assert req["response_format"]["json_schema"]["schema"]["properties"]["action"]["enum"][0] == "delegate"
    assert all(sum(len(m["content"]) for m in r["messages"]) <= 30000 for r in STATE["requests"][-3:])
    assert not any(e.get("event") == "exception" for e in out["trace"])
