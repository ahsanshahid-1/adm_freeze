import json,os,collections
d=json.load(open(os.path.expanduser("~/_paper_analysis/gate_audit/gate_audit.json"))); rows=d["rows"]
print("instances",d["instances"],"materialized",sum(r["materialized"] for r in rows))
fa=lambda r:(r["family"],r["rep"]) in {("D2",1),("D4",2)}
for lab,sel in [("all",lambda r:True),("Tier1",lambda r:not r["condition"].startswith("X")),("Tier2",lambda r:r["condition"].startswith("X"))]:
    s=[r for r in rows if sel(r)]
    qp=sum(r.get("quality_passed",False) for r in s); pp=sum(r.get("provenance_passed",False) for r in s); both=sum(r.get("quality_passed",False) and r.get("provenance_passed",False) for r in s)
    print(lab,len(s),"Q accepts",qp,"P accepts",pp,"both accept",both)
rej=[r for r in rows if not r.get("quality_passed",True)]
print("Q rejections:",len(rej),"in FA blocks:",sum(fa(r) for r in rej),collections.Counter(f["check"] for r in rej for f in r["quality_failures"]))
prej=[r for r in rows if not r.get("provenance_passed",True)]
print("P rejections:",len(prej),collections.Counter(f["check"] for r in prej for f in r["provenance_failures"]))
print("example details:",[ (r["family"],r["template"],r["condition"],r["rep"],r["quality_failures"][0]["detail"]) for r in rej[:2]])
