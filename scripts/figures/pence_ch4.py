r"""Figures for the Pence story, chapter 4 (the fair, bought for scrap, Dec 1905 - 1906).

    python scripts/figures/pence_ch4.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch4-*.jpg.
  ch4-buildings-map       the fair buildings Pence bought (names from the Dec 1905 / May 1906 reports, matched to the
                          project's Sanborn-derived 'buildings' layer), on the 1902-03 ground (combined_dem) and lake
  ch4-perspective-1906    Oregonian 4 May 1906 p. 11, "Perspective map showing route of Lafe Pence's electric line ..."
"""
import cv2
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.patches import Patch
from pyogrio.raw import read
from shapely import from_wkb
from shapely.affinity import translate

import figstyle as S

P = S.PROJECT
OUT = S.HERE / "stories" / "pence" / "figures"
T = P / "qgis" / "terrain"

DEC_STATE = {"Agricultural & Horticultural Building", "Oriental Building", "Oregon Building", "Auditorium",
             "Fire Dept. Station, Photo Gallery, Express Office (entrance row)", "Police Station",
             "Administration Building Colonnade"}                        # paid 28 Dec 1905, $2,725
DEC_OTHER = {"California Building", "Washington Building", "Foreign Palace",
             "Machinery, Electricity and Transportation Building"}       # late Dec 1905 / sold on to him by Jan 1906
MAY_GOVT = {"U. S. Government Building", "Fisheries Building", "Forestry and Irrigation Building", "Alaska Building",
            "U. S. Life Saving Station"}                                 # 22 May 1906, $3,000 with annexes
DEC_COL, MAY_COL = "#c0661e", "#7a3e0e"


def buildings_map():
    x0, x1, y0, y1 = 7634150, 7638350, 688950, 693750
    cell = 3.0
    a = cv2.imread(str(T / "combined_dem.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (T / "combined_dem.tfw").read_text().split()]
    gx, gy = np.meshgrid(np.arange(x0, x1, cell), np.arange(y1, y0, -cell))
    z = cv2.remap(a, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32),
                  cv2.INTER_LINEAR, borderValue=-9999)
    z = np.where(z > -9000, z, np.nan)
    gy_, gx_ = np.gradient(np.nan_to_num(z, nan=np.nanmin(z)), cell)
    sl = np.arctan(np.hypot(gx_, gy_) * 2.0)
    shade = np.clip(np.sin(0.7) * np.cos(sl) + np.cos(0.7) * np.sin(sl) * np.cos(np.radians(315) - np.arctan2(-gx_, gy_)), 0, 1)
    shade = np.where(np.isfinite(z), shade, 0.85)
    fig = S.figure((y1 - y0) / (x1 - x0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(shade, cmap="gray", extent=(x0, x1, y0, y1), vmin=-0.6, vmax=1.2, interpolation="bilinear")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    m, _, g, _ = read(P / "qgis" / "expo-model.gpkg", layer="huber_1902_lakebed_refit")
    for q in from_wkb(g):
        q = translate(q, 20, -10)
        for poly in getattr(q, "geoms", [q]):
            xs, ys = poly.exterior.xy
            ax.fill(xs, ys, color=S.WATER, alpha=0.55, lw=0)
    m, _, g, d = read(P / "qgis" / "expo-model.gpkg", layer="buildings")
    names = dict(zip(m["fields"], d))["display_name"]
    found = set()
    for q, n in zip(from_wkb(g), names):
        for poly in getattr(q, "geoms", [q]):
            xs, ys = poly.exterior.xy
            if n in DEC_STATE or n in DEC_OTHER:
                ax.fill(xs, ys, color=DEC_COL, lw=0); found.add(n)
            elif n in MAY_GOVT:
                ax.fill(xs, ys, color=MAY_COL, lw=0); found.add(n)
            elif n == "Emergency Hospital":
                ax.fill(xs, ys, color=S.BUILT, alpha=0.6, lw=0); ax.plot(xs, ys, color=S.INK, lw=1.6); found.add(n)
            else:
                ax.fill(xs, ys, color=S.BUILT, alpha=0.45, lw=0)
    missing = (DEC_STATE | DEC_OTHER | MAY_GOVT) - found
    if missing:
        print("not in the buildings layer:", missing)

    def lab(x, y, text, ha="left", color=S.INK, style="normal", weight="normal", size=7.5):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontstyle=style, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.2", fc=S.PAPER, ec="none", alpha=0.85))

    lab(7635700, 693330, "Government Building\nand annexes", color=MAY_COL, weight="bold")
    lab(7634300, 693520, "fill behind the Government\nBuilding (approx.)", style="italic", color=S.MUTED, size=7)
    lab(7634260, 691150, "Cottel tract\n(approx.)", style="italic", color=S.MUTED, size=7)
    # each building Pence bought, labelled on the building along its long axis when the name fits; small ones get a
    # short leader instead. The Emergency Hospital label sits directly west of it.
    shapes = {}
    for q, n in zip(from_wkb(g), names):
        if n in DEC_STATE or n in DEC_OTHER or n == "Emergency Hospital":
            for poly in getattr(q, "geoms", [q]):
                if n not in shapes or poly.area > shapes[n].area:
                    shapes[n] = poly
    SHORT = {"California Building": "California", "Washington Building": "Washington", "Oriental Building": "Oriental",
             "Oregon Building": "Oregon", "Police Station": "Police", "Foreign Palace": "Foreign Exhibits",
             "Agricultural & Horticultural Building": "Agricultural", "Administration Building Colonnade": "Colonnade",
             "Fire Dept. Station, Photo Gallery, Express Office (entrance row)": "Fire station",
             "Auditorium": "Auditorium", "Machinery, Electricity and Transportation Building": "Machinery & Transportation"}
    LEADER = {   # where the label goes if it doesn't fit on the building (ft), and its alignment
        "California Building": (7635800, 689760, "right"), "Washington Building": (7635900, 690080, "right"),
        "Oregon Building": (7636560, 689130, "right"), "Police Station": (7636300, 689090, "right"),
        "Administration Building Colonnade": (7636950, 689250, "left"),
        "Fire Dept. Station, Photo Gallery, Express Office (entrance row)": (7637330, 689380, "left"),
        "Auditorium": (7637520, 689830, "left"), "Oriental Building": (7636150, 689330, "right"),
    }
    FS = 6.6
    ft_per_pt = (x1 - x0) / (S.WIDTH_PX / S.DPI * 72)              # map feet per typographic point
    halo = [pe.withStroke(linewidth=2, foreground="#7a3e0e")]
    for n, text in SHORT.items():
        if n not in shapes:
            continue
        poly = shapes[n]
        rect = poly.minimum_rotated_rectangle
        xs, ys = np.array(rect.exterior.coords)[:4].T
        e = [(np.hypot(xs[(i + 1) % 4] - xs[i], ys[(i + 1) % 4] - ys[i]), i) for i in range(4)]
        long_len, i = max(e)
        short_len = min(e)[0]
        ang = np.degrees(np.arctan2(ys[(i + 1) % 4] - ys[i], xs[(i + 1) % 4] - xs[i]))
        ang = ((ang + 90) % 180) - 90
        c = poly.centroid if poly.contains(poly.centroid) else poly.representative_point()
        fit = None
        for t in (text, text.replace(" & ", " &\n")):          # one line, or split at the ampersand
            lines = t.split("\n")
            for fs in (6.6, 6.2, 5.8, 5.4, 5.0):
                if (max(map(len, lines)) * fs * 0.6 * ft_per_pt < long_len * 0.94
                        and len(lines) * fs * 1.25 * ft_per_pt < short_len * 1.05):
                    fit = (t, fs); break
            if fit:
                break
        if fit:
            ax.text(c.x, c.y, fit[0], rotation=ang, rotation_mode="anchor", ha="center", va="center", fontsize=fit[1],
                    color="white", fontweight="bold", path_effects=halo, linespacing=1.0)
        else:
            lx, ly, ha = LEADER.get(n, (c.x + 150, c.y + 150, "left"))
            ax.annotate(text, xy=(c.x, c.y), xytext=(lx, ly), ha=ha, va="center", fontsize=FS, color="#8a4512",
                        bbox=dict(boxstyle="round,pad=0.18", fc=S.PAPER, ec="none", alpha=0.88),
                        arrowprops=dict(arrowstyle="-", color="#8a4512", lw=0.7, shrinkA=0, shrinkB=2))
    if "Emergency Hospital" in shapes:
        h = shapes["Emergency Hospital"]
        ax.text(h.bounds[0] - 30, h.centroid.y, "Emergency Hospital\n(Pence office)", ha="right", va="center",
                fontsize=7, fontweight="bold", color=S.INK,
                bbox=dict(boxstyle="round,pad=0.2", fc=S.PAPER, ec="none", alpha=0.88))
    lab(7635300, 691700, "Guild's Lake (1902)", style="italic", color="#2f5f78", size=8)
    ax.legend(handles=[Patch(color=DEC_COL, label="bought Dec 1905 (state buildings and others)"),
                       Patch(color=MAY_COL, label="bought May 1906 (Government Building and annexes)"),
                       Patch(color=S.BUILT, alpha=0.45, label="the rest of the fair")],
              loc="upper right", bbox_to_anchor=(0.995, 0.855), fontsize=7, frameon=True, facecolor=S.PAPER, edgecolor="none", framealpha=0.9)
    S.north_arrow(ax, 0.95, 0.94)
    S.scale_bar(ax, x0 + 120, y0 + 110, 1000)
    S.save(fig, OUT / "ch4-buildings-map.jpg")


def perspective():
    import pymupdf
    doc = pymupdf.open(P / "sources" / "newspapers" / "oregonian_1906-05-04_p11_perspective-map-pence-electric-line-linnton.pdf")
    pg = doc[0]
    clip = pymupdf.Rect(44, 82, 862, 562)                       # the drawing and its title box, page units
    zoom = S.WIDTH_PX / clip.width
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3][..., ::-1].copy()
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / "ch4-perspective-1906.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("wrote stories/pence/figures/ch4-perspective-1906.jpg")


if __name__ == "__main__":
    buildings_map()
    perspective()
