import sys,os,json,shutil
from pathlib import Path
os.chdir(os.path.expanduser("~/Data-Mining")); sys.path.insert(0,"adm_code")
from adm import stages as S, tasks as T
from adm.core import SYSTEM_SPEC, instance_dirs, read_json
from adm.fixed import oracle_graph
from adm.tools import Budget, ToolSession
paths,_=S.make_paths("crc",Path("adm_local_run"),Path("adm_crc_run")); cfg=read_json(paths.configs/"study.json")
spec=dict(SYSTEM_SPEC["F"]); spec["q"]=spec["p"]=True
for f,r in (("D2",1),("D4",2)):
    T.ensure_instance(paths,"evaluation",f,"T1","C0",r); d=instance_dirs(paths,"evaluation",f,"T1","C0",r)
    sub=Path("/tmp/wex_sub"); shutil.rmtree(sub,ignore_errors=True)
    s=ToolSession("wex",d["visible"],d["trusted"],sub,spec,Budget(cfg["limits"]),{"estimator":0})
    o=s.t_materialize_features(oracle_graph(s.contract,s.catalog)); h=s.handles[o["handle"]]
    rng=s.contract["value_ranges"]
    for c,(lo,hi) in rng.items():
        if c not in h["frames"]["validation"].columns: continue
        tr=h["frames"]["train"][c].astype(float); va=h["frames"]["validation"][c].astype(float)
        out=va[(va<lo-1e-9)|(va>hi+1e-9)]
        if len(out): print(f"{f} rep{r} {c}: train [{tr.min():.4g}, {tr.max():.4g}] -> contract range [{lo:.4g}, {hi:.4g}]; rejected validation values {sorted(out.round(4).tolist())[:3]} (n={len(out)})")
