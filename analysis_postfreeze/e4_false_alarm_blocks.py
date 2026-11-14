import json,glob,os,collections
R=os.path.expanduser("~/Data-Mining/adm_crc_run/adm_state")
rs=[json.load(open(p)) for p in glob.glob(f"{R}/outputs/runs/E4/*.json")]
blk=lambda r:(r["dataset_id"],r["repetition_id"]) in {("D2",1),("D4",2)}
print(collections.Counter((r["system_id"],blk(r),r["terminal_state"],int(r.get("verified_completion") or 0)) for r in rs if r["dataset_id"] in ("D2","D4")))
