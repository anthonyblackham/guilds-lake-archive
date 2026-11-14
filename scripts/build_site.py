r"""Build the browsable index: site/index.html from catalog/sources.csv and scripts/site_template.html.

    python scripts/build_site.py

The catalogue is embedded in the page as JSON (no server needed; opens from disk or GitHub Pages). Thumbnails are
referenced as ../thumbs/<id>.jpg. local_path is left out of the page.
"""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

HOLDERS = [  # (holder, keywords searched in collection + credit + id), first match wins
    ("Library of Congress", ["library of congress", "loc-"]),
    ("Multnomah County Library", ["multnomah county library", "mcl-"]),
    ("University of Oregon", ["university of oregon special", "ph037", "uo photos"]),
    ("Historic Oregon Newspapers", ["historic oregon newspapers", "news-"]),
    ("University of Washington", ["university of washington"]),
    ("Oregon Historical Society", ["oregon historical society"]),
    ("Oregon State University", ["lantern slides", "oregon state university"]),
    ("City of Portland Archives", ["city of portland archives"]),
    ("Multnomah County Surveyor", ["multnomah county surveyor", "multnomah county surv", "multco.us/surveyimages"]),
    ("Internet Archive", ["archive.org"]),
    ("Geographicus", ["geographicus"]),
    ("Oregon State Archives", ["oregon state archives"]),
    ("University of Maryland", ["university of maryland"]),
    ("Oregon Railroad Map Search", ["railroad plats", "rrsearch"]),
    ("Olmsted NHS", ["olmsted national historic site", "national park service"]),
    ("USGS", ["geological survey"]),
]


def holder(r):
    hay = " ".join((r["collection"], r["credit"], r["id"], r["url_original"])).lower()
    for name, keys in HOLDERS:
        if any(k in hay for k in keys):
            return name
    return "Other"


def year(d):
    m = re.search(r"(1[789]\d\d|20\d\d)", d or "")
    return int(m.group(1)) if m else None


MON = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


def sort_key(d):
    """An ISO-like key (YYYY-MM-DD, missing parts as 00) from the catalogue's mixed date styles."""
    d = (d or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", d)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?(?!\d)", d)
    if m and int(m.group(2)) <= 12:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3) or '00'}"
    y = re.search(r"(1[789]\d\d|20\d\d)", d)
    if not y:
        return ""
    mo = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?", d.lower())
    day = re.search(r"(?<![\d/])(\d{1,2})(?![\d/])", d.replace(y.group(1), ""))
    return f"{y.group(1)}-{MON[mo.group(1)]:02d}-{int(day.group(1)) if day and mo else 0:02d}" if mo else f"{y.group(1)}-00-00"


def main():
    with open(HERE / "catalog" / "sources.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keep = ["id", "title", "date", "creator", "kind", "collection", "archive_id", "url_original", "url_mirror",
            "rights", "credit", "thumb", "place", "description", "notes_ref"]
    items = []
    for r in rows:
        it = {k: r[k] for k in keep if r.get(k)}
        it["holder"] = holder(r)
        y = year(r["date"])
        if y:
            it["year"] = y
        k = sort_key(r["date"])
        if k:
            it["sk"] = k
        if it.get("thumb"):
            it["thumb"] = "../" + it["thumb"]
        items.append(it)
    data = json.dumps(items, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = (HERE / "scripts" / "site_template.html").read_text(encoding="utf-8").replace("/*CATALOG*/[]", data)
    (HERE / "site").mkdir(exist_ok=True)
    (HERE / "site" / "index.html").write_text(page, encoding="utf-8")
    hc = {}
    for it in items:
        hc[it["holder"]] = hc.get(it["holder"], 0) + 1
    print(f"{len(items)} items -> site/index.html ({len(page) / 1e6:.1f} MB)")
    print(dict(sorted(hc.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
