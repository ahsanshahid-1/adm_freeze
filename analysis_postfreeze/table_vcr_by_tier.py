import json,glob,os,pandas as pd
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
d=pd.DataFrame([(r["system_id"],r["condition_id"],int(r.get("verified_completion") or 0)) for r in (json.load(open(p)) for p in glob.glob(R+"/outputs/runs/E1/*.json"))],columns=["s","c","V"])
g=lambda m: d[m].groupby("s")["V"].agg(["mean","size"])
t=pd.concat({"T1":g(~d.c.str.startswith("X")),"T2":g(d.c.str.startswith("X")),"All":g(d.c==d.c),"T2noX4":g(d.c.isin(["X2b","X3a"])),"X4":g(d.c=="X4b")},axis=1)
print(t.round(3).to_string())
