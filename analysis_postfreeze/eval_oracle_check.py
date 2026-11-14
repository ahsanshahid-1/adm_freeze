"""Pre-freeze solvability check on the evaluation portfolio (no agents, no GPU).
Builds every formal Tier-2 instance (36 tasks x frozen levels x repetitions 0-4, so it covers 3 or 5 repetitions)
and runs the oracle solver on every partition; also runs the declared-specification graph (F) on each instance and
records that it is rejected. Writes adm_state/outputs/tier2_solvability_evaluation_precheck.json.
Run from ~/Data-Mining: python3 eval_oracle_check.py"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path("adm_code").resolve()))
from adm import stages as S, tasks as T, fixtures as FX
from adm.core import read_json, write_json


def main():
    paths, _ = S.make_paths("crc", Path("adm_local_run"), Path("adm_crc_run"))
    prop = read_json(paths.manifests / "freeze_proposal.json")
    levels = prop["tier2_conditions"]
    keys = sorted({("evaluation", f, t, c, r) for f in S.FAMILIES for t in S.TEMPLATES for c in levels for r in range(5)})
    print("tier-2 levels", levels, "| instances", len(keys), flush=True)
    t0 = time.time()
    T.ensure_instances(paths, keys, workers=8)
    print(f"instances built in {time.time() - t0:.0f}s", flush=True)
    sol = FX.oracle_solvability(paths, keys, print)
    sol.update({"levels": levels, "repetitions": list(range(5)), "seconds": round(time.time() - t0, 1)})
    write_json(paths.outputs / "tier2_solvability_evaluation_precheck.json", sol)
    print("ORACLE_DONE", sol["instances"], "instances,", len(sol["failures"]), "failures", sol["failures"][:10], flush=True)


if __name__ == "__main__":
    main()
