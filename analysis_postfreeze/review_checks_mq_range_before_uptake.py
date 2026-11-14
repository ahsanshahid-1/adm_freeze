import json,glob,os,gzip,collections
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
recs=[json.load(open(p)) for p in glob.glob(f"{R}/outputs/runs/E1/*.json")]
blk=lambda r:(r["dataset_id"],r["repetition_id"]) in {("D2",1),("D4",2)}
F=[r for r in recs if r["system_id"]=="F" and r["condition_id"]=="X4b" and not blk(r)]
fx=[r for r in F if any("value_ranges" in str(f) for g in r.get("gate_log") or [] for f in g.get("failures") or [])]
print("F X4 outside FA blocks: range fired",len(fx),"/",len(F),collections.Counter(r["task_id"] for r in fx))
print("example failing checks:",[g for g in fx[0]["gate_log"] if not g["passed"]][:2])
def seq(r):
    out=[]; p=os.path.join(R,r["trace_path"])
    for line in gzip.open(p,"rt"):
        try: ev=json.loads(line)
        except: continue
        if ev.get("event")!="tool": continue
        t=ev.get("tool"); s=json.dumps(ev.get("obs") or "")[:20000]
        if t=="materialize_features":
            g=(ev.get("args") or {}).get("graph") or {}
            if any(isinstance(n,dict) and n.get("policy")=="authoritative_verified" for n in g.get("nodes") or []): out.append("AV")
        if "value_ranges" in s and ('"passed": false' in s or "passed\": false" in s or "out-of-range" in s): out.append("RANGE_FAIL")
    return out
for s in ("MQ","M0","S0"):
    x=[r for r in recs if r["system_id"]==s and r["condition_id"]=="X4b"]
    c=collections.Counter()
    for r in x:
        q=seq(r); 
        if "AV" in q: c["used"]+=1; c["range_fail_before_first_use"]+= ("RANGE_FAIL" in q[:q.index("AV")])
        c["range_fail_any"]+=("RANGE_FAIL" in q)
    print(s,dict(c))
print("trace tool event keys:",list(json.loads(next(l for l in gzip.open(os.path.join(R,x[0]["trace_path"]),"rt") if '"tool"' in l)).keys()))
mq=[r for r in recs if r["system_id"]=="MQ" and r["condition_id"]=="X4b"]
c=collections.Counter()
for r in mq:
    q=seq(r)
    if "AV" in q: c[("used", r["template_id"], "range_fail_before" if "RANGE_FAIL" in q[:q.index("AV")] else "no_range_fail_before")]+=1
print(sorted(c.items()))
