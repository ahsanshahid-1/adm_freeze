import json,glob,os,gzip,collections,math
import numpy as np,pandas as pd
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
def load(e): return [json.load(open(p)) for p in sorted(glob.glob(f"{R}/outputs/runs/{e}/*.json"))]
def ops(rec):
    used=set(); p=os.path.join(R,rec.get("trace_path") or "")
    if not rec.get("trace_path") or not os.path.exists(p): return None
    for line in gzip.open(p,"rt"):
        try: ev=json.loads(line)
        except: continue
        if ev.get("event")!="tool" or ev.get("tool")!="materialize_features": continue
        g=(ev.get("args") or {}).get("graph") or {}
        for n in (g.get("nodes") or []) if isinstance(g,dict) else []:
            if isinstance(n,dict) and n.get("op")=="load" and n.get("policy")=="authoritative_verified": used.add("av")
    return used
E1=load("E1"); E4=load("E4")
blk=lambda r:(r["dataset_id"],r["repetition_id"]) in {("D2",1),("D4",2)}
# A range predicate on F (declared-spec workflow)
def fired(r): return any("value_ranges" in str(f) for g in (r.get("gate_log") or []) for f in (g.get("failures") or []))
F=[r for r in E1 if r["system_id"]=="F"]
for lab,sel in [("Tier1",lambda r: not r["condition_id"].startswith("X")),("X2",lambda r:r["condition_id"].startswith("X2")),("X3",lambda r:r["condition_id"].startswith("X3")),("X4",lambda r:r["condition_id"].startswith("X4"))]:
    s=[r for r in F if sel(r)]
    print("F range fired",lab,sum(fired(r) for r in s),"/",len(s),"| in FA blocks",sum(fired(r) for r in s if blk(r)),"/",sum(1 for r in s if blk(r)))
print("F FA-block abstention reasons",collections.Counter(r.get("abstention_reason") for r in F if blk(r)))
G=[r for r in E1 if r["system_id"] in ("MQ","MQP","SQP") and blk(r)]
print("gated FA-block abstention reasons",collections.Counter((r["system_id"],r.get("abstention_reason")) for r in G if r["terminal_state"]=="ABSTAINED"))
# B gated X4 used-but-failed
for s in ("MP","SQP","MQP"):
    x=[r for r in E1 if r["system_id"]==s and r["condition_id"].startswith("X4")]
    uf=[r for r in x if "av" in (ops(r) or set()) and not r.get("verified_completion")]
    print("X4",s,"used&failed",len(uf),collections.Counter((r["terminal_state"],r.get("first_failure"),blk(r)) for r in uf))
# C Tier1 uptake by condition
rows=[]
for r in E1:
    if r["system_id"]=="F" or r["condition_id"].startswith("X"): continue
    rows.append((r["system_id"],r["condition_id"],int("av" in (ops(r) or set()))))
t=pd.DataFrame(rows,columns=["s","c","u"]).pivot_table(index="s",columns="c",values="u",aggfunc="sum")
print("Tier1 uptake by condition (of 108):"); print(t.to_string())
# D E4 uptake
for s in ("M0","SQP","MQP"):
    x4=[r for r in E4 if r["system_id"]==s and r["condition_id"].startswith("X4")]; t1=[r for r in E4 if r["system_id"]==s and not r["condition_id"].startswith("X")]
    print("E4",s,"X4 used",sum("av" in (ops(r) or set()) for r in x4),"/",len(x4),"verified",sum(int(r.get("verified_completion") or 0) for r in x4),"| T1 used",sum("av" in (ops(r) or set()) for r in t1),"/",len(t1))
# E limit types
c=collections.Counter()
for r in E1+E4:
    if r["terminal_state"]=="BUDGET_EXCEEDED":
        e=str(r.get("run_error") or r.get("error") or "")
        k=next((k for k in ("token","model_call","tool_call","second","wall","evaluation") if k in e.lower()),"other:"+e[:60])
        c[(r["experiment_id"],k)]+=1
print("budget exceeded by limit:",dict(c))
act=[r.get("active_seconds") or 0 for r in E1 if r["system_id"]!="F"]; print("E1 agentic active s max",max(act),"n>=600",sum(a>=600 for a in act))
print("server_gpu_seconds sums:",{e:round(sum(r.get("server_gpu_seconds") or 0 for r in load(e))/3600,2) for e in ("E1","E4","E5")})
# F mixed model with random slope
from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
d=pd.DataFrame([(r["task_id"],f'{r["dataset_id"]}_r{r["repetition_id"]}',float(r["system_id"]=="MQP"),int(r.get("verified_completion") or 0)) for r in E1 if r["system_id"] in ("M0","MQP")],columns=["task","fblock","is_MQP","V"])
for name,vc in [("intercepts",{"task":"0 + C(task)","block":"0 + C(fblock)"}),("with block slope",{"task":"0 + C(task)","block":"0 + C(fblock)","slope":"0 + C(fblock):is_MQP"})]:
    m=BinomialBayesMixedGLM.from_formula("V ~ is_MQP",vc,d); f=m.fit_vb(); i=list(m.exog_names).index("is_MQP"); b,sd=f.fe_mean[i],f.fe_sd[i]
    print("mixed",name,"OR",round(math.exp(b),3),[round(math.exp(b-1.96*sd),3),round(math.exp(b+1.96*sd),3)])
