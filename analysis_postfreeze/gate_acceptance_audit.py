"""Post-hoc gate-acceptance audit (paper 5). Runs the oracle solver's known-correct workflow for every E1 instance
through the frozen ToolSession, so the frozen quality and provenance gates judge it exactly as in the runs.
Read-only on the study state; scratch output goes to /tmp. Run from ~/Data-Mining with the frozen interpreter.
Output: ~/_paper_analysis/gate_audit/gate_audit.json
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("adm_code").resolve()))
from adm import stages as S  # noqa: E402
from adm import tasks as T  # noqa: E402
from adm.core import FAMILIES, TEMPLATES, SYSTEM_SPEC, instance_dirs, read_json  # noqa: E402
from adm.fixed import oracle_graph  # noqa: E402
from adm.tools import Budget, ToolSession  # noqa: E402

paths, _ = S.make_paths("crc", Path("adm_local_run"), Path("adm_crc_run"))
cfg = read_json(paths.configs / "study.json")
conds = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"] + list(cfg["tier2_conditions"])
out_dir = Path(os.path.expanduser("~/_paper_analysis/gate_audit")); out_dir.mkdir(parents=True, exist_ok=True)
scratch = Path("/tmp/gate_audit_sub")
spec = dict(SYSTEM_SPEC["F"]); spec["q"] = True; spec["p"] = True
t0 = time.time()
for f in FAMILIES:
    part = out_dir / f"gate_audit_{f}.json"
    if part.exists():
        continue
    rows = []
    for t in TEMPLATES:
        for c in conds:
            for r in cfg["repetitions"]:
                T.ensure_instance(paths, "evaluation", f, t, c, r)
                d = instance_dirs(paths, "evaluation", f, t, c, r)
                if scratch.exists():
                    shutil.rmtree(scratch)
                s = ToolSession(f"audit-{f}-{t}-{c}-r{r}", d["visible"], d["trusted"], scratch, spec,
                                Budget(cfg["limits"]), {"estimator": 0})
                o = s.t_materialize_features(oracle_graph(s.contract, s.catalog))
                row = {"family": f, "template": t, "condition": c, "rep": r, "materialized": bool(o.get("materialized")),
                       "error": o.get("error")}
                for v in o.get("gate_verdicts", []):
                    row[v["gate"] + "_passed"] = v["passed"]
                    row[v["gate"] + "_failures"] = [{"check": ck["check"], "detail": str(ck.get("detail", ""))[:300]}
                                                    for ck in v.get("failures", [])]
                rows.append(row)
    json.dump(rows, open(part, "w"), default=str)
    print(f"{time.strftime('%H:%M:%S')} {f} done, {len(rows)} instances, {time.time() - t0:.0f}s", flush=True)
allrows = [x for f in FAMILIES for x in json.load(open(out_dir / f"gate_audit_{f}.json"))]
json.dump({"instances": len(allrows), "rows": allrows}, open(out_dir / "gate_audit.json", "w"), default=str)
print("AUDIT DONE", len(allrows), flush=True)
