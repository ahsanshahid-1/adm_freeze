import json,os,sys,collections
sys.path.insert(0,os.path.expanduser("~/Data-Mining/adm_code"))
import pandas as pd
from pathlib import Path
from adm import stages as S
from adm.core import instance_dirs, read_json
os.chdir(os.path.expanduser("~/Data-Mining"))
paths,_=S.make_paths("crc",Path("adm_local_run"),Path("adm_crc_run"))
d=json.load(open(paths.outputs/"e6_replay.json"))
cls=collections.Counter(); subs=collections.defaultdict(set)
for r in d["results"]:
    rec=json.load(open(paths.outputs/"runs"/r["run_id"].split("-")[0]/f'{r["run_id"]}.json'))
    dirs=instance_dirs(paths,rec["suite"],rec["dataset_id"],rec["template_id"],rec["condition_id"],rec["repetition_id"])
    cat=read_json(dirs["private"]/"catalog.json"); tab=next(t for t,v in cat["tables"].items() if v["grain"]=="observation")
    f=next(x for x in cat["tables"][tab]["files"] if x["version"]=="v2"); df=pd.read_parquet(dirs["private"]/f["path"])
    applied=any(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns if c!="_shard")
    g=read_json(paths.submissions/rec["experiment_id"]/r["run_id"]/"graph.json")
    verified_load=any(n.get("op")=="load" and n.get("policy")=="authoritative_verified" for n in g["nodes"])
    for k,v in r["checks"].items():
        if v["passed"]: continue
        if k=="wrong_version_detected" and not applied: c="no corruption applied (all numeric columns string-encoded)"
        elif verified_load: c="hash-verifying load fell back to intact replica"
        elif v["detail"]: c="corruption flagged with a different code: "+",".join(v["detail"])
        else: c="other: "+rec["condition_id"]
        cls[(k,c)]+=1; subs[c].add(r["run_id"])
for k,v in sorted(cls.items()): print(v,k)
print({c:len(s) for c,s in subs.items()})
