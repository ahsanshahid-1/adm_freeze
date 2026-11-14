"""Execute adm_kaggle_pipeline.ipynb locally as consecutive 'sessions' (fresh kernel each time),
injecting configuration values the way a user would edit the configuration cell."""
import re
import shutil
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "adm_kaggle_pipeline.ipynb"


def run_session(name: str, overrides: dict, timeout: int = 7200):
    nb = nbformat.read(NB, as_version=4)
    cfg = next(c for c in nb.cells if c.cell_type == "code" and "CONFIGURATION (edit here)" in c.source)
    for k, v in overrides.items():
        cfg.source, n = re.subn(rf"^{k} = .*?(\s+#.*)?$", f"{k} = {v!r}", cfg.source, flags=re.M)
        assert n == 1, k
    t0 = time.time()
    client = NotebookClient(nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}})
    try:
        client.execute()
        status = "ok"
    except Exception as e:
        status = f"error: {type(e).__name__}: {str(e)[:3000]}"
    out = ROOT / "adm_local_run" / f"executed_{name}.ipynb"
    out.parent.mkdir(exist_ok=True)
    nbformat.write(nb, out)
    print(f"=== session {name}: {status} ({(time.time() - t0) / 60:.1f} min) -> {out}", flush=True)
    # print the tail of every output of the last few code cells
    for c in [c for c in nb.cells if c.cell_type == "code"][-6:]:
        for o in c.get("outputs", []):
            txt = o.get("text") or "".join(o.get("data", {}).get("text/plain", "")) or "\n".join(o.get("traceback", []))
            if txt:
                print(txt[-2500:], flush=True)
    return status


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "clean"):
        for d in ["adm_local_run", "adm_code"]:
            shutil.rmtree(ROOT / d, ignore_errors=True)
    if which in ("all", "clean", "s1"):
        run_session("s1_pilot", {})
    if which in ("all", "s2"):
        run_session("s2_freeze_partial", {"FREEZE_CONFIRMED": True, "RUN_TESTS": False, "SESSION_STOP_NEW_HOURS": 0.09})
    if which in ("all", "s3"):
        run_session("s3_resume", {"RUN_TESTS": False})
