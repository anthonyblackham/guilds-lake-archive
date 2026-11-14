r"""Figures for the Pence story, chapter 2 (the big idea, 1905).

    python scripts/figures/pence_ch2.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch2-*.jpg.
  ch2-ditch-1905   Sunday Oregonian 21 May 1905 p. 31, "Lafe Pence's Ditch and What He Purposes to Accomplish" (as printed)
  ch2-works-map    the Pence Company Canal and High Line Flume as mapped in 1906 (City Archives A2009-009.3473; the
                   user's hand trace, expo-model.gpkg pence_canal_trace_1906_hand), on a muted OpenStreetMap base, with
                   the 1902 lake, Macleay Park, the Scotch Nubbin and Sylvan (the 1905 plan's tunnel route)
"""
import json
import math

import cv2
import matplotlib.patheffects as pe
import numpy as np
from pyogrio.raw import read
from pyproj import Transformer
from shapely import from_wkb
from shapely.affinity import translate
from shapely.geometry import shape

import figstyle as S

P = S.PROJECT
OUT = S.HERE / "stories" / "pence" / "figures"
T = P / "qgis" / "terrain"


def write(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / name), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("wrote", (OUT / name).relative_to(S.HERE))


def page():
    a = cv2.imread(str(P / "sources" / "newspapers" / "sunday-oregonian_1905-05-21_p31_lafe-pences-ditch.jpg"))
    a = a[60:, :]                                        # drop the clipping service's header line
    h, w = a.shape[:2]
    write(cv2.resize(a, (S.WIDTH_PX, round(h * S.WIDTH_PX / w)), interpolation=cv2.INTER_AREA), "ch2-ditch-1905.jpg")


def osm_base(x0, x1, y0, y1, res):
    """Cached OpenStreetMap z13 tiles (qgis/terrain/tile_cache/osm_z13, fetched by the project's scripts) on a 2913 grid."""
    zoom, R = 13, 6378137.0
    gx, gy = np.meshgrid(np.arange(x0, x1, res), np.arange(y1, y0, -res))
    mx, my = Transformer.from_crs(2913, 3857, always_xy=True).transform(gx, gy)
    n = 256 * 2 ** zoom
    px = (mx + math.pi * R) / (2 * math.pi * R) * n
    py = (math.pi * R - my) / (2 * math.pi * R) * n
    tx0, ty0, tx1, ty1 = int(px.min() // 256), int(py.min() // 256), int(px.max() // 256), int(py.max() // 256)
    mosaic = np.full(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), 235, np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            t = cv2.imread(str(T / "tile_cache" / f"osm_z{zoom}" / f"{tx}_{ty}"))
            if t is not None:
                mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = cv2.resize(t, (256, 256))
    osm = cv2.remap(mosaic, (px - tx0 * 256 - 0.5).astype(np.float32), (py - ty0 * 256 - 0.5).astype(np.float32),
                    cv2.INTER_LINEAR)[..., ::-1].astype(np.float32) / 255
    grey = osm.mean(-1, keepdims=True)
    return np.clip(0.42 + 0.58 * (0.35 * osm + 0.65 * grey), 0, 1)       # muted: the routes lead


def scan_1906(x0, x1, y0, y1, res):
    """The Pence Company's 1906 map (City Archives A2009-009.3473), warped onto the 2913 grid with the project's affine
    fit to the PLSS section corners (qgis/georeference/...3473.jgw, residual ~340 ft)."""
    g = P / "qgis" / "georeference" / "A2009-009.3473_map-general-course-pence-company-high-line-flume-and-canal"
    scan = cv2.imread(str(g) + ".jpg")
    a, d, b, e, c, f = [float(v) for v in open(str(g) + ".jgw").read().split()]
    Ai = np.linalg.inv(np.array([[a, b, c], [d, e, f], [0, 0, 1]]))
    gx, gy = np.meshgrid(np.arange(x0, x1, res), np.arange(y1, y0, -res))
    col = Ai[0, 0] * gx + Ai[0, 1] * gy + Ai[0, 2]
    row = Ai[1, 0] * gx + Ai[1, 1] * gy + Ai[1, 2]
    w = cv2.remap(scan, col.astype(np.float32), row.astype(np.float32), cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_CONSTANT, borderValue=(244, 239, 228))
    return w[..., ::-1]


def works_map():
    x0, x1, y0, y1 = 7559000, 7641000, 677500, 736000
    asp = (y1 - y0) / (x1 - x0)
    fig = S.figure(asp * 2 + 0.02)                       # two panels, one above the other, same frame
    h = asp / (asp * 2 + 0.02)
    top = fig.add_axes([0, 1 - h, 1, h])
    top.imshow(scan_1906(x0, x1, y0, y1, 40.0), extent=(x0, x1, y0, y1), interpolation="bilinear")
    top.set_xlim(x0, x1); top.set_ylim(y0, y1); top.set_aspect("equal"); top.axis("off")
    top.text(x1 - 1200, y1 - 2200, "1906: the Pence Company's own map", fontsize=10, fontweight="bold", color=S.INK,
             va="top", ha="right", bbox=dict(boxstyle="round,pad=0.3", fc=S.PAPER, ec="none", alpha=0.9))
    ax = fig.add_axes([0, 0, 1, h])
    ax.imshow(osm_base(x0, x1, y0, y1, 40.0), extent=(x0, x1, y0, y1), interpolation="bilinear")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    ax.text(x1 - 1200, y1 - 2200, "Today: the same routes, traced from it", fontsize=10, fontweight="bold", color=S.INK,
            va="top", ha="right", bbox=dict(boxstyle="round,pad=0.3", fc=S.PAPER, ec="none", alpha=0.9))
    halo = [pe.withStroke(linewidth=3.2, foreground="white")]
    # the 1902 lake
    m, _, g, _ = read(P / "qgis" / "expo-model.gpkg", layer="huber_1902_lakebed_refit")
    for q in from_wkb(g):
        for poly in getattr(translate(q, 20, -10), "geoms", [translate(q, 20, -10)]):
            x, y = poly.exterior.xy
            ax.fill(x, y, color=S.WATER, alpha=0.8, lw=0)
    park = shape(json.loads((T / "macleay_park_1897_2913.geojson").read_text())["features"][0]["geometry"])
    for poly in getattr(park, "geoms", [park]):
        x, y = poly.exterior.xy
        ax.fill(x, y, color="#6f8f5a", alpha=0.35, lw=0)
    # the 1906 routes (user's trace)
    m, _, g, d = read(P / "qgis" / "expo-model.gpkg", layer="pence_canal_trace_1906_hand")
    names = dict(zip(m["fields"], d))["name"]
    ends = {}
    for q, n in zip(from_wkb(g), names):
        x, y = q.xy
        flume = "Flume" in (n or "")
        ax.plot(x, y, color=S.FLUME if not flume else "#a85e14", lw=2.6 if not flume else 2.2,
                ls="-" if not flume else (0, (5, 2.5)), solid_capstyle="round", path_effects=halo)
        ends[n] = (q.coords[0], q.coords[-1])
    tr = Transformer.from_crs(4326, 2913, always_xy=True)
    sylvan = tr.transform(-122.7365, 45.5100)

    def lab(x, y, text, ha="left", color=S.INK, style="normal", weight="normal", size=8):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontstyle=style, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.22", fc=S.PAPER, ec="none", alpha=0.88))

    ax.plot(*sylvan, "o", color=S.INK, ms=5)
    lab(sylvan[0] - 900, sylvan[1] + 2600, "Sylvan: the 1905 plan's\ntunnel route", ha="right", size=7.5)
    ax.plot(7634108, 688467, "^", color=S.CUT, ms=8, mec="white", mew=1)
    lab(7631500, 690300, "Scotch Nubbin", ha="right", color=S.CUT, weight="bold")
    lab(7631800, 686300, "Macleay Park", ha="right", color="#4f6f3a", style="italic", size=7.5)
    lab(7632600, 694800, "Guild's Lake\n(1902)", ha="right", color="#2f5f78", style="italic", size=7.5)
    lab(7566500, 724500, "the Pence Company Canal", color="#a85e14", weight="bold")
    lab(7582500, 733200, "the High Line Flume (dashed)", color="#a85e14", size=7.5)
    lab(7600500, 713500, "Cornelius Pass", ha="center", style="italic", color=S.MUTED, size=7.5)
    lab(7612000, 706500, "along the Linnton road", ha="left", style="italic", color=S.MUTED, size=7.5)
    S.north_arrow(ax, 0.96, 0.82)
    S.scale_bar(ax, x0 + 2500, y0 + 3000, 5280 * 2, "2 miles")
    ax.text(x1 - 500, y0 + 600, "Base map © OpenStreetMap contributors", ha="right", va="bottom", fontsize=6.5, color=S.MUTED)
    S.save(fig, OUT / "ch2-works-map.jpg")


if __name__ == "__main__":
    page()
    works_map()
