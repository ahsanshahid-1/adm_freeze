import json,glob,os,collections
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
recs=[json.load(open(p)) for p in glob.glob(R+"/outputs/runs/E1/*.json")]
F1=[r for r in recs if r["system_id"]=="F" and not r["condition_id"].startswith("X") and not r.get("verified_completion")]
print("reps:",collections.Counter((r["dataset_id"],r["repetition_id"]) for r in F1))
print(json.dumps(F1[0]["gate_log"])[:1500])
fails=collections.Counter()
for r in F1:
    for g in (r.get("gate_log") or []):
        for c in (g.get("failed") or g.get("failures") or []):
            fails[(g.get("gate"),str(c)[:90])]+=1
print(fails.most_common(8))
# gated agents on D2/D4: VCR by rep
for s in ("MQ","MQP","SQP","MP","M0","S0"):
    t=collections.defaultdict(list)
    for r in recs:
        if r["system_id"]==s and r["dataset_id"] in ("D2","D4") and not r["condition_id"].startswith("X"):
            t[(r["dataset_id"],r["repetition_id"])].append(int(r.get("verified_completion") or 0))
    print(s,{k:round(sum(v)/len(v),2) for k,v in sorted(t.items())})
