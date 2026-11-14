import json,glob,os,collections,numpy as np,pandas as pd
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
def load(e): return [json.load(open(p)) for p in glob.glob(f"{R}/outputs/runs/{e}/*.json")]
def frame(rs): return pd.DataFrame([(r["dataset_id"],r["repetition_id"],r["template_id"],r["condition_id"],r["system_id"],int(r.get("verified_completion") or 0),r["terminal_state"],r.get("first_failure")) for r in rs],columns=["family","rep","template","condition","system","V","term","ff"])
rng=np.random.default_rng(20261030)
def con(d,w):
    piv=d.pivot_table(index=["family","rep","template","condition"],columns="system",values="V",aggfunc="first").dropna()
    diff=sum(c*piv[s] for s,c in w.items()); D=diff.groupby(level=["family","rep"]).mean().reset_index(name="D")
    est=D.groupby("family")["D"].mean().mean(); fams=[g["D"].to_numpy() for _,g in D.groupby("family")]
    st=[np.mean([v[rng.integers(0,len(v),len(v))].mean() for v in fams]) for _ in range(5000)]
    return f"{100*est:+.1f} [{100*np.quantile(st,.025):+.1f}, {100*np.quantile(st,.975):+.1f}] n={len(piv)}"
e1=frame(load("E1")); e4=frame(load("E4"))
C={"MQP-M0":{"MQP":1,"M0":-1},"P":{"MP":.5,"M0":-.5,"MQP":.5,"MQ":-.5},"Q":{"MQ":.5,"M0":-.5,"MQP":.5,"MP":-.5},"SQP-S0":{"SQP":1,"S0":-1}}
for x in ("X2","X3","X4"):
    print(x,{k:con(e1[e1.condition.str.startswith(x)],w) for k,w in C.items()})
print("E4 MQP-M0:",{t:con(e4[e4.condition.str.startswith("X")==(t=="T2")],{"MQP":1,"M0":-1}) for t in ("T1","T2")}, "all",con(e4,{"MQP":1,"M0":-1}))
print("E4 X4 VCR:",e4[e4.condition.str.startswith("X4")].groupby("system")["V"].mean().round(3).to_dict())
print("E4 terminal:",e4.groupby(["system","term"]).size().unstack(fill_value=0).to_dict("index"))
bad=((e1.family=="D2")&(e1.rep==1))|((e1.family=="D4")&(e1.rep==2))
b=e1[bad]
print("FA blocks runs/system:",b.groupby("system").size().to_dict())
print("FA blocks VCR:",b.groupby(["system"])["V"].mean().round(3).to_dict())
print("FA blocks terminal:",b.groupby(["system","term"]).size().unstack(fill_value=0).to_dict("index"))
print("budget outside FA blocks:",e1[~bad&(e1.term=="BUDGET_EXCEEDED")].groupby("system").size().to_dict())
print("budget in FA blocks:",b[b.term=="BUDGET_EXCEEDED"].groupby("system").size().to_dict())
print("X4 first failure S0/M0:",e1[e1.condition.str.startswith("X4")&e1.system.isin(["S0","M0"])].groupby(["system","ff"]).size().to_dict())
att=glob.glob(f"{R}/attempts/E1/*.json")
print("E1 infra attempts:",len(att)); 
for p in att[:10]:
    a=json.load(open(p)); print(os.path.basename(p)[:45], str({k:a.get(k) for k in ("reason","error","terminal_state","run_error","time","started")})[:220])
e5=frame(load("E5")); print("E5 by cond:",e5.groupby(["condition"]).size().to_dict())
r5=load("E5"); print("E5 false submissions:",collections.Counter((r["system_id"],r["condition_id"]) for r in r5 if r.get("false_submission")))
print("E5 correct refusal by system:",collections.Counter(r["system_id"] for r in r5 if r.get("correct_refusal")))
