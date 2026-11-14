"""Watchdog for the frozen formal run on the CRC JupyterHub server. Runs on the Mac, because a watchdog on the server
dies when the JupyterHub user server is stopped (as at 06:16 CST on 13 Nov 2026).

Every INTERVAL seconds it checks the job. It never edits frozen code, settings or run records.
  * Job alive and records arriving                -> log one status line.
  * Job alive but no new record for STALL_MIN     -> log an ALERT only (no action; a stalled job needs a person).
  * Formal stage done (FORMAL_COMPLETE)           -> back up the state (tgz + sha256), log, and exit.
  * Supervisor ended by itself (exit file present) -> log the log tail and exit WITHOUT relaunching
                                                    (run_rest.sh already retried 4 times; that needs investigation).
  * Job killed (no process, no exit file)         -> due diligence, then relaunch:
        1. start the JupyterHub user server if it is not running, and wait until ready;
        2. record an incident: last run records, serving-log tail (SIGTERM / errors), uptime;
        3. confirm no other notebook session or vLLM of ours is running;
        4. back up the state (tgz, gzip test, record count, sha256);
        5. relaunch `bash run_rest.sh` with the same command as before;
        6. confirm a new nbconvert process and GPU use.
     At most MAX_RESTARTS relaunches; after that it only alerts.
Usage: .venv/bin/python tools/watchdog.py [INTERVAL_S] [MAX_RESTARTS]   (log: adm_crc_run_watchdog.log in repo root)
"""
from __future__ import annotations
import contextlib
import io
import json
import sys
import time
from pathlib import Path

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 300
MAX_RESTARTS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
STALL_MIN = 30
ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "adm_crc_run_watchdog.log"
sys.argv = ["x"]
sys.path.insert(0, str(ROOT / "tools"))
import jhub  # noqa: E402

D = "~/Data-Mining"
R = f"{D}/adm_crc_run/adm_state"
L = f"{D}/adm_crc_run/logs"


def log(msg: str):
    line = f"[{time.strftime('%a %Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def sh(cmd: str, timeout: int = 600) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        jhub.run_shell(cmd, timeout=timeout)
    return buf.getvalue()


def server_running() -> bool:
    u = jhub.S.get(f"{jhub.HUB}/hub/api/users/{jhub.USER}", timeout=30).json()
    return bool((u.get("servers") or {}).get("", {}).get("ready"))


def start_server() -> bool:
    r = jhub.S.post(f"{jhub.HUB}/hub/api/users/{jhub.USER}/server", timeout=60)
    log(f"start server: HTTP {r.status_code}")
    for _ in range(60):
        if server_running():
            return True
        time.sleep(10)
    return False


STATUS = f"""
P=$(cat {L}/formalrest.pid 2>/dev/null)
alive=0; [ -n "$P" ] && [ -e /proc/$P ] && alive=1
ex=$(cat {L}/formalrest.exit 2>/dev/null || echo none)
st=$(/opt/jupyterhub/bin/python3 -c "import json; print(json.load(open('{R}/STATE.json'.replace('~','$HOME')))['stages'].get('formal'))" 2>/dev/null)
n1=$(ls {R}/outputs/runs/E1 2>/dev/null | wc -l); n5=$(ls {R}/outputs/runs/E5 2>/dev/null | wc -l); n4=$(ls {R}/outputs/runs/E4 2>/dev/null | wc -l)
newest=$(find {R}/outputs/runs -name '*.json' -mmin -{STALL_MIN} 2>/dev/null | wc -l)
gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null)
done_=$(grep -c FORMAL_COMPLETE {L}/formalrest.log 2>/dev/null)
echo "STATUS alive=$alive exit=$ex formal=$st E1=$n1 E5=$n5 E4=$n4 recent=$newest gpu=$gpu complete=$done_"
"""


def status() -> dict:
    out = sh(STATUS, 180)
    line = next((l for l in out.splitlines() if l.startswith("STATUS ")), None)
    if not line:
        raise RuntimeError("no status line: " + out[-300:])
    return dict(kv.split("=", 1) for kv in line[7:].split())


def backup(tag: str) -> str:
    out = sh(f"""cd {D}/adm_crc_run && T=$(date +%Y%m%d_%H%M) && f={D}/backups/adm_state_{tag}_$T.tgz &&
tar -czf $f adm_state && gzip -t $f && echo "runs_in_archive E1=$(tar -tzf $f | grep -c 'outputs/runs/E1/.*json$') \
E5=$(tar -tzf $f | grep -c 'outputs/runs/E5/.*json$') E4=$(tar -tzf $f | grep -c 'outputs/runs/E4/.*json$')" &&
cd {D}/backups && sha256sum $(basename $f) | tee $(basename $f).sha256""", 1800)
    return " | ".join(l.strip() for l in out.splitlines() if "runs_in_archive" in l or ".tgz" in l)


def incident() -> str:
    return sh(f"""echo "uptime: $(uptime)"
echo "last records:"; find {R}/outputs/runs -name '*.json' -printf '%TY-%Tm-%Td %TH:%TM:%.2TS %f\\n' | sort | tail -3
f=$(ls -t {R}/outputs/serving_logs/vllm_* 2>/dev/null | head -1); echo "serving log: $f"
grep -E "signal=|ERROR|CUDA|out of memory" $f 2>/dev/null | grep -v '"POST' | head -4 | cut -c1-200
echo "supervisor log tail:"; tail -3 {L}/formalrest.log | cut -c1-160""", 300)


def our_processes() -> str:
    return sh("ps -u $USER -o pid,etime,cmd | grep -E 'nbconvert|vllm serve|run_rest' | grep -v grep | cut -c1-110", 120)


def main():
    restarts, last_n, alerted_stall = 0, None, False
    log(f"watchdog started: interval {INTERVAL}s, max restarts {MAX_RESTARTS}")
    while True:
        try:
            if not server_running():
                log("ALERT: JupyterHub user server is not running")
                if restarts >= MAX_RESTARTS:
                    log("max restarts reached; not restarting. Needs a person.")
                    time.sleep(INTERVAL); continue
                if not start_server():
                    log("ALERT: server did not become ready; retrying next cycle")
                    time.sleep(INTERVAL); continue
                log("server is ready")
            s = status()
            n = f"E1 {s['E1']} E5 {s['E5']} E4 {s['E4']}"
            if s["formal"] == "done" or s["complete"] not in ("0", ""):
                log(f"FORMAL STAGE COMPLETE ({n}). Backing up.")
                log("backup: " + backup("formal_complete"))
                log("watchdog finished")
                return
            if s["alive"] == "1":
                if s["recent"] == "0":
                    if not alerted_stall:
                        log(f"ALERT: job alive but no new run record for {STALL_MIN} min ({n}, gpu {s['gpu']}%). "
                            "No action taken (could be backbone switch or a long stage; check if it persists).")
                        alerted_stall = True
                else:
                    alerted_stall = False
                log(f"ok | {n} | gpu {s['gpu']}% | restarts so far {restarts}")
            elif s["exit"] != "none":
                log(f"ALERT: supervisor ended by itself with exit {s['exit']} ({n}). Not relaunching; investigate.")
                log("incident:\n" + incident())
                return
            else:
                log(f"ALERT: job is not running and left no exit file ({n}): it was killed.")
                if restarts >= MAX_RESTARTS:
                    log("max restarts reached; not relaunching. Needs a person."); time.sleep(INTERVAL); continue
                log("incident:\n" + incident())
                procs = our_processes().strip()
                if "nbconvert" in procs or "vllm serve" in procs:
                    log("ALERT: found our nbconvert/vLLM still running; not relaunching to avoid two sessions:\n" + procs)
                    time.sleep(INTERVAL); continue
                log("backup before relaunch: " + backup("before_relaunch"))
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = jhub.launch("bash run_rest.sh", "formalrest", cwd=D)
                restarts += 1
                log(f"relaunched (rc {rc}, restart {restarts}): " + buf.getvalue().strip().replace("\n", " | "))
                time.sleep(240)
                log("after relaunch: " + our_processes().strip().replace("\n", " | "))
            last_n = n
        except Exception as ex:  # keep watching through network blips
            log(f"check failed: {type(ex).__name__}: {str(ex)[:200]}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
