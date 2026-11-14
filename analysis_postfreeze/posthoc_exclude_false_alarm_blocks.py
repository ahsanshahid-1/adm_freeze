import json,glob,os,numpy as np,pandas as pd
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
rows=[]
for p in glob.glob(R+"/outputs/runs/E1/*.json"):
    r=json.load(open(p)); rows.append((r["dataset_id"],r["repetition_id"],r["template_id"],r["condition_id"],r["system_id"],int(r.get("verified_completion") or 0)))
df=pd.DataFrame(rows,columns=["family","rep","template","condition","system","V"])
bad=((df.family=="D2")&(df.rep==1))|((df.family=="D4")&(df.rep==2))
rng=np.random.default_rng(20261030)
def contrast(d,w):
    piv=d.pivot_table(index=["family","rep","template","condition"],columns="system",values="V",aggfunc="first")
    diff=sum(c*piv[s] for s,c in w.items())
    D=diff.groupby(level=["family","rep"]).mean().reset_index(name="D")
    est=D.groupby("family")["D"].mean().mean()
    fams=[g["D"].to_numpy() for _,g in D.groupby("family")]
    st=[np.mean([v[rng.integers(0,len(v),len(v))].mean() for v in fams]) for _ in range(10000)]
    return round(100*est,1),[round(100*np.quantile(st,.025),1),round(100*np.quantile(st,.975),1)]
C={"H1 MQP-M0":{"MQP":1,"M0":-1},"Q":{"MQ":.5,"M0":-.5,"MQP":.5,"MP":-.5},"P":{"MP":.5,"M0":-.5,"MQP":.5,"MQ":-.5},
   "QxP":{"MQP":1,"MQ":-1,"MP":-1,"M0":1},"MQP-SQP":{"MQP":1,"SQP":-1},"SQP-S0":{"SQP":1,"S0":-1}}
d=df[~bad]
for lab,sub in [("all",d),("Tier1",d[~d.condition.str.startswith("X")]),("Tier2",d[d.condition.str.startswith("X")]),("noX4",d[~d.condition.str.startswith("X4")])]:
    print(lab,{k:contrast(sub,w) for k,w in C.items()})
print("VCR excl blocks:",d.groupby("system")["V"].mean().round(3).to_dict())
print("Tier1 VCR excl:",d[~d.condition.str.startswith("X")].groupby("system")["V"].mean().round(3).to_dict())
