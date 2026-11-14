"""Fetch citation metadata from arXiv abstract pages, slowly (one request every 5 s).

Writes paper/refcheck/arxiv_meta.json: {id: {title, authors, date, comments, journal_ref, doi, fetched_at}}.
Reads the <meta name="citation_*"> tags that arXiv publishes on every abstract page.
Resumable: ids already in the output file are skipped.
"""
import html, json, os, re, sys, time, urllib.request, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "arxiv_meta.json")
IDS = sys.argv[1:]
data = json.load(open(OUT)) if os.path.exists(OUT) else {}


def meta(page, name):
    return [html.unescape(m) for m in re.findall(rf'<meta name="{name}" content="([^"]*)"', page)]


def field(page, cls):
    m = re.search(rf'<td class="tablecell {cls}[^"]*">(.*?)</td>', page, re.S)
    return re.sub(r"<[^>]+>", "", html.unescape(m.group(1))).strip() if m else None


for aid in IDS:
    if aid in data and "abstract" in data[aid]:
        continue
    req = urllib.request.Request(f"https://arxiv.org/abs/{aid}", headers={"User-Agent": "refcheck/1.0 (academic citation check)"})
    for attempt in range(3):
        try:
            page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
            break
        except Exception as ex:  # 429 or network: back off
            print(aid, "retry", attempt, ex, flush=True)
            time.sleep(30 * (attempt + 1))
    else:
        continue
    data[aid] = {
        "title": (meta(page, "citation_title") or [None])[0],
        "authors": meta(page, "citation_author"),
        "date": (meta(page, "citation_date") or [None])[0],
        "comments": field(page, "comments"),
        "journal_ref": field(page, "jref"),
        "doi_field": field(page, "doi"),
        "abstract": (meta(page, "citation_abstract") or [None])[0],
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    json.dump(data, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(aid, "|", data[aid]["title"], "|", len(data[aid]["authors"]), "authors |", data[aid]["date"], flush=True)
    time.sleep(5)
