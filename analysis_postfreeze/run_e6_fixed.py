"""Post-run deviation (recorded in outputs/e6_deviation.json): run the E6 replay/invariance audit with ONE line of
adm.fixtures.replay_checks changed, because the frozen line fails under pandas 3 on integer columns:

  frozen:  d.loc[d.index[0], numc[0]] = float(d[numc[0]].iloc[0]) + 1.2345
  used:    d[numc[0]] = d[numc[0]].astype("float64"); d.loc[d.index[0], numc[0]] = float(d[numc[0]].iloc[0]) + 1.2345

The data change the check makes (one value + 1.2345 in an authorised file) is the same. The frozen package on disk is
not modified; the patched function is built from the frozen source text at run time and the diff is asserted to be that
single line. Output: outputs/e6_replay.json in exactly the frozen stage_e6 format, so the unmodified frozen pipeline
then reuses it (stage_e6 returns an existing file) and writes the final report itself.
Run from ~/Data-Mining with /opt/jupyterhub/bin/python3 (the frozen kernel's interpreter).
"""
import difflib
import inspect
import json
import os
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path("adm_code").resolve()))
from adm import fixtures as FX, runner as R, stages as S  # noqa: E402
from adm.core import now_iso, write_json  # noqa: E402

OLD = "d.loc[d.index[0], numc[0]] = float(d[numc[0]].iloc[0]) + 1.2345"
NEW = ('d[numc[0]] = d[numc[0]].astype("float64"); '
       "d.loc[d.index[0], numc[0]] = float(d[numc[0]].iloc[0]) + 1.2345")

src = textwrap.dedent(inspect.getsource(FX.replay_checks))
assert src.count(OLD) == 1, "frozen line not found exactly once"
fixed = src.replace(OLD, NEW)
diff = [l for l in difflib.unified_diff(src.splitlines(), fixed.splitlines(), lineterm="", n=0)
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
assert len(diff) == 2 and diff[0][1:].strip() == OLD and diff[1][1:].strip() == NEW, diff
ns = dict(vars(FX))
exec(compile(fixed, "replay_checks_fixed", "exec"), ns)
replay_fixed = ns["replay_checks"]

paths, _ = S.make_paths("crc", Path("adm_local_run"), Path("adm_crc_run"))
out_path = paths.outputs / "e6_replay.json"
assert not out_path.exists(), "e6_replay.json already exists; not overwriting"

todo = []
for rec in R.load_records(paths, "E1") + R.load_records(paths, "E4"):
    sub = paths.submissions / rec["experiment_id"] / rec["run_id"]
    if (sub / "model.pkl").exists() and rec["terminal_state"] == "SUBMITTED":
        todo.append((rec, sub))
print(f"{now_iso()} retained submissions to check: {len(todo)}", flush=True)
results, t0 = [], time.time()
for i, (rec, sub) in enumerate(todo, 1):
    results.append(replay_fixed(paths, rec, sub, print))
    if i % 10 == 0 or i == len(todo):
        print(f"{now_iso()} {i}/{len(todo)} checked, {time.time() - t0:.0f}s, all passed so far: "
              f"{all(r['all_passed'] for r in results)}", flush=True)
out = {"submissions_checked": len(results), "all_passed": all(r["all_passed"] for r in results) if results else None,
       "results": results}
write_json(out_path, out)
write_json(paths.outputs / "e6_deviation.json", {
    "created": now_iso(), "reason": "frozen E6 wrong-version check raised TypeError under pandas 3 "
    "(Invalid value for dtype int64) after all 8,352 formal runs were recorded; supervisor gave up after 4 attempts",
    "frozen_line": OLD, "line_used": NEW, "diff": diff, "submissions_checked": len(results),
    "all_passed": out["all_passed"], "frozen_package_modified": False})
print("E6 DONE", json.dumps({"submissions_checked": len(results), "all_passed": out["all_passed"]}), flush=True)
