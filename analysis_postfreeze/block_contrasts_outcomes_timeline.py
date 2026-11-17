import json,glob,os,pandas as pd
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state/outputs")
recs=[json.load(open(p)) for p in glob.glob(R+"/runs/E1/*.json")]
print("time-like keys:",[k for k in recs[0] if any(w in k for w in ("time","start","end","created","finish"))])
df=pd.DataFrame([(r["dataset_id"],r["repetition_id"],r["template_id"],r["condition_id"],r["system_id"],int(r.get("verified_completion") or 0),r["terminal_state"]) for r in recs],columns=["f","r","t","c","s","V","term"])
piv=df.pivot_table(index=["f","r","t","c"],columns="s",values="V")
D=(piv["MQP"]-piv["M0"]).groupby(level=["f","r"]).mean()*100
print("H1 per block (pp):"); print(D.round(1).unstack().to_string())
sub=df.assign(invalid=(df.term=="SUBMITTED")&(df.V==0))
g=sub.groupby("s")
print(pd.DataFrame({"runs":g.size(),"verified":g.V.sum(),"invalid_sub":g.invalid.sum(),"abstained":g.term.apply(lambda x:(x=="ABSTAINED").sum()),
  "budget":g.term.apply(lambda x:(x=="BUDGET_EXCEEDED").sum()),"execution":g.term.apply(lambda x:(x=="EXECUTION_ERROR").sum())}).to_string())
mt=sorted(os.path.getmtime(p) for p in glob.glob(R+"/runs/E1/*.json")+glob.glob(R+"/runs/E4/*.json")+glob.glob(R+"/runs/E5/*.json"))
import datetime as dt
f=lambda x:dt.datetime.utcfromtimestamp(x).strftime("%Y-%m-%d %H:%M UTC")
print("first formal record:",f(mt[0]),"| last formal record:",f(mt[-1]))
