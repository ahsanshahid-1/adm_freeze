import json,glob,os,collections
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state/outputs")
c=collections.Counter()
for e in ("E1","E4"):
    for p in glob.glob(f"{R}/runs/{e}/*.json"):
        r=json.load(open(p)); sub=f"{R}/submissions/{e}/{r['run_id']}"
        if os.path.exists(sub+"/model.pkl"):
            c[(e,"retained")]+=1
            if r["terminal_state"]=="SUBMITTED": c[(e,"retained_and_submitted")]+=1
    c[(e,"runs")]=len(glob.glob(f"{R}/runs/{e}/*.json"))
print(dict(c))
