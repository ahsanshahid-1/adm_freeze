"""Look up bibliographic records on Crossref, one query every 3 s; writes crossref_meta.json.
Usage: crossref_meta.py "key|query" ... (resumable; existing keys are skipped)."""
import json, os, sys, time, urllib.parse, urllib.request, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "crossref_meta.json")
data = json.load(open(OUT)) if os.path.exists(OUT) else {}
for arg in sys.argv[1:]:
    key, q = arg.split("|", 1)
    if key in data:
        continue
    url = ("https://api.crossref.org/works?rows=3&select=DOI,title,author,container-title,issued,volume,issue,page,type&query.bibliographic="
           + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": "refcheck/1.0 (mailto:refcheck@example.org)"})
    for attempt in range(3):
        try:
            items = json.load(urllib.request.urlopen(req, timeout=30))["message"]["items"]
            break
        except Exception as ex:
            print(key, "retry", attempt, ex, flush=True)
            time.sleep(20 * (attempt + 1))
    else:
        continue
    recs = [{"doi": it.get("DOI"), "title": (it.get("title") or [None])[0],
             "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in it.get("author", [])],
             "venue": (it.get("container-title") or [None])[0], "issued": it.get("issued", {}).get("date-parts"),
             "volume": it.get("volume"), "issue": it.get("issue"), "page": it.get("page"), "type": it.get("type")} for it in items]
    data[key] = {"query": q, "results": recs, "fetched_at": dt.datetime.now().isoformat(timespec="seconds")}
    json.dump(data, open(OUT, "w"), indent=1, ensure_ascii=False)
    r = recs[0] if recs else {}
    print(key, "|", r.get("title"), "|", "; ".join(r.get("authors", [])[:8]), "|", r.get("venue"), r.get("issued"), r.get("volume"), r.get("issue"), r.get("page"), "|", r.get("doi"), flush=True)
    time.sleep(3)
