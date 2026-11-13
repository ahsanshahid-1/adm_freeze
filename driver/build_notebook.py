"""Assemble adm_kaggle_pipeline.ipynb from the tested package sources in notebook_src/."""
from pathlib import Path

import nbformat as nbf

SRC = Path(__file__).resolve().parent
OUT = SRC.parent / "adm_kaggle_pipeline.ipynb"

MODULES = [
    ("Core utilities: seeds, hashing, paths, session clock", ["adm/__init__.py", "adm/core.py"]),
    ("Datasets: acquisition, canonical import (D1-D4), synthetic generators (D5-D6), splits", ["adm/datasets.py"]),
    ("Shared preprocessing, candidate grids and metrics (Section 10)", ["adm/modeling.py"]),
    ("Task templates, catalogs, contracts, defects, negative controls, hidden references (Sections 6-7)", ["adm/tasks.py"]),
    ("Declarative transform graph engine", ["adm/engine.py"]),
    ("Fixed contract-driven workflow F", ["adm/fixed.py"]),
    ("Internal quality and provenance gates (Section 9.6)", ["adm/gates.py"]),
    ("Instrumented tools, budgets and trusted provenance (Section 13)", ["adm/tools.py"]),
    ("Independent evaluator (Section 14)", ["adm/evaluator.py"]),
    ("Language-model clients (vLLM and the scripted MockLLM)", ["adm/llm.py"]),
    ("Agent state machines: F, single agent, three-role team", ["adm/agents.py"]),
    ("Runner: manifests, worker processes, retries, resumable records", ["adm/runner.py"]),
    ("Clean-data reference workflows and dummy models", ["adm/references.py"]),
    ("Analysis: paired estimates, block bootstrap, Holm, tables, figures (Section 15)", ["adm/analysis.py"]),
    ("Power simulation, limit calibration and protocol freeze", ["adm/power.py"]),
    ("Evaluator fixtures and E6 replay/invariance checks", ["adm/fixtures.py"]),
    ("Model serving (vLLM: Kaggle 2x T4 or CRC 1x RTX PRO 6000)", ["adm/serving.py"]),
    ("Stage orchestration", ["adm/stages.py"]),
    ("Prompts", sorted(str(p.relative_to(SRC)) for p in (SRC / "adm" / "prompts").glob("*.md"))),
    ("Schemas", sorted(str(p.relative_to(SRC)) for p in (SRC / "adm" / "schemas").glob("*.json"))),
    ("Unit, property and isolation tests", sorted(str(p.relative_to(SRC)) for p in (SRC / "tests").glob("*.py"))),
]

INTRO = """# Autonomous and Verifiable Data Mining Using Agentic AI: study pipeline

This notebook implements the protocol in `main-plan.md` end to end: benchmark construction (D1-D6, T1-T6, C0-C6, N1/N2),
the seven systems (F, S0, M0, MQ, MP, SQP, MQP), the independent evaluator, the pilot (E0), the protocol freeze, the formal
experiments (E1, E4, E5, optional E7), replay checks (E6) and the prespecified analysis.

The platform is detected automatically (`PLATFORM = "auto"`): the UA Little Rock CRC JupyterHub server, Kaggle, or local mock mode.

## How to run it on the CRC server (primary)
Hardware: 1 x NVIDIA RTX PRO 6000 Blackwell (96 GB), 64 CPU cores. Follows `main-plan-v2.md`: backbone A
`Qwen/Qwen3.8-27B`, backbone B `google/gemma-4-31B-it`, served one at a time in **BF16** with reasoning mode off. Use the **Python 3 (ipykernel)** kernel; missing packages are installed with `pip install --user`.
1. **Session 1** runs the tests, evaluator fixtures, model preflight and the pilot (E0), then writes
   `adm_crc_run/adm_state/reports/pilot.md` and a freeze proposal. Read the report.
2. **Session 2**: set `FREEZE_CONFIRMED = True` (optionally `FREEZE_REPETITIONS`) and run again. The protocol is frozen and
   the formal experiments run to completion; there is no session time limit.
3. If a session is interrupted (server restart, idle culling), run again: completed runs are kept and skipped.

Everything the notebook creates lives in `adm_crc_run/` next to it and persists: state in `adm_state`, model weights in
`adm_models` and the vLLM environment in `vllm_env` (both reused across sessions).

## How to run it on Kaggle
1. Create a notebook, upload this file, then in **Settings** choose **Accelerator: GPU T4 x2** and **Internet: On**.
2. Click **Save Version -> Save & Run All (Commit)**. Every session runs all cells; the `auto` stage picks the next step.
3. **Session 1** runs the tests, evaluator fixtures, model preflight and the pilot (E0), then writes `adm_state/reports/pilot.md`
   and a freeze proposal. Read the report.
4. **Session 2**: open the notebook, choose **Add Input -> Your Work -> (this notebook's output from the previous version)**,
   set `FREEZE_CONFIRMED = True` in the configuration cell (optionally `FREEZE_REPETITIONS`), and Save & Run All again.
   The protocol is frozen and E1 starts.
5. **Later sessions**: each time, attach the newest output version as input and Save & Run All. Work resumes from the saved
   state; each session stops dispatching new runs at about 10.5 hours and saves everything. The session summary at the end
   says what happens next. The study is complete when `adm_state/reports/final_report.md` exists.

Everything that must persist lives in `/kaggle/working/adm_state` (records, traces, submissions, manifests, reports).
Generated task data and model weights are rebuilt each session under `/tmp` and verified against recorded content digests.

## Running locally
Without Kaggle or the CRC server the notebook runs in **local mock mode**: no GPU, a scripted MockLLM replaces the language model, and a reduced
rehearsal design replaces E1/E4/E5. This tests every component; its numbers are not research results.
"""

CONFIG = '''# ===================== CONFIGURATION (edit here) =====================
import time as _time
NOTEBOOK_START = _time.time()

STAGE = "auto"                 # "auto" | "pilot" | "supplement" | "calibrate" | "calibrate2" | "freeze" | "formal" | "report"
FREEZE_CONFIRMED = False       # set True after reviewing reports/pilot.md
FREEZE_REPETITIONS = None      # e.g. [0, 1, 2, 3]; None = proposal (power-based, at least 3)
FREEZE_LIMIT_OVERRIDES = {}    # e.g. {"aggregate_tokens": 120000}; overrides are recorded in the freeze manifest
ENABLE_E7 = False              # optional budget-sensitivity experiment; must be chosen before E1 starts
CONCURRENCY = None             # concurrent agent runs (None: 8 on CRC/Kaggle, 6 locally); locked at freeze
RUN_TESTS = True               # run the unit/isolation test suite each session
PLATFORM = "auto"              # "auto" | "crc" | "kaggle" | "local"
SESSION_STOP_NEW_HOURS = None  # stop dispatching new runs after this many hours (None: 10.5 on Kaggle/local, no limit on CRC)
SESSION_HARD_STOP_HOURS = None # kill in-flight runs after this many hours (None: 11.25 on Kaggle/local, no limit on CRC)
SESSION_DEADLINE = None        # e.g. "2026-11-11 08:50" (server local time): overrides the two limits above; no new runs
                               # start in the last 35 minutes and the session stops at the deadline, even after a restart
FORCE_MOCK = False             # CRC/Kaggle: use the MockLLM instead of vLLM (plumbing test)
CRC_ROOT = "adm_crc_run"       # CRC only: run root (state + cache), relative to the working directory
LOCAL_ROOT = "adm_local_run"   # local mode only
LOCAL_REHEARSAL = {"families": ["D5", "D6"], "templates": ["T1", "T3"], "conditions": ["C0", "C3", "C6"]}
LOCAL_REPETITIONS = [0, 1]
'''

SETUP = '''import os, sys, json, shutil
from pathlib import Path
if PLATFORM == "auto":
    if os.environ.get("ADM_PLATFORM"):
        PLATFORM = os.environ["ADM_PLATFORM"]
    elif Path("/kaggle/working").exists() and os.environ.get("KAGGLE_KERNEL_RUN_TYPE"):
        PLATFORM = "kaggle"
    elif Path("/srv/exaiops-shared").exists() and "/exaiops/" in os.environ.get("JUPYTERHUB_API_URL", ""):
        PLATFORM = "crc"
    else:
        PLATFORM = "local"
assert PLATFORM in ("crc", "kaggle", "local"), PLATFORM
ON_KAGGLE = PLATFORM == "kaggle"
_unlimited = PLATFORM == "crc"
if SESSION_STOP_NEW_HOURS is None:
    SESSION_STOP_NEW_HOURS = 10_000.0 if _unlimited else 10.5
if SESSION_HARD_STOP_HOURS is None:
    SESSION_HARD_STOP_HOURS = 10_000.0 if _unlimited else 11.25
if SESSION_DEADLINE:
    import datetime as _dt
    _left = (_dt.datetime.fromisoformat(SESSION_DEADLINE).timestamp() - NOTEBOOK_START) / 3600
    if _left <= 0.6:
        raise RuntimeError(f"SESSION_DEADLINE {SESSION_DEADLINE} is less than 36 minutes away; nothing would run")
    SESSION_HARD_STOP_HOURS = _left
    SESSION_STOP_NEW_HOURS = _left - 35 / 60
    print(f"deadline {SESSION_DEADLINE}: new runs stop after {SESSION_STOP_NEW_HOURS:.2f} h, hard stop after {_left:.2f} h")
WORK = Path("/kaggle/working") if ON_KAGGLE else Path.cwd()
os.chdir(WORK)
CODE = Path("adm_code")
if CODE.exists():
    shutil.rmtree(CODE)            # the package is rewritten from this notebook every session
for d in ["adm/prompts", "adm/schemas", "tests"]:
    (CODE / d).mkdir(parents=True, exist_ok=True)
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"
import importlib, importlib.metadata as _md, site, subprocess, sysconfig
PACKAGES = {"numpy": "numpy", "pandas": "pandas", "scipy": "scipy", "sklearn": "scikit-learn", "duckdb": "duckdb",
            "pyarrow": "pyarrow", "matplotlib": "matplotlib", "xlrd": "xlrd", "openpyxl": "openpyxl",
            "jsonschema": "jsonschema", "pytest": "pytest"}
_user = not os.access(sysconfig.get_paths()["purelib"], os.W_OK)  # read-only kernel env (CRC): install with --user
if _user:
    _bin = os.path.join(site.getuserbase(), "bin")                  # ~/.local/bin: pip-installed scripts (pytest, uv)
    if _bin not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")
missing = []
for mod, pkg in PACKAGES.items():
    try:
        importlib.import_module(mod)
    except ImportError:
        missing.append(pkg)
# CRC: bring every package to the latest release for this kernel's Python until the protocol is frozen; after the
# freeze the installed versions are kept so the formal runs use the same stack as the pilot. Elsewhere install only
# what is missing (Kaggle's preinstalled stack is left alone).
_frozen = (WORK / CRC_ROOT / "adm_state" / "manifests" / "freeze.json").exists()
_upgrade = PLATFORM == "crc" and not _frozen
install = list(PACKAGES.values()) if _upgrade else missing
if install:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-warn-script-location", "--disable-pip-version-check",
                    *(["--upgrade"] if _upgrade else []), *(["--user"] if _user else []), *install], check=True)
    if _user:
        site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()
    for mod in PACKAGES:
        importlib.import_module(mod)                                 # fail here, not later, if anything is still missing
PACKAGE_VERSIONS = {pkg: _md.version(pkg) for pkg in PACKAGES.values()}
print("packages:", PACKAGE_VERSIONS)
print("platform:", PLATFORM, "| python:", sys.version.split()[0], "| working directory:", WORK, "| installed:", missing or "nothing")
'''

INIT = '''sys.path.insert(0, str((WORK / CODE).resolve()))
import importlib, adm
from adm import stages as S, runner as R
from adm.core import SessionClock, read_json
from adm.serving import Server, gpu_info, host_info

MODE = PLATFORM
paths, VLLM_ENV = S.make_paths(MODE, Path(LOCAL_ROOT), Path(CRC_ROOT))
restored = S.restore_from_inputs(paths) if ON_KAGGLE else None
user = {"concurrency": CONCURRENCY, "force_mock": FORCE_MOCK or None}
if MODE == "local":
    user.update({"rehearsal": LOCAL_REHEARSAL})
user["package_versions"] = {"python": sys.version.split()[0], **PACKAGE_VERSIONS}
print("session:", S.acquire_session(paths))  # stops leftovers of a killed previous session; refuses if one is live
cfg = S.init_config(paths, MODE, user)
clock = SessionClock(start=NOTEBOOK_START, stop_new_h=SESSION_STOP_NEW_HOURS, hard_stop_h=SESSION_HARD_STOP_HOURS)
server = (Server(VLLM_ENV, paths.models, paths.configs, paths.outputs / "serving_logs",
                 platform="crc" if MODE == "crc" else "kaggle") if cfg["llm"]["mode"] == "vllm" else None)
S.write_deviations(paths)
st = S.state(paths)
print("state:", paths.state, "| stages done:", st["stages"], "| LLM:", cfg["llm"]["mode"])
print("host:", host_info())
print("gpu:", gpu_info() if MODE in ("kaggle", "crc") else "not used in local mode")
print("session limits (h): stop new", SESSION_STOP_NEW_HOURS, "| hard stop", SESSION_HARD_STOP_HOURS)
'''

BUILD = '''build_info = S.stage_build(paths)
for k, v in build_info["canonical"].items():
    print(f"{k:22s} rows={v['rows']:6d} groups={v['groups']:6d} features={v['features']:3d} {v.get('class_counts', '')}")
'''

TESTS = '''if RUN_TESTS:
    code = S.stage_tests(WORK / CODE)
    assert code == 0, "unit tests failed: fix before running experiments"
'''

DECIDE = '''st = S.state(paths)
frozen = (paths.manifests / "freeze.json").exists()
if STAGE == "auto":
    if st["stages"].get("pilot") != "done":
        RUN = ["pilot"]
    elif not frozen:
        RUN = ["freeze", "formal"] if FREEZE_CONFIRMED else ["freeze"]
    elif st["stages"].get("formal") != "done":
        RUN = ["formal"]
    else:
        RUN = ["report"]
else:
    RUN = [STAGE]
print("stages to run this session:", RUN)
'''

PILOT = '''if "pilot" in RUN:
    try:
        S.stage_pilot(paths, cfg, clock, server)
    finally:
        S.stop_llm(paths, server, "E0")
if "supplement" in RUN:  # STAGE = "supplement": supplementary pilot E0S (C1-C5), recorded separately
    try:
        S.stage_pilot_supplement(paths, cfg, clock, server)
    finally:
        S.stop_llm(paths, server, "E0S")
for _cal in ("calibrate", "calibrate2"):  # STAGE = "calibrate2": second Tier-2 calibration E0X2 (X2, X3, X4)
    if _cal in RUN:
        try:
            S.stage_tier2_calibration(paths, cfg, clock, server, which=_cal)
        finally:
            S.stop_llm(paths, server, S.CALIBRATIONS[_cal][0])
'''

FREEZE = '''if "freeze" in RUN:
    reps = FREEZE_REPETITIONS or (LOCAL_REPETITIONS if MODE == "local" else None)
    man = S.stage_freeze(paths, cfg, WORK / CODE, FREEZE_CONFIRMED, reps, FREEZE_LIMIT_OVERRIDES, ENABLE_E7)
    if man is None:
        RUN = [r for r in RUN if r != "formal"]
'''

FORMAL = '''if "formal" in RUN:
    try:
        res = S.stage_formal(paths, cfg, clock, server, WORK / CODE)
        print("formal stage:", res)
    finally:
        S.stop_llm(paths, server, "formal")
if "report" in RUN:
    from adm import references as REF
    refs = REF.build_references(paths, "evaluation", (cfg.get("rehearsal") or {}).get("families", S.FAMILIES),
                                (cfg.get("rehearsal") or {}).get("templates", S.TEMPLATES), cfg["repetitions"])
    S.final_report(paths, cfg, refs, S.stage_e6(paths))
'''

SUMMARY = '''summary = S.session_summary(paths, cfg, clock)
from IPython.display import Markdown, display
for name in (["final_report.md"] + (["pilot_tier2_v2.md"] if "calibrate2" in RUN else [])
             + (["pilot_tier2.md"] if "calibrate" in RUN else [])
             + (["pilot_supplement.md"] if "supplement" in RUN else []) + ["pilot.md", "protocol_freeze.md", "deviations.md"]):
    p = paths.reports / name
    if p.exists():
        display(Markdown(f"---\\n### {name}\\n\\n" + p.read_text()[:60000]))
        break
'''


def writefile_cell(rel: str) -> str:
    text = (SRC / rel).read_text()
    return f"%%writefile adm_code/{rel}\n{text}"


def main():
    nb = nbf.v4.new_notebook()
    cells = [nbf.v4.new_markdown_cell(INTRO),
             nbf.v4.new_markdown_cell("## 1. Configuration"), nbf.v4.new_code_cell(CONFIG),
             nbf.v4.new_markdown_cell("## 2. Environment setup"), nbf.v4.new_code_cell(SETUP),
             nbf.v4.new_markdown_cell("## 3. Study package\nEach cell writes one module of the `adm` package. "
                                      "Do not edit between frozen sessions: the code hash is part of the protocol freeze.")]
    for title, files in MODULES:
        cells.append(nbf.v4.new_markdown_cell(f"### {title}"))
        for f in files:
            cells.append(nbf.v4.new_code_cell(writefile_cell(f)))
    cells += [nbf.v4.new_markdown_cell("## 4. Initialise paths, restore previous session state, load configuration"),
              nbf.v4.new_code_cell(INIT),
              nbf.v4.new_markdown_cell("## 5. Build the benchmark sources (download, checksum, import assertions, splits)"),
              nbf.v4.new_code_cell(BUILD),
              nbf.v4.new_markdown_cell("## 6. Unit, property and isolation tests"), nbf.v4.new_code_cell(TESTS),
              nbf.v4.new_markdown_cell("## 7. Decide what this session runs"), nbf.v4.new_code_cell(DECIDE),
              nbf.v4.new_markdown_cell("## 8. Pilot E0: evaluator fixtures, model preflight, 336 pilot runs, backbone-B smoke test, "
                                       "power simulation and freeze proposal"), nbf.v4.new_code_cell(PILOT),
              nbf.v4.new_markdown_cell("## 9. Protocol freeze (requires `FREEZE_CONFIRMED = True`)"), nbf.v4.new_code_cell(FREEZE),
              nbf.v4.new_markdown_cell("## 10. Formal experiments: E1 -> E5 -> (E7) -> E4, then references, E6 and the final analysis"),
              nbf.v4.new_code_cell(FORMAL),
              nbf.v4.new_markdown_cell("## 11. Session summary and reports"), nbf.v4.new_code_cell(SUMMARY)]
    nb["cells"] = cells
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                      "language_info": {"name": "python"}}
    nbf.write(nb, OUT)
    print(f"wrote {OUT} with {len(cells)} cells")


if __name__ == "__main__":
    main()
