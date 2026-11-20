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

from PIL import Image
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
.hero { margin: 4px 0 14px }
.hero a { display: block }
.hero img { display: block; width: 100%; height: auto; max-height: 80vh; object-fit: contain; margin: 0 auto;
  background: var(--panel) }
.hero.portrait img { width: auto; max-width: 100% }
.hero figcaption { font: 12.5px/1.4 var(--sans); color: var(--muted); margin-top: 6px; text-align: center }
.panels img { display: block; width: 100%; height: auto; border: 1px solid var(--rule); background: var(--panel) }
.overview { margin: 22px 0 0 }
.overview img { display: block; width: 100%; height: auto; border: 1px solid var(--rule) }
.overview figcaption { font: 13px/1.5 var(--sans); color: var(--muted); margin-top: 6px }
.panels figcaption { font: 12.5px/1.4 var(--sans); color: var(--muted); margin-top: 5px }
@media (max-width: 700px) { .panels { grid-template-columns: minmax(0, 1fr) } }
.swipe { position: relative; width: 100%; max-width: 100%; aspect-ratio: 1600 / 1635; margin: 0 auto;
  overflow: hidden; touch-action: pan-y; user-select: none; cursor: ew-resize; border: 1px solid var(--rule); border-radius: 4px;
  background: var(--panel) }
.swipe img { position: absolute; inset: 0; width: 100%; height: 100%; display: block; pointer-events: none }
.swipe .then { clip-path: inset(0 calc(100% - var(--pos, 50%)) 0 0) }
.swipe .handle { position: absolute; top: 0; bottom: 0; left: var(--pos, 50%); width: 0; pointer-events: none }
.swipe .handle::before { content: ""; position: absolute; top: 0; bottom: 0; left: -1.5px; width: 3px; background: #fffaf0;
  box-shadow: 0 0 0 1px rgba(0,0,0,.35) }
.swipe .knob { position: absolute; top: 50%; left: 0; width: 46px; height: 46px; transform: translate(-50%, -50%);
  border-radius: 50%; background: #fffaf0; box-shadow: 0 2px 8px rgba(0,0,0,.35); display: grid; place-items: center;
  color: #2a241c; font: 600 16px var(--sans) }
.swipe .tag { position: absolute; top: 12px; padding: 6px 10px; font: 600 13px/1 var(--sans); letter-spacing: .08em;
  background: rgba(20,16,12,.72); color: #fffaf0; border-radius: 3px; pointer-events: none }
.swipe .tag.l { left: 12px }
.swipe .tag.r { right: 12px }
.swipe input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; margin: 0; cursor: ew-resize }
.swipe input:focus-visible ~ .handle .knob { outline: 3px solid var(--accent); outline-offset: 3px }
.key { display: flex; flex-wrap: wrap; gap: 8px 20px; list-style: none; padding: 0; margin: 12px 0 0;
  font: 13.5px/1.4 var(--sans); color: var(--muted) }
.key li { display: flex; align-items: center; gap: 8px }
.key .sw { width: 16px; height: 12px; border: 1px solid rgba(0,0,0,.35); display: inline-block }
.timeline { margin: 8px 0 0; padding: 0; list-style: none; border-left: 2px solid var(--rule) }
.timeline li { position: relative; padding: 2px 0 18px 22px; font: 15.5px/1.55 var(--sans) }
.timeline li::before { content: ""; position: absolute; left: -7px; top: 8px; width: 12px; height: 12px; border-radius: 50%;
  background: var(--bg); border: 2px solid var(--accent) }
.timeline .yr { display: block; font: 600 13px var(--sans); letter-spacing: .06em; color: var(--badge) }
"""



def hero(sid, title):
    """The survey's relief render (scripts/figures/relief_make.py), when there is one: web JPEG on the card, the
    lossless PNG behind it."""
    jpg = HERE / "topography" / "renders" / f"{sid}-relief.jpg"
    if not jpg.exists():
        return ""
    import sys
    sys.path.insert(0, str(HERE / "scripts" / "figures"))
    from relief_make import CAPTION
    w, h = Image.open(jpg).size
    png = jpg.with_suffix(".png")
    full = f"renders/{png.name if png.exists() else jpg.name}"
    cap = html.escape(CAPTION.get(sid, "The sheet in relief, raised from its traced contours."))
    return (f'<figure class="hero{" portrait" if h > w else ""}"><a href="{full}"><img loading="lazy" '
            f'src="renders/{jpg.name}" width="{w}" height="{h}" alt="{html.escape(title)}, rendered in relief"></a>'
            f"<figcaption>{cap}</figcaption></figure>\n")

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
  <a class="door" href="fair/"><span class="k">The fair</span><h3>The 1905 Exposition</h3>
    <p>Where the Lewis and Clark Exposition stood on today's map: Guild's Lake, the palaces and the Trail, laid over
    the city that replaced them.</p></a>
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
{hero(sid, sv['title'])}<div class="panels">
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
<p><a class="dl" href="../gis/historic_hydrography.gpkg" download>Download historic_hydrography.gpkg</a>
&nbsp; <span class="note">GeoPackage, {(HERE / "gis" / "historic_hydrography.gpkg").stat().st_size / 1e6:.1f} MB &middot;
Guild's Lake in 1852, 1902 and 1905, Balch Creek then and now, and the Pence flumes and canal, each with its date and
source &middot; <a href="https://github.com/anthonyblackham/guilds-lake-archive/blob/main/gis/README.md#historic-hydrography">README</a></span></p>
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
    fair = """
<figure style="margin:0">
  <div class="swipe" id="swipe" style="--pos:50%">
    <img class="now" src="slider-2025.jpg" alt="The site today: warehouses and rail yards where Guild's Lake was, with street names">
    <img class="then" src="slider-1905.jpg" alt="The 1905 exposition laid over today's aerial: Guild's Lake at fair level, the U.S. Government Building on its peninsula, the Bridge of Nations, the Trail, the American Inn and the exhibit palaces inside the fence">
    <span class="tag l">1905</span><span class="tag r">Today</span>
    <input id="swipe-pos" type="range" min="0" max="100" value="50" step="0.1" aria-label="Slide between the 1905 fair and today">
    <div class="handle"><div class="knob" aria-hidden="true">&#8596;</div></div>
  </div>
  <ul class="key">
    <li><span class="sw" style="background:#efe0b4"></span>Fairgrounds</li>
    <li><span class="sw" style="background:#e8c66a"></span>Exposition buildings</li>
    <li><span class="sw" style="background:#cdbf9f"></span>Roads and walks</li>
    <li><span class="sw" style="background:#b98a55"></span>Bridge of Nations</li>
    <li><span class="sw" style="background:#9fc4d6"></span>Guild's Lake at fair level</li>
    <li><span class="sw" style="background:transparent;border:0;border-top:4px solid #111;height:0;width:18px"></span>Fence</li>
  </ul>
  <figcaption class="note" style="margin-top:8px">Both sides show the 2025 aerial photograph; drag to lay the 1905
  exposition over it. Buildings, roads, the bridge, the fence and the shoreline are traced from the Sanborn fire
  insurance map of the exposition (1905) and the Huber &amp; Maxwell survey (1902). Aerial: City of Portland,
  Summer 2025. Street names: OpenStreetMap contributors. Work in progress.</figcaption>
</figure>
<script>
(() => {
  const box = document.getElementById("swipe"), r = document.getElementById("swipe-pos");
  const set = v => { box.style.setProperty("--pos", v + "%"); r.value = v; };
  r.addEventListener("input", () => set(r.value));
  const at = e => { const b = box.getBoundingClientRect(); return Math.min(100, Math.max(0, (e.clientX - b.left) / b.width * 100)); };
  let drag = false;
  box.addEventListener("pointerdown", e => { drag = true; box.setPointerCapture(e.pointerId); set(at(e)); });
  box.addEventListener("pointermove", e => { if (drag) set(at(e)); });
  ["pointerup", "pointercancel"].forEach(t => box.addEventListener(t, () => { drag = false; }));
})();
</script>

<h2>From lake to fair to industrial district</h2>
<ul class="timeline">
  <li><span class="yr">1852</span>Surveyors walk the edge of Guild's Lake, a shallow lake on the Willamette bottomland
    below the West Hills. An 1883 plat lays city blocks across the water; none are ever built.</li>
  <li><span class="yr">1902&ndash;03</span>Huber &amp; Maxwell survey the lake, and the Olmsted Brothers plan the
    exposition grounds around it.</li>
  <li><span class="yr">1905</span>The Lewis and Clark Centennial Exposition. The lake is raised for the summer, the
    Government Building stands on its peninsula, and the Bridge of Nations crosses the water.</li>
  <li><span class="yr">1906</span>The palaces are sold for salvage: buildings that cost $290,000 bring $5,525. The lake
    drains to a mud flat. <a href="../stories/pence/">Lafe Pence</a> buys the grounds and starts sluicing the hills.</li>
  <li><span class="yr">1909&ndash;14</span>Lewis-Wiley washes the hill under Westover Terraces into the lake bed, and
    subdivisions spread over the hills around the old grounds.</li>
  <li><span class="yr">1920s</span>The Port of Portland pumps river silt over the rest of the lake, and the industrial
    district rises on the fill.</li>
</ul>

<h2>Explore</h2>
<div class="doors">
  <a class="door" href="grounds/"><span class="k">Map &amp; photographs</span><h3>The Official Ground Plan</h3>
    <p>The fair's own 1905 map with a pin for every building: its photographs, floor plans and heights, galleries by
    theme, and the spots where the cameras stood.</p></a>
</div>

<h2>Coming to this page</h2>
<div class="doors">
  <div class="door soon"><span class="k">Data</span><h3>Fair buildings</h3>
    <p>The footprints as a free GeoPackage, with names, concessions and sources.</p></div>
  <div class="door soon"><span class="k">Model</span><h3>The fair in 3D</h3>
    <p>The grounds, the lake and the hills in three dimensions.</p></div>
  <div class="door soon"><span class="k">Story</span><h3>The fair and the lake</h3>
    <p>How a lake nobody wanted became a world's fair, and what the fair set off.</p></div>
</div>

<h2>Related</h2>
<div class="doors">
  <a class="door" href="../stories/pence/"><span class="k">Story</span><h3>Lafe Pence and the Scotch Nubbin</h3>
    <p>The promoter who bought the fair for scrap and set out to wash the hills into the lake.</p></a>
  <a class="door" href="../topography/"><span class="k">Maps &amp; data</span><h3>Historic topography and water</h3>
    <p>The ground and the lake before the fill, from seven surveys, free to download.</p></a>
</div>"""
    write("fair/index.html", page("The 1905 Exposition - Guild's Lake Archive",
                                  [("Guild's Lake Archive", ""), ("The fair", None)],
                                  "<h1>The 1905 Exposition</h1><p>For one summer, Guild's Lake was a world's fair. "
                                  "Drag the map to see where it stood.</p>", fair, 1))

    write("topography/index.html", page("Historic topography - Guild's Lake Archive",
                                        [("Guild's Lake Archive", ""), ("Maps & data", None)],
                                        "<h1>Historic topography</h1><p>The ground before it was cut and filled.</p>", topo, 1))


if __name__ == "__main__":
    main()
