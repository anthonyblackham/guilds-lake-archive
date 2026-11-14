r"""Build the archive's front door and section pages: index.html (landing), stories/index.html, topography/index.html.

    python scripts/build_pages.py

The topography page lists the surveys from gis/historic_topography.gpkg (layer `surveys`) with download links; the
per-survey showcase cards (original, coloured contours, model) slot in later. All pages share one look with the
story pages (scripts/story_template.html).
"""
import csv
import html
import json
from pathlib import Path

from pyogrio import list_layers
from pyogrio.raw import read

HERE = Path(__file__).resolve().parent.parent
GPKG = HERE / "gis" / "historic_topography.gpkg"

CSS = """
:root { --bg: #f4efe4; --panel: #fbf8f1; --ink: #2a241c; --muted: #6d6354; --rule: #d9cfbd; --accent: #2f5f62;
  --badge: #8a5a2b; --serif: "Source Serif 4", Georgia, "Times New Roman", serif;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif; color-scheme: light }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #1b1915; --panel: #24211c; --ink: #ece4d4;
  --muted: #a89c88; --rule: #3a352c; --accent: #7fb3b0; --badge: #d9a26a; color-scheme: dark } }
:root[data-theme="dark"] { --bg: #1b1915; --panel: #24211c; --ink: #ece4d4; --muted: #a89c88; --rule: #3a352c;
  --accent: #7fb3b0; --badge: #d9a26a; color-scheme: dark }
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.6 var(--serif) }
a { color: var(--accent) }
.wrap { max-width: 1000px; margin: 0 auto; padding-block: 0 72px;
  padding-left: max(18px, env(safe-area-inset-left, 0px)); padding-right: max(18px, env(safe-area-inset-right, 0px)) }
.top { font: 13px var(--sans); padding-block: 18px; display: flex; gap: 18px; flex-wrap: wrap; border-bottom: 1px solid var(--rule) }
.top a { text-decoration: none }
.top .here { color: var(--muted) }
header { padding-block: 44px 24px }
h1 { font: 600 clamp(32px, 6vw, 50px)/1.08 var(--serif); margin: 0 0 12px; letter-spacing: -0.015em; text-wrap: balance }
header p { font: italic 20px/1.45 var(--serif); color: var(--muted); margin: 0; max-width: 62ch }
h2 { font: 600 24px/1.2 var(--serif); margin: 40px 0 10px }
.doors { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 8px }
.door { display: block; background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 20px 20px 18px;
  text-decoration: none; color: inherit }
.door:hover, .door:focus-visible { border-color: var(--accent); outline: none }
.door .k { font: 600 11px var(--sans); text-transform: uppercase; letter-spacing: 0.1em; color: var(--badge) }
.door h3 { font: 600 22px/1.2 var(--serif); margin: 6px 0 8px; color: var(--ink) }
.door p { margin: 0; font: 14.5px/1.5 var(--sans); color: var(--muted) }
.door.soon { opacity: 0.6; pointer-events: none }
.list { display: grid; gap: 14px }
.item { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 16px 18px }
.item h3 { font: 600 20px/1.25 var(--serif); margin: 0 0 4px }
.item .meta { font: 13.5px/1.5 var(--sans); color: var(--muted) }
.item p { margin: 6px 0 0; font: 15px/1.5 var(--sans) }
table { width: 100%; border-collapse: collapse; font: 14px/1.45 var(--sans) }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--rule); vertical-align: top }
th { font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted) }
.scroll { overflow-x: auto }
.dl { display: inline-block; background: var(--accent); color: var(--bg); text-decoration: none; padding: 9px 16px;
  border-radius: 6px; font: 500 15px var(--sans) }
.note { font: 14px/1.55 var(--sans); color: var(--muted) }
.card { margin: 36px 0 0; padding-top: 22px; border-top: 1px solid var(--rule) }
.card h3 { font: 600 22px/1.25 var(--serif); margin: 0 0 4px; text-wrap: balance }
.card .meta { font: 13.5px/1.55 var(--sans); color: var(--muted); margin: 0 0 12px }
.panels { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px }
.panels figure { margin: 0 }
.panels img { display: block; width: 100%; height: auto; border: 1px solid var(--rule); background: var(--panel) }
.overview { margin: 22px 0 0 }
.overview img { display: block; width: 100%; height: auto; border: 1px solid var(--rule) }
.overview figcaption { font: 13px/1.5 var(--sans); color: var(--muted); margin-top: 6px }
.panels figcaption { font: 12.5px/1.4 var(--sans); color: var(--muted); margin-top: 5px }
@media (max-width: 700px) { .panels { grid-template-columns: minmax(0, 1fr) } }
"""


def page(title, crumbs, header_html, body, depth):
    up = "../" * depth
    nav = " ".join((f'<span class="here">{html.escape(t)}</span>' if href is None else f'<a href="{up}{href}">{html.escape(t)}</a>')
                   for t, href in crumbs)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style></head>
<body><div class="wrap">
<nav class="top">{nav}</nav>
<header>{header_html}</header>
<main>{body}</main>
</div></body></html>
"""


def write(rel, text):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print("wrote", rel)


def counts():
    with open(HERE / "catalog" / "sources.csv", newline="", encoding="utf-8") as f:
        n = sum(1 for _ in csv.DictReader(f))
    m, _, _, d = read(GPKG, layer="surveys", read_geometry=False)
    surveys = [dict(zip(m["fields"], row)) for row in zip(*d)]
    return n, surveys


def main():
    n_sources, surveys = counts()
    n_features = int(sum(float(s["features"]) for s in surveys))
    crumbs_home = [("Guild's Lake Archive", None)]
    doors = f"""
<div class="doors">
  <a class="door" href="site/"><span class="k">Sources</span><h3>The catalogue</h3>
    <p>{n_sources:,} photographs, maps, surveys, letters and newspaper pages, each linked to the archive that holds the original.</p></a>
  <a class="door" href="stories/"><span class="k">Stories</span><h3>Illustrated write-ups</h3>
    <p>What the sources say, told with maps and pictures: first, Lafe Pence and the Scotch Nubbin.</p></a>
  <a class="door" href="topography/"><span class="k">Maps &amp; data</span><h3>Historic topography</h3>
    <p>The ground before it was cut and filled: {len(surveys)} surveys traced into {n_features:,} contours and spot heights, free to download (CC BY 4.0).</p></a>
  <div class="door soon"><span class="k">Coming later</span><h3>3D model</h3>
    <p>The fairgrounds, the lake and the hills in three dimensions, before and after.</p></div>
</div>"""
    write("index.html", page("Guild's Lake Archive", crumbs_home,
                             "<h1>Guild's Lake Archive</h1><p>Sources, stories and maps for Guild's Lake, the 1905 Lewis "
                             "and Clark Exposition grounds, and their subsequent development.</p>", doors, 0))

    stories = """
<div class="list">
  <div class="item"><h3><a href="pence/">Lafe Pence and the Scotch Nubbin</a></h3>
    <div class="meta">Draft &middot; seven chapters &middot; 1857-1923</div>
    <p>How a promoter set out to wash the West Hills into Guild's Lake: the water claims, the flume war in Macleay Park,
    the fair bought for scrap, the winter on the Scotch Nubbin, and the banks that failed with his loans on their books.</p></div>
</div>"""
    write("stories/index.html", page("Stories - Guild's Lake Archive", [("Guild's Lake Archive", ""), ("Stories", None)],
                                     "<h1>Stories</h1><p>Illustrated write-ups built from the archive's sources.</p>", stories, 1))

    rows = []
    for s in surveys:
        corr = float(s["datum_correction_ft"])
        rows.append(f"""<tr><td><a href="../site/#{html.escape(s['source_id'])}">{html.escape(s['title'])}</a></td>
<td>{html.escape(s['date'])}</td><td>{html.escape(s['interval'])}</td>
<td>{'none' if corr == 0 else f'{corr:+.1f} ft'}</td><td>{int(float(s['features'])):,}</td></tr>""")
    layers = [L for L, _ in list_layers(GPKG) if L != "surveys"]
    cards = []
    for sv in surveys:
        sid = sv["survey_id"]
        if not (HERE / "topography" / "cards" / f"{sid}-model.jpg").exists():
            continue
        corr = float(sv["datum_correction_ft"])
        lays = ", ".join(f"<code>{L}</code>" for L in layers if L.startswith(sid))
        cards.append(f"""<section class="card" id="{sid}"><h3>{html.escape(sv['title'])}</h3>
<p class="meta">{html.escape(sv['date'])} &middot; {html.escape(sv['surveyor'])} &middot; {html.escape(sv['interval'])}
&middot; datum correction {'none' if corr == 0 else f'{corr:+.1f} ft'}<br>Placed: {html.escape(sv['position'])}; {html.escape(sv['fit'])}
<br>Layers: {lays} &middot; <a href="../site/#{html.escape(sv['source_id'])}">the sheet in the catalogue</a></p>
<div class="panels">
<figure><a href="cards/{sid}-original.jpg"><img loading="lazy" src="cards/{sid}-original.jpg" alt="The {html.escape(sv['title'])} as printed"></a><figcaption>The sheet</figcaption></figure>
<figure><a href="cards/{sid}-contours.jpg"><img loading="lazy" src="cards/{sid}-contours.jpg" alt="Traced contours coloured by height"></a><figcaption>Traced lines, coloured by height</figcaption></figure>
<figure><a href="cards/{sid}-model.jpg"><img loading="lazy" src="cards/{sid}-model.jpg" alt="Reconstructed ground, shaded relief coloured by height"></a><figcaption>The ground they describe</figcaption></figure>
</div></section>""")
    cards = "".join(cards)
    topo = f"""
<p>Contours and spot heights traced from the historic surveys of Guild's Lake and the hills behind it, from 1896 to
about 1910, before and during the sluicing and filling that reshaped the ground. Every line carries the height printed
on the sheet and its height on the City of Portland datum, how it was traced, and a link to the sheet it came from.</p>
<p><a class="dl" href="../gis/historic_topography.gpkg" download>Download historic_topography.gpkg</a>
&nbsp; <span class="note">GeoPackage, {GPKG.stat().st_size / 1e6:.1f} MB &middot; EPSG:2913 (Oregon North, feet) &middot;
{len(layers)} layers + survey index &middot; <a href="https://github.com/anthonyblackham/guilds-lake-archive/blob/main/gis/README.md">README</a>
&middot; <a href="https://github.com/anthonyblackham/guilds-lake-archive/blob/main/gis/LICENSE">CC BY 4.0</a></span></p>
<figure class="overview"><a href="overview.jpg"><img src="overview.jpg" alt="Every survey's traced contours, coloured by height, over today's ground, each titled on its own lines"></a>
<figcaption>Seven surveys, 1896&ndash;1910, on today's ground: every traced line on one height scale over the 2025
aerial photograph and the lidar bare earth. Each title sits on the part of the map that drawing supplies.</figcaption></figure>
<h2>The surveys</h2>
<div class="scroll"><table><thead><tr><th>Survey</th><th>Date</th><th>Interval</th><th>Datum correction</th><th>Features</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">Each survey's title links to its sheet in the catalogue. Below, each survey three ways, all in the
sheet's own frame and orientation: the sheet as printed, the traced lines coloured by height, and the ground they
describe as shaded relief in the same colours. Click any panel for the full-size image.</p>
{cards}"""
    write("topography/index.html", page("Historic topography - Guild's Lake Archive",
                                        [("Guild's Lake Archive", ""), ("Maps & data", None)],
                                        "<h1>Historic topography</h1><p>The ground before it was cut and filled.</p>", topo, 1))


if __name__ == "__main__":
    main()
