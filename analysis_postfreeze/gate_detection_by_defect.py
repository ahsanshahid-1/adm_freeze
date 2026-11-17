import json,glob,os
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state/outputs/runs/E1")
F=[json.load(open(p)) for p in glob.glob(R+"/*-F-none.json")]
fa=lambda r:(r["dataset_id"],r["repetition_id"]) in {("D2",1),("D4",2)}
def fails(r,gate,key): return any(g["gate"]==gate and any(key in str(f) for f in g.get("failures",[])) for g in r.get("gate_log") or [])
for c,gate,key in (("X2b","quality","record_coverage"),("X3a","quality","value_ranges"),("X4b","provenance","content_hash")):
    s=[r for r in F if r["condition_id"]==c]; o=[r for r in s if not fa(r)]
    print(c,gate,key,"detected",sum(fails(r,gate,key) for r in s),"/",len(s),"| outside FA blocks",sum(fails(r,gate,key) for r in o),"/",len(o))
