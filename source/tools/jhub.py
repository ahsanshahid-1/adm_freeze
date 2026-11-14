#!/usr/bin/env python3
"""Small client for the UALR CRC JupyterHub (exaiops) single-user server.

Token is read from ~/.config/jhub/token (or $JHUB_TOKEN). It is never printed.

Usage:
  jhub.py status                      hub + server status
  jhub.py start | stop                start/stop your server
  jhub.py ls [REMOTE_DIR]             list a remote directory
  jhub.py put LOCAL [REMOTE]          upload a file or directory (chunked)
  jhub.py get REMOTE [LOCAL]          download a file
  jhub.py py "CODE" | -f FILE.py      run Python in a fresh remote kernel
  jhub.py sh "COMMAND"                run a shell command on the server
  jhub.py launch NAME "COMMAND"       start a long job that survives disconnecting (log: adm_crc_run/logs/NAME.log)
  jhub.py logs NAME [-n LINES]        show the tail of a launched job's log and whether it is still running
  Options for py/sh:  --timeout SECONDS (default 600)
  Option for py:      --kernel science|python3 (default science, CRC's shared env)
"""
import argparse
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
import websocket

HUB = os.environ.get("JHUB_URL", "https://jh.crc.ualr.edu/exaiops")
USER = os.environ.get("JHUB_USER", "axshahid")
SERVER = f"{HUB}/user/{USER}"
CHUNK = 8 * 1024 * 1024


def _token() -> str:
    tok = os.environ.get("JHUB_TOKEN")
    if not tok:
        p = Path.home() / ".config" / "jhub" / "token"
        if not p.exists():
            sys.exit(f"No token: create {p} or set JHUB_TOKEN")
        tok = p.read_text().strip()
    return tok


S = requests.Session()
S.headers["Authorization"] = f"token {_token()}"


def _check(r: requests.Response) -> requests.Response:
    if r.status_code >= 400:
        sys.exit(f"HTTP {r.status_code} {r.request.method} {r.url}\n{r.text[:2000]}")
    return r


def _q(path: str) -> str:
    return requests.utils.quote(path.strip("/"))


# ---------------------------------------------------------------- hub / server
def status():
    u = _check(S.get(f"{HUB}/hub/api/user", timeout=30)).json()
    srv = u.get("servers", {}).get("")
    print(f"user: {u['name']}  server: {'running' if srv and srv.get('ready') else 'not running'}")
    if srv:
        print(f"started: {srv.get('started')}  last_activity: {srv.get('last_activity')}")
        st = _check(S.get(f"{SERVER}/api/status", timeout=30)).json()
        print(f"kernels: {st.get('kernels')}  connections: {st.get('connections')}")


def start(wait: int = 300):
    r = S.post(f"{HUB}/hub/api/users/{USER}/server", timeout=60)
    if r.status_code not in (201, 202, 400):
        _check(r)
    t0 = time.time()
    while time.time() - t0 < wait:
        srv = _check(S.get(f"{HUB}/hub/api/user", timeout=30)).json()["servers"].get("")
        if srv and srv.get("ready"):
            print("server ready")
            return
        time.sleep(5)
    sys.exit("server did not become ready in time")


def stop():
    _check(S.delete(f"{HUB}/hub/api/users/{USER}/server", timeout=60))
    print("stop requested")


# ---------------------------------------------------------------- files
def ls(path: str = ""):
    m = _check(S.get(f"{SERVER}/api/contents/{_q(path)}", params={"content": 1}, timeout=60)).json()
    if m["type"] != "directory":
        print(f"{m['type']:9} {m.get('size') or 0:>12} {m['path']}")
        return
    for c in sorted(m["content"], key=lambda c: (c["type"] != "directory", c["name"])):
        size = c.get("size") or 0
        print(f"{c['type']:9} {size:>12} {c['path']}")


def _mkdir(remote: str):
    parts = [p for p in remote.strip("/").split("/") if p]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p
        r = S.get(f"{SERVER}/api/contents/{_q(cur)}", params={"content": 0}, timeout=60)
        if r.status_code == 404:
            _check(S.put(f"{SERVER}/api/contents/{_q(cur)}", json={"type": "directory"}, timeout=60))


def _put_file(local: Path, remote: str):
    size = local.stat().st_size
    with local.open("rb") as fh:
        if size <= CHUNK:
            body = {"type": "file", "format": "base64", "name": local.name,
                    "content": base64.b64encode(fh.read()).decode()}
            _check(S.put(f"{SERVER}/api/contents/{_q(remote)}", json=body, timeout=300))
        else:
            n = 1
            while True:
                data = fh.read(CHUNK)
                last = fh.tell() >= size
                body = {"type": "file", "format": "base64", "name": local.name,
                        "chunk": -1 if last else n,
                        "content": base64.b64encode(data).decode()}
                _check(S.put(f"{SERVER}/api/contents/{_q(remote)}", json=body, timeout=300))
                if last:
                    break
                n += 1
    print(f"put {local} -> {remote} ({size} bytes)")


def put(local: str, remote: str | None):
    src = Path(local).expanduser()
    if not src.exists():
        sys.exit(f"not found: {src}")
    remote = (remote or src.name).strip("/")
    if src.is_file():
        if "/" in remote:
            _mkdir(remote.rsplit("/", 1)[0])
        _put_file(src, remote)
        return
    skip = {".DS_Store", "__pycache__", ".ipynb_checkpoints", ".git", ".venv"}
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = Path(root).relative_to(src)
        rdir = remote if str(rel) == "." else f"{remote}/{rel.as_posix()}"
        _mkdir(rdir)
        for f in files:
            if f in skip:
                continue
            _put_file(Path(root) / f, f"{rdir}/{f}")


def get(remote: str, local: str | None):
    dst = Path(local or Path(remote).name).expanduser()
    if dst.is_dir():
        dst = dst / Path(remote).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    with S.get(f"{SERVER}/files/{_q(remote)}", stream=True, timeout=300) as r:
        _check(r)
        with dst.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    print(f"get {remote} -> {dst} ({dst.stat().st_size} bytes)")


# ---------------------------------------------------------------- execution
def run_python(code: str, timeout: int = 600, kernel_name: str = "python3", detach_on: str | None = None) -> int:
    """Run code in a fresh kernel and stream its output. With detach_on, disconnect (leaving the kernel running)
    as soon as that marker appears in the output."""
    k = _check(S.post(f"{SERVER}/api/kernels", json={"name": kernel_name}, timeout=60)).json()
    kid = k["id"]
    ws_url = SERVER.replace("https://", "wss://").replace("http://", "ws://")
    ws = websocket.create_connection(
        f"{ws_url}/api/kernels/{kid}/channels",
        header=[f"Authorization: {S.headers['Authorization']}"], timeout=timeout)
    session, msg_id = uuid.uuid4().hex, uuid.uuid4().hex
    ws.send(json.dumps({
        "header": {"msg_id": msg_id, "username": USER, "session": session,
                   "msg_type": "execute_request", "version": "5.3"},
        "parent_header": {}, "metadata": {}, "channel": "shell", "buffers": [],
        "content": {"code": code, "silent": False, "store_history": False,
                    "user_expressions": {}, "allow_stdin": False, "stop_on_error": True},
    }))
    rc, got_reply, idle = 0, False, False
    deadline = time.time() + timeout
    detached = False
    try:
        while not (got_reply and idle):
            if time.time() > deadline:
                print(f"\n[timeout after {timeout}s; interrupting]", file=sys.stderr)
                S.post(f"{SERVER}/api/kernels/{kid}/interrupt", timeout=30)
                return 124
            msg = json.loads(ws.recv())
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            t, c = msg["msg_type"], msg["content"]
            if t == "stream":
                (sys.stderr if c["name"] == "stderr" else sys.stdout).write(c["text"])
                sys.stdout.flush()
                if detach_on and detach_on in c["text"]:
                    detached = True
                    _remember_kernel(kid)
                    print(f"[detached; kernel {kid} keeps running on the server]")
                    return 0
            elif t in ("execute_result", "display_data"):
                txt = c.get("data", {}).get("text/plain")
                if txt:
                    print(txt)
            elif t == "error":
                print("\n".join(c.get("traceback", [])), file=sys.stderr)
                rc = 1
            elif t == "status" and c.get("execution_state") == "idle":
                idle = True
            elif t == "execute_reply":
                got_reply = True
                if c.get("status") != "ok":
                    rc = 1
    finally:
        ws.close()
        if not detached:
            S.delete(f"{SERVER}/api/kernels/{kid}", timeout=30)
    return rc


KERNELS_FILE = Path.home() / ".config" / "jhub" / "launched_kernels.json"


def _remember_kernel(kid: str):
    ids = json.loads(KERNELS_FILE.read_text()) if KERNELS_FILE.exists() else []
    KERNELS_FILE.write_text(json.dumps(sorted(set(ids) | {kid})))


def cleanup_kernels():
    """Shut down supervisor kernels started by `launch` whose job has finished (idle). Other kernels are untouched."""
    ids = set(json.loads(KERNELS_FILE.read_text())) if KERNELS_FILE.exists() else set()
    live = {k["id"]: k for k in _check(S.get(f"{SERVER}/api/kernels", timeout=30)).json()}
    keep = set()
    for kid in ids:
        k = live.get(kid)
        if k is None:
            continue
        if k["execution_state"] == "idle":
            S.delete(f"{SERVER}/api/kernels/{kid}", timeout=30)
        else:
            keep.add(kid)
    KERNELS_FILE.write_text(json.dumps(sorted(keep)))


def launch(cmd: str, name: str, cwd: str = "~/Self-Research", heartbeat: int = 120) -> int:
    """Start a long job on the server that survives this client disconnecting.

    The job runs as its own process group, logging to ~/Self-Research/adm_crc_run/logs/<name>.log. A server-managed
    kernel supervises it and prints a heartbeat while it runs, so the server reports the job as activity (a running
    job is not idle). Stop it with: jhub.py sh 'kill -- -$(cat ~/Self-Research/adm_crc_run/logs/<name>.pid)'."""
    code = (
        "import os, subprocess, time, datetime\n"
        f"cwd = os.path.expanduser({cwd!r}); name = {name!r}\n"
        "logdir = os.path.join(cwd, 'adm_crc_run', 'logs'); os.makedirs(logdir, exist_ok=True)\n"
        "log = open(os.path.join(logdir, name + '.log'), 'ab', buffering=0)\n"
        f"p = subprocess.Popen({cmd!r}, shell=True, executable='/bin/bash', cwd=cwd, stdout=log,\n"
        "                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)\n"
        "open(os.path.join(logdir, name + '.pid'), 'w').write(str(p.pid))\n"
        "print(f'JOB_STARTED pid={p.pid} log={log.name}', flush=True)\n"
        "while p.poll() is None:\n"
        f"    time.sleep({heartbeat})\n"
        "    print(f'{datetime.datetime.now():%H:%M} running', flush=True)\n"
        "open(os.path.join(logdir, name + '.exit'), 'w').write(str(p.returncode))\n"
        "print('JOB_EXIT', p.returncode, flush=True)\n"
    )
    return run_python(code, timeout=120, kernel_name="python3", detach_on="JOB_STARTED")


def run_shell(cmd: str, timeout: int = 600) -> int:
    code = (
        "import subprocess, sys\n"
        f"p = subprocess.Popen({cmd!r}, shell=True, executable='/bin/bash',\n"
        "    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)\n"
        "for line in p.stdout:\n"
        "    print(line, end='', flush=True)\n"
        "rc = p.wait()\n"
        "if rc: raise SystemExit(f'[exit code {rc}]')\n"
    )
    return run_python(code, timeout)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("start"); sub.add_parser("stop")
    p = sub.add_parser("ls"); p.add_argument("path", nargs="?", default="")
    p = sub.add_parser("put"); p.add_argument("local"); p.add_argument("remote", nargs="?")
    p = sub.add_parser("get"); p.add_argument("remote"); p.add_argument("local", nargs="?")
    p = sub.add_parser("py"); p.add_argument("code", nargs="?"); p.add_argument("-f", "--file")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--kernel", default="science", help="kernelspec name (science | python3)")
    p = sub.add_parser("sh"); p.add_argument("command"); p.add_argument("--timeout", type=int, default=600)
    p = sub.add_parser("launch"); p.add_argument("name"); p.add_argument("command")
    p = sub.add_parser("logs"); p.add_argument("name"); p.add_argument("-n", type=int, default=60)
    a = ap.parse_args()

    if a.cmd == "status": status()
    elif a.cmd == "start": start()
    elif a.cmd == "stop": stop()
    elif a.cmd == "ls": ls(a.path)
    elif a.cmd == "put": put(a.local, a.remote)
    elif a.cmd == "get": get(a.remote, a.local)
    elif a.cmd == "py":
        code = Path(a.file).read_text() if a.file else a.code
        if not code:
            sys.exit("give CODE or -f FILE")
        sys.exit(run_python(code, a.timeout, a.kernel))
    elif a.cmd == "sh": sys.exit(run_shell(a.command, a.timeout))
    elif a.cmd == "launch":
        cleanup_kernels()
        sys.exit(launch(a.command, a.name))
    elif a.cmd == "logs":
        d = "~/Self-Research/adm_crc_run/logs"
        sys.exit(run_shell(f"cd {d} && tail -n {a.n} {a.name}.log; echo; "
                           f"if [ -f {a.name}.exit ]; then echo \"[job exited with code $(cat {a.name}.exit)]\"; "
                           f"elif kill -0 $(cat {a.name}.pid) 2>/dev/null; then echo '[job running]'; "
                           f"else echo '[job not running, no exit code recorded]'; fi", 60))


if __name__ == "__main__":
    main()
