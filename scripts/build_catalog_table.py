r"""Build catalog/sources.csv (one row per work) and thumbs/ from the research project's catalogue.

    python scripts/build_catalog_table.py [--project ../lewis-clark-1905]

Step 1 (2026-11-13): the items the project's own catalogue builder assembles (scripts/build_catalog.py in the research
project: Multnomah County Library, LoC stereographs, OSU slides, OHS, UW, City Archives, maps & plans, railroad plats,
...) are mapped onto the archive's fields (catalog/README.md). Later steps add the newspapers, UO prints, Olmsted
papers and the topo sheets.

Thumbnails: the project's 640 px previews are copied to thumbs/<id>.jpg only where the rights class allows
(public-domain or credit); permission-needed and unknown items get a link and credit, no image.
The project folder is read only.
"""
import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FIELDS = ["id", "title", "date", "creator", "kind", "collection", "archive_id", "url_original", "url_mirror",
          "rights", "credit", "thumb", "place", "topics", "used_in", "notes_ref", "description", "local_path"]

KIND = {"stereographs": "photo", "lantern slides": "photo", "photographs": "photo", "postcards": "postcard",
        "maps and plans": "map", "black-and-white photographs": "photo", "clippings": "clipping",
        "business letters": "letter", "forms (documents)": "document", "admission tickets": "ephemera",
        "invitations": "ephemera", "congressional records": "document", "administrative reports": "document",
        "periodicals": "periodical", "receipts (financial records)": "document", "passes (tickets)": "ephemera"}
PREFIX = {"Multnomah County Library": "mcl", "Library of Congress stereographs": "loc-stereo", "OSU lantern slides": "osu",
          "OHS photos": "ohs", "UW photos": "uw", "City Archives photos": "pdx-archives", "UO photos (copies)": "uo-copy",
          "Other photos": "misc", "Newspaper illustrations": "news", "Postcards": "umd", "Maps & plans": "map",
          "Railroad plats": "rrsearch"}


def kind_of(item):
    f = item.get("fmt", "").lower()
    if f in KIND:
        return KIND[f]
    if item["src"] in ("Maps & plans", "Railroad plats"):
        return "map"
    for words, k in ((("photograph", "negative", "portrait"), "photo"), (("letter", "correspondence"), "letter"),
                     (("ticket", "coupon", "pass", "invitation", "menu", "tag", "souvenir", "flier", "letterhead",
                       "badge", "label"), "ephemera"),
                     (("pamphlet", "booklet", "book", "periodical"), "publication"),
                     (("engraving", "sketch", "drawing", "print"), "drawing"),
                     (("record", "resolution", "report", "list", "claim", "document", "form", "minutes"), "document")):
        if any(w in f for w in words):
            return k
    return "item"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80]


def rights(item):
    """(rights class, credit) from what the catalogue records. Classes: pd, credit, permission, unknown."""
    src, m = item["src"], item.get("meta", {})
    if src == "Multnomah County Library":
        r = m.get("Rights & Usage", "")
        return ("pd" if r.lower().startswith(("public domain", "no known")) else "unknown"), "Multnomah County Library"
    if src == "Library of Congress stereographs":
        return "pd", "Library of Congress, Prints & Photographs Division"
    if src == "OSU lantern slides":
        return "pd", "Oregon State University Special Collections & Archives (Flickr Commons, no known copyright restrictions)"
    if src == "OHS photos":
        return "permission", m.get("Collection", "Oregon Historical Society Research Library")
    if src == "UW photos":
        return "permission", "University of Washington Libraries, Special Collections"
    if src == "City Archives photos":
        return "credit", m.get("Collection", "City of Portland Archives & Records Center")
    if src == "Newspaper illustrations":
        return "pd", m.get("Source", "")
    if src == "Postcards":
        return "pd", "University of Maryland Libraries"
    if src == "Railroad plats":
        return "credit", "Oregon Railroad Map Search (rrsearch.aociris.org)"
    if src == "Maps & plans":
        s = m.get("Source", "")
        if "Library of Congress" in s or "Official Guide" in s or "Internet Archive" in s or "Official Catalogue" in s:
            return "pd", s
        if "Olmsted" in s:
            return "credit", "Courtesy of the National Park Service, Frederick Law Olmsted National Historic Site"
        if "Archives" in s or "Multnomah" in s or "County" in s or "Street Railway" in s or "Washington State" in s:
            return "credit", s
        return "unknown", s
    return "unknown", m.get("Source", "")


def collect(project):
    sys.path.insert(0, str(project / "scripts"))
    import build_catalog as bc                     # the project's builder (read only use)
    rows = bc.read_csv("images.csv") if hasattr(bc, "read_csv") else []
    import csv as _csv
    with open(project / "data" / "images.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(_csv.DictReader(f))
    folder, done = bc.mcl_folder({bc.mcl_key(r["Identifier"]): r for r in rows})
    items = list(folder)
    for r in rows:
        if bc.mcl_key(r["Identifier"]) in done:
            continue
        items.append({"src": "Multnomah County Library", "t": r.get("Title", ""), "id": r.get("Identifier", ""),
                      "fmt": r.get("Format.Original", ""), "meta": {k: r[k] for k in bc.FIELDS if r.get(k)},
                      "page": r.get("page_url", ""), "thumb": r.get("thumb", ""), "orig": r.get("image_original", "")})
    for fn in ("stereographs", "osu_slides", "ohs_photos", "uw_photos", "city_archives_photos", "other_photos",
               "postcards", "maps_plans", "railroad_plats"):
        items += getattr(bc, fn)()
    return items


def make_thumb(src, dst, size=640):
    """640 px JPEG from an image (large mosaics read reduced) or a PDF's first page."""
    import cv2
    import numpy as np
    if dst.exists():
        return True
    if src.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(src) as doc:
            pg = doc[0]; z = size / max(pg.rect.width, pg.rect.height)
            pg.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(str(dst), jpg_quality=82)
        return True
    big = src.stat().st_size > 40e6
    im = cv2.imread(str(src), cv2.IMREAD_REDUCED_COLOR_8 if big else cv2.IMREAD_COLOR)
    if im is None:
        return False
    if im.dtype != np.uint8:
        im = cv2.normalize(im, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    k = size / max(im.shape[:2])
    if k < 1:
        im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(dst), im, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return True


def g_titles(project):
    """Titles for the county G-series surveys from the bold entries in the project's g-series README."""
    t = {}
    f = project / "sources" / "multco-survey" / "g-series" / "README.md"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            mm = re.match(r"- \*\*(G\d+/\d+[A-Z]?)\*\*(?: \([^)]*\))?: (.*)", line)
            if mm:
                t[mm.group(1)] = re.sub(r"\*\*", "", mm.group(2))
    return t


def step2(project, have_ids):
    """Topo and survey sheets: the curated table, the county G-series surveys and the county plats."""
    rows = []
    for add in sorted((HERE / "catalog" / "additions").glob("*.csv")):  # curated tables (topo sheets, Olmsted papers)
        with open(add, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(dict(r, local_path=r.pop("file")))
    titles = g_titles(project)
    with open(project / "data" / "sail_g_surveys.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            gid = r["survey_id"]
            if gid in have_ids:
                continue
            fn = project / "sources" / "multco-survey" / "g-series" / (gid.replace("/", "_") + ".PDF")
            desc = titles.get(gid, "")
            q = re.match(r'\s*"([^"]+)"', desc)
            short = q.group(1) if q else re.split(r"(?<![A-Z])\.\s", desc)[0]
            rows.append({"id": "multco-" + slug(gid), "title": f"Multnomah County survey {gid}" + (": " + short[:120] if desc else ""),
                         "date": r.get("survey_date", "").replace("/", "-"), "creator": r.get("surveyor", ""), "kind": "survey",
                         "collection": "Multnomah County Surveyor's Office, Survey and Assessor Image Locator (SAIL), miscellaneous surveys",
                         "archive_id": gid, "url_original": r.get("scan_url", ""), "rights": "credit",
                         "credit": "Multnomah County Surveyor's Office", "description": desc[:500],
                         "place": r.get("dlcs", ""), "notes_ref": "sources/multco-survey/g-series/README.md",
                         "local_path": str(fn.relative_to(project)).replace("\\", "/") if fn.exists() else ""})
    for fn in sorted((project / "sources" / "multco-survey").glob("PL*.pdf")) + sorted((project / "sources" / "multco-survey").glob("PL*.PDF")):
        stem = fn.stem
        pid = stem.split("_")[0].split(" ")[0]
        if pid in have_ids:
            continue
        name = stem[len(pid):].strip(" _-").replace("-", " ").replace("_", " ")
        yr = re.search(r"(18|19)\d\d(-\d\d)?", name)
        rows.append({"id": "multco-plat-" + slug(pid), "title": f"Plat {pid}: {name.title()}", "date": yr.group(0) if yr else "",
                     "creator": "", "kind": "plat", "collection": "Multnomah County Surveyor's Office, subdivision plats",
                     "archive_id": pid, "url_original": "", "rights": "credit", "credit": "Multnomah County Surveyor's Office",
                     "description": "", "place": "", "notes_ref": "",
                     "local_path": str(fn.relative_to(project)).replace("\\", "/")})
    return rows

PAPERS = {  # file prefix: (title, Historic Oregon Newspapers LCCN or "", seq = page?)
    "oregonian": ("Morning Oregonian", "sn83025138", True), "sunday-oregonian": ("Sunday Oregonian", "sn83045782", False),
    "oregon-journal": ("Oregon Daily Journal", "sn85042444", True), "oregon-sunday-journal": ("Oregon Sunday Journal", "", False),
    "hillsboro-argus": ("Hillsboro Argus", "", False), "st-johns-review": ("St. Johns Review", "", False),
    "hillsboro-independent": ("Hillsboro Independent", "", False), "east-oregonian": ("East Oregonian", "", False),
    "portland-labor-press": ("Portland Labor Press", "", False), "morning-astorian": ("Morning Astorian", "", False),
    "washington-county-news": ("Washington County News", "", False), "st-helens-mist": ("St. Helens Mist", "", False),
    "portland-new-age": ("Portland New Age", "", False), "oregon-emerald": ("Oregon Emerald", "", False),
    "medford-mail-tribune": ("Medford Mail Tribune", "", False), "medford-mail": ("Medford Mail", "", False),
    "lake-county-examiner": ("Lake County Examiner", "", False), "eugene-weekly-guard": ("Eugene Weekly Guard", "", False),
    "eugene-daily-guard": ("Eugene Daily Guard", "", False), "daily-capital-journal": ("Daily Capital Journal", "", False),
    "corvallis-times": ("Corvallis Times", "", False), "albany-democrat": ("Albany Democrat", "", False),
}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def parse_paper(name):
    """(paper key, ISO date, page label, page number, slug) from a newspaper file name, or None."""
    m = re.match(r"([a-z-]+)_(\d{4}-\d{2}-\d{2})_((?:s\d+-)?p\d+)_?(.*)", name)
    if m:
        pg = int(re.search(r"p(\d+)", m.group(3)).group(1))
        return m.group(1), m.group(2), m.group(3), pg, m.group(4)
    m = re.match(r"(Morning Oregonian|The Oregon daily journal)\.?, (\w+) (\d+), (\d{4}), Page (\d+)", name)
    if m:
        key = "oregonian" if m.group(1).startswith("Morning") else "oregon-journal"
        d = f"{m.group(4)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(3)):02d}"
        return key, d, "p" + m.group(5), int(m.group(5)), ""
    return None


def looks_like_headline(q):
    """A quoted headline from the notes, not a quoted phrase from the article body."""
    w = [x for x in re.findall(r"[A-Za-z][\w'&.-]*", q) if len(x) > 3]
    return q[0].isupper() and len(w) >= 2 and sum(x[0].isupper() for x in w) >= 0.6 * len(w)


def note_lines(project):
    lines = []
    for f in (project / "notes").glob("*.md"):
        lines += f.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines


def step3(project, have_paths):
    """Newspaper articles in sources/newspapers: one row per article file; crops become the thumbnail."""
    news = project / "sources" / "newspapers"
    timeline = {}
    with open(project / "data" / "pence_timeline.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            for mm in re.finditer(r"sources/newspapers/([^\s;,)]+)", r["source"]):
                timeline.setdefault(Path(mm.group(1)).stem, r["summary"])
    lines = note_lines(project)
    files = sorted(news.glob("*"))
    crops = {}
    for f in files:
        if f.suffix.lower() in (".jpg", ".png", ".jp2"):
            pp = parse_paper(f.stem)
            if pp:
                crops.setdefault((pp[0], pp[1], pp[2]), f)
    rows, used_crops = [], set()
    for f in files:
        if f.suffix.lower() != ".pdf":
            continue
        pp = parse_paper(f.stem)
        if not pp:
            continue
        key, date, plabel, pg, sl = pp
        rel = str(f.relative_to(project)).replace("\\", "/")
        if rel.rsplit(".", 1)[0] in have_paths:
            continue
        paper, lccn, seq_is_page = PAPERS.get(key, (key.replace("-", " ").title(), "", False))
        url = ""
        if lccn:
            url = f"https://oregonnews.uoregon.edu/lccn/{lccn}/{date}/ed-1/" + (f"seq-{pg}/" if seq_is_page else "")
        headline = ""
        for ln in lines:
            if f.name in ln:
                for q in re.findall(r'"([^"*]{8,140})"', ln):
                    if looks_like_headline(q):
                        headline = q; break
                if headline:
                    break
        desc = timeline.get(f.stem, "")
        title = headline or (sl.replace("-", " ").capitalize() if sl else f"{paper}, page {pg}")
        crop = crops.get((key, date, plabel))
        if crop:
            used_crops.add(crop)
        rows.append({"id": "news-" + slug(f"{key}-{date}-{plabel}-{sl}")[:70], "title": title,
                     "date": date, "creator": paper, "kind": "newspaper",
                     "collection": "Historic Oregon Newspapers (University of Oregon Libraries)" if lccn or key in PAPERS else "Newspapers",
                     "archive_id": f"{paper}, {date}, {plabel.replace('-', ' ')}", "url_original": url,
                     "rights": "pd", "credit": f"{paper}, {date}, via Historic Oregon Newspapers",
                     "description": desc[:500], "place": "", "notes_ref": "",
                     "local_path": rel, "_thumb_src": str(crop) if crop else str(f)})
    return rows


def step4(project):
    """UO SCUA PH037 (Angelus Studio): one row per print or negative in sources/uo/PH037; crops (an extra _suffix
    after a print's own name) and the _full copies are not separate works. Titles and call numbers from the
    notes (the user's catalogue titles), place/view/date from data/building_photos.csv."""
    folder = project / "sources" / "uo" / "PH037"
    files = {}
    for f in sorted(folder.glob("*.jpg")):
        files.setdefault(re.sub(r"_full$", "", f.stem), []).append(f)
    stems = set(files)
    works = [st for st in sorted(stems) if not ("_" in st and st.rsplit("_", 1)[0] in stems)]
    lines = note_lines(project)
    bp = {}
    with open(project / "data" / "building_photos.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            bp[r["photo"]] = r
    rows = []
    for st in works:
        L = next((ln for ln in lines if st + "." in ln or st + "**" in ln), "")
        q = re.search(r'\*\*:\s*(?:catalogued as\s*)?"([^"]+)"', L) or re.search(r'"([^"]{8,})"', L)
        call = re.search(r"\[(PH037_[^\]]+)\]", L)
        od = re.search(r"Oregon Digital[^.;]*?\b((?:df|j3|k3)[0-9a-z]{6,8})\b", L) or re.search(r"_((?:df|j3)[0-9a-z]{7})_", st)
        slug_part = re.sub(r"^ph037_(?:uncaptioned_)?(?:b\d+_)?[A-Za-z0-9]+_(?:print_)?", "", st)
        title = q.group(1).replace("\ufffd", "-").strip() if q else slug_part.replace("-", " ").capitalize()
        callno = call.group(1) if call else ""
        if not callno:
            m = re.match(r"ph037_(b\d+)_([A-Za-z0-9]+)_(print_)?", st)
            if m:
                callno = f"PH037_{m.group(1)}_{m.group(2)}" + ("_print" if m.group(3) else "")
        if od:
            url = f"https://oregondigital.org/concern/images/{od.group(1)}"
        elif callno:
            url = "https://oregondigital.org/catalog?q=" + callno.replace("_print_copy1", "")
        else:
            url = ""
        desc = re.sub(r"^.*?\)\.?\s*", "", L.split('"', 2)[-1]).strip() if q else ""
        desc = re.sub(r"\*\*|\(title from the user\)\.?\s*", "", desc).strip()[:500]
        b = bp.get(st, {})
        dm = re.search(r"(1[89]\d\d-\d\d(?:-\d\d)?)$", st)
        date = b.get("date", "") or (dm.group(1) if dm else "")
        small = min(files[st], key=lambda f: f.stat().st_size)
        rows.append({"id": "uo-" + slug(st.replace("ph037_", "ph037-"))[:70], "title": title,
                     "date": date, "creator": "Angelus Studio", "kind": "photo",
                     "collection": "University of Oregon Special Collections & University Archives, PH037 (Angelus Studio)",
                     "archive_id": callno or st, "url_original": url,
                     "rights": "credit",
                     "credit": "Angelus Studio, University of Oregon Libraries, Special Collections & University Archives (PH037)",
                     "description": desc, "place": b.get("place", ""), "notes_ref": "notes/uo_scua_visit.md" if L else "",
                     "local_path": str(small.relative_to(project)).replace("\\", "/"), "_thumb_src": str(small)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, default=HERE.parent / "lewis-clark-1905")
    a = ap.parse_args()
    project = a.project.resolve()
    items = collect(project)
    out, seen = [], set()
    (HERE / "thumbs").mkdir(exist_ok=True)
    for it in items:
        m = it.get("meta", {})
        base = f"{PREFIX.get(it['src'], 'item')}-{slug(it.get('id') or it.get('t', ''))}"
        uid, n = base, 2
        while uid in seen:
            uid, n = f"{base}-{n}", n + 1
        seen.add(uid)
        rc, credit = rights(it)
        thumb = ""
        t = it.get("thumb", "")
        if rc in ("pd", "credit") and t and not t.startswith("http"):
            src = project / t
            if src.exists():
                dst = HERE / "thumbs" / f"{uid}.jpg"
                if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                    shutil.copyfile(src, dst)
                thumb = f"thumbs/{uid}.jpg"
        date = m.get("Date") or m.get("Date.Created") or m.get("Date.Range") or ""
        desc = m.get("Description") or m.get("Notes") or m.get("Summary") or ""
        out.append({
            "id": uid, "title": it.get("t", ""), "date": date, "creator": m.get("Creator", ""),
            "kind": kind_of(it),
            "collection": m.get("Collection") or m.get("Original collection") or it["src"],
            "archive_id": it.get("id", ""), "url_original": it.get("page", ""), "url_mirror": "",
            "rights": rc, "credit": credit, "thumb": thumb,
            "place": m.get("Subject.Place", "") or m.get("Township/Range", ""),
            "topics": m.get("Subject.Topic", ""), "used_in": "", "notes_ref": "",
            "description": re.sub(r"\s+", " ", desc)[:500], "local_path": it.get("orig", ""),
        })
    # step 2: topo and survey sheets (skip what step 1 already has, by archive id)
    have = {r["archive_id"] for r in out} | {Path(r["local_path"]).stem.split("_")[0] for r in out if r["local_path"]}
    have |= {"G2/41A", "G2/41B", "G7/37"}
    for r in step2(project, have):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        thumb = ""
        if r["rights"] in ("pd", "credit") and r.get("local_path"):
            src = project / r["local_path"]
            dst = HERE / "thumbs" / f"{r['id']}.jpg"
            if src.exists() and make_thumb(src, dst):
                thumb = f"thumbs/{r['id']}.jpg"
        row = {k: r.get(k, "") for k in FIELDS}
        row["thumb"] = thumb
        out.append(row)
    # step 3: newspaper articles
    have_paths = {r["local_path"].rsplit(".", 1)[0] for r in out if r["local_path"]}
    for r in step3(project, have_paths):
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        dst = HERE / "thumbs" / f"{r['id']}.jpg"
        thumb = f"thumbs/{r['id']}.jpg" if make_thumb(Path(r["_thumb_src"]), dst) else ""
        row = {k: r.get(k, "") for k in FIELDS}
        row["thumb"] = thumb
        out.append(row)
    # step 4: UO PH037 Angelus prints
    have_paths = {Path(r["local_path"]).stem.replace("_full", "") for r in out if r["local_path"]}
    for r in step4(project):
        if r["id"] in seen or Path(r["local_path"]).stem.replace("_full", "") in have_paths:
            continue
        seen.add(r["id"])
        dst = HERE / "thumbs" / f"{r['id']}.jpg"
        thumb = f"thumbs/{r['id']}.jpg" if make_thumb(Path(r["_thumb_src"]), dst) else ""
        row = {k: r.get(k, "") for k in FIELDS}
        row["thumb"] = thumb
        out.append(row)
    with open(HERE / "catalog" / "sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(out)
    from collections import Counter
    print(f"{len(out)} rows -> catalog/sources.csv")
    print("rights:", dict(Counter(r["rights"] for r in out)))
    print("kinds:", dict(Counter(r["kind"] for r in out)))
    print("thumbnails:", sum(1 for r in out if r["thumb"]), "| no link to original:", sum(1 for r in out if not r["url_original"]))


if __name__ == "__main__":
    main()
