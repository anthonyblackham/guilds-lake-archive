r"""Figures for the Pence story, chapter 5 (washing down the Scotch Nubbin, winter 1906-07).

    python scripts/figures/pence_ch5.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch5-*.jpg.
  ch5-flume-picture     the 11 Mar 1907 Oregonian flume picture, as printed
  ch5-picture-vs-model  the same picture with the cut face and flumes traced (user's linework), over the model before the cuts
         (ground cut away since in blue), from the picture's solved camera
  ch5-trestle-collapse  the trestle collapse in Balch's Gulch, Oregonian 16 Feb 1907
  ch5-route-map         map: the cut face, the flumes in the picture and the documented spoil route to the Government Building
"""
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from pyogrio.raw import read
from shapely import from_wkb
from shapely.affinity import translate

import figstyle as S

P = S.PROJECT
OUT = S.HERE / "stories" / "pence" / "figures"


def bgr(hexcol):
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (4, 2, 0))


def fit(img, width=S.WIDTH_PX):
    h, w = img.shape[:2]
    return cv2.resize(img, (width, round(h * width / w)), interpolation=cv2.INTER_AREA)


def write(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / name), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("wrote", (OUT / name).relative_to(S.HERE))


def scans():
    news = P / "sources" / "newspapers"
    bird = cv2.imread(str(news / "oregonian_1906-03-01_p10_eating-away-the-hill-birdseye_drawing.jpg"))
    write(fit(bird[95:1078, 15:2400]), "ch5-birdseye.jpg")     # the drawing's dotted frame, without the column text
    write(fit(cv2.imread(str(news / "oregonian_1907-03-11_p12_pence-flumes-illustration.jpg"))), "ch5-flume-picture.jpg")
    write(fit(cv2.imread(str(news / "oregonian_1907-02-16_p10_balchs-gulch-trestle-collapse_photo.jpg")), 1200),
          "ch5-trestle-collapse.jpg")


def picture_vs_model():
    sys.path.insert(0, str(P / "scripts" / "cam1907"))
    import render_compare as R
    today, gx, gy, cell = R.grid()
    hills = R.sample("hills_1906_dem", gx, gy) - R.OFFSET + R.CITY
    grounds = R.sample("combined_dem", gx, gy) + R.CITY
    before = np.where(np.isfinite(hills), hills, today)
    before = np.where(np.isfinite(grounds), grounds, before)
    water = np.isfinite(grounds) & (grounds - R.CITY < R.WATER)
    cut = np.nan_to_num(before - today, nan=0.0)
    model = R.render(before, cell, gx, gy, water, cut)
    pic = cv2.resize(cv2.imread(str(P / "sources" / "newspapers" / "oregonian_1907-03-11_p12_pence-flumes-illustration.jpg")),
                     (R.W, R.H), interpolation=cv2.INTER_AREA)
    # the user's corrected linework (ground coordinates, cast on today's lidar) projected back through the camera
    m, _, g, d = read(P / "qgis" / "terrain" / "scotch_nubbin_1907_photo.gpkg", layer="oregonian_1907_cut_and_flumes")
    names = dict(zip(m["fields"], d))["name"]
    zt = lambda x, y: float(today[int(round((gy[0, 0] - y) / cell)), int(round((x - gx[0, 0]) / cell))])
    proj = []
    for q, n in zip(from_wkb(g), names):
        pts = np.array([(x, y, zt(x, y)) for x, y in q.segmentize(10).coords])
        uv, zc = R.proj(pts)
        proj.append((n, uv[zc > 0].astype(np.int32)))

    def lines(img):
        out = img.copy()
        for n, uv in proj:
            cv2.polylines(out, [uv], n.startswith("cut"), bgr(S.CUT if n.startswith("cut") else S.FLUME), 3, cv2.LINE_AA)
        return out

    aerial, zbuf = render_aerial(R, today, gx, gy, cell)
    aerial = street_labels(R, aerial, zbuf, today, gx, gy, cell)
    gap = np.full((14, R.W, 3), bgr(S.PAPER), np.uint8)
    write(fit(np.vstack([lines(pic), gap, lines(model), gap, lines(aerial)])), "ch5-picture-vs-model.jpg")


def render_aerial(R, z, gx, gy, cell):
    """Today's ground from the picture's camera, coloured from the 2025 aerial photo (Portland Maps), lightly shaded.
    Same z-sorted point splat as render_compare.render; returns the image and its depth buffer."""
    T = P / "qgis" / "terrain"
    ph = cv2.imread(str(T / "basemap_aerial_2025.jpg")).astype(np.float32)
    w = [float(v) for v in (T / "basemap_aerial_2025.jgw").read_text().split()]
    colr = cv2.remap(ph, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32),
                     cv2.INTER_LINEAR, borderValue=(225, 222, 214))
    dzdy, dzdx = np.gradient(z, -cell, cell)
    sl, asp = np.arctan(np.hypot(dzdx, dzdy)), np.arctan2(dzdy, -dzdx)
    hs = np.clip(np.sin(.75) * np.cos(sl) + np.cos(.75) * np.sin(sl) * np.cos(np.radians(300) - (np.pi / 2 - asp)), 0, 1)
    uv, zc = R.proj(np.c_[gx.ravel(), gy.ravel(), z.ravel()])
    ok = (zc > 40) & (uv[:, 0] > -20) & (uv[:, 0] < R.W + 20) & (uv[:, 1] > -20) & (uv[:, 1] < R.H + 20)
    uv, zc, h, col = uv[ok], zc[ok], hs.ravel()[ok], colr.reshape(-1, 3)[ok]
    o = np.argsort(-zc)
    uv, zc, h, col = uv[o], zc[o], h[o], col[o]
    col = col * (0.72 + 0.4 * h[:, None])
    fog = np.clip(zc / 14000, 0, 0.6)[:, None]
    col = col * (1 - fog) + np.array([226, 222, 214]) * fog
    img = np.full((R.H, R.W, 3), (232, 228, 220), np.float32)
    zbuf = np.full((R.H, R.W), np.inf, np.float32)
    s = np.clip((R.F / 2 * cell * 1.3 / zc).astype(int) + 1, 1, 8)
    for ds in range(1, 9):
        k = s >= ds
        for dx in range(ds):
            for dy in ([ds - 1] if dx < ds - 1 else range(ds)):
                u = uv[k, 0].astype(int) + dx; v = uv[k, 1].astype(int) + dy
                m = (u >= 0) & (u < R.W) & (v >= 0) & (v < R.H)
                u, v, zz, cc = u[m], v[m], zc[k][m], col[k][m]
                near = zz < zbuf[v, u]
                img[v[near], u[near]] = cc[near]; zbuf[v[near], u[near]] = zz[near]
    return np.clip(img, 0, 255).astype(np.uint8), zbuf


STREETS = {"Northwest 32nd Avenue": "NW 32nd Ave", "Northwest 33rd Avenue": "NW 33rd Ave"}
BRIDGE = ((7635408, 689053), (7635000, 689170))   # Thurman St bridge ends (data/model_structures.csv)


def street_labels(R, img, zbuf, z, gx, gy, cell):
    """Map-style labels laid along features in the picture: white text with a dark outline, rotated to the feature's
    direction on screen. Only what helps place the view: NW 32nd and NW 33rd Aves (cached OpenStreetMap ways), labelled
    on the same block so they sit side by side and parallel, and the Thurman St bridge."""
    from PIL import Image, ImageDraw, ImageFont
    from pyproj import Transformer
    import matplotlib
    tr = Transformer.from_crs(4326, 2913, always_xy=True)
    streets = {}
    for f in ("osm_roads_willamette_heights.json", "osm_roads_westover.json", "osm_roads_m1698.json"):
        p = P / "qgis" / "terrain" / f
        if p.exists():
            for e in json.loads(p.read_text(encoding="utf-8")).get("elements", []):
                n = e.get("tags", {}).get("name")
                if n in STREETS and "geometry" in e:
                    xs, ys = tr.transform([g["lon"] for g in e["geometry"]], [g["lat"] for g in e["geometry"]])
                    streets.setdefault(STREETS[n], []).append(np.c_[xs, ys])
    zat = lambda x, y: float(z[int(np.clip(round((gy[0, 0] - y) / cell), 0, z.shape[0] - 1)),
                               int(np.clip(round((x - gx[0, 0]) / cell), 0, z.shape[1] - 1))])

    def screen(x, y, dz=2.0):
        uv, zc = R.proj(np.array([[x, y, zat(x, y) + dz]]))
        return uv[0], zc[0]

    def visible(u, v, d):
        return d > 60 and 0 <= u < R.W and 0 <= v < R.H and d < zbuf[int(v), int(u)] + 25

    def x_at(lines, n):            # the street's easting at northing n (N-S avenues)
        for q in lines:
            if q[:, 1].min() <= n <= q[:, 1].max():
                o = np.argsort(q[:, 1])
                return float(np.interp(n, q[o, 1], q[o, 0]))
        return None

    labels = []
    # the two avenues on one block: the northing where both are visible
    for n in range(688850, 689450, 25):
        cand = []
        for text, lines in streets.items():
            x = x_at(lines, n)
            if x is None:
                break
            (u, v), d = screen(x, n)
            (ua, va), _ = screen(x_at(lines, n - 60) or x, n - 60)
            (ub, vb), _ = screen(x_at(lines, n + 60) or x, n + 60)
            if not visible(u, v, d):
                break
            cand.append((text, (u, v), np.degrees(np.arctan2(vb - va, ub - ua))))
        if len(cand) == len(streets):
            break
    else:
        cand = []
    if cand:
        # one angle for both, NW 33rd's (near vertical): parallel on the page (user's choice, 2026-11-13). In
        # perspective NW 32nd itself slants up to the left here; its label is kept upright anyway.
        ref = next(c[2] for c in cand if "33rd" in c[0])
        labels += [(t, uv, ref) for t, uv, _ in cand]
    # Thurman St bridge, along the deck
    (u0, v0), _ = screen(*BRIDGE[0], 6); (u1, v1), _ = screen(*BRIDGE[1], 6)
    labels.append(("Thurman St bridge", ((u0 + u1) / 2, (v0 + v1) / 2), np.degrees(np.arctan2(v1 - v0, u1 - u0))))

    font = ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"), 24)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).convert("RGBA")
    for text, (u, v), ang in labels:
        ang = ((ang + 90) % 180) - 90
        tw, th = ImageDraw.Draw(pil).textbbox((0, 0), text, font=font, stroke_width=3)[2:]
        lay = Image.new("RGBA", (tw + 8, th + 8), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((4, 4), text, font=font, fill=(255, 255, 255, 255), stroke_width=3,
                                 stroke_fill=(30, 26, 20, 255))
        lay = lay.rotate(-ang, expand=True, resample=Image.BICUBIC)
        pil.alpha_composite(lay, (int(u - lay.width / 2), int(v - lay.height / 2)))
    return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)


def route_map():
    T = P / "qgis" / "terrain"
    x0, x1, y0, y1 = 7633050, 7637150, 687950, 693350
    dem = cv2.imread(str(T / "balch_hills_dem.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (T / "balch_hills_dem.tfw").read_text().split()]
    c0, c1 = int((x0 - w[4]) / w[0]), int((x1 - w[4]) / w[0])
    r0, r1 = int((w[5] - y1) / -w[3]), int((w[5] - y0) / -w[3])
    z = dem[r0:r1, c0:c1]
    z = np.where(z > -9000, z, np.nan)
    z = np.where(np.isfinite(z), z, np.nanmin(z))
    gy_, gx_ = np.gradient(z, w[0])
    az, alt = np.radians(315), np.radians(40)
    slope = np.arctan(np.hypot(gx_, gy_) * 1.5)
    aspect = np.arctan2(-gx_, gy_)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    shade = np.clip(shade, 0, 1)

    fig = S.figure((y1 - y0) / (x1 - x0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(shade, cmap="gray", extent=(x0, x1, y0, y1), vmin=-0.6, vmax=1.15, alpha=0.9, interpolation="bilinear")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")

    # the 1902 lake (Huber & Maxwell outline, with the combined surface's shift)
    m, _, g, _ = read(P / "qgis" / "expo-model.gpkg", layer="huber_1902_lakebed_refit")
    for q in from_wkb(g):
        q = translate(q, 20.0, -10.0)
        for poly in getattr(q, "geoms", [q]):
            xs, ys = poly.exterior.xy
            ax.fill(xs, ys, color=S.WATER, alpha=0.45, lw=0)
    # exposition buildings
    m, _, g, d = read(P / "qgis" / "expo-model.gpkg", layer="buildings")
    for q in from_wkb(g):
        for poly in getattr(q, "geoms", [q]):
            xs, ys = poly.exterior.xy
            ax.fill(xs, ys, color=S.BUILT, alpha=0.55, lw=0)
    # the picture's cut face and flumes, then the documented route
    gp = T / "scotch_nubbin_1907_photo.gpkg"
    m, _, g, d = read(gp, layer="oregonian_1907_cut_and_flumes")
    names = dict(zip(m["fields"], d))["name"]
    for q, n in zip(from_wkb(g), names):
        if n == "flume_to_bridge_and_trail":
            continue                      # below the junction the picture's line is probably the artist's
        xs, ys = q.xy
        if n.startswith("cut"):
            ax.fill(xs, ys, color=S.CUT, alpha=0.35, lw=0)
            ax.plot(xs, ys, color=S.CUT, lw=1.6)
        else:
            ax.plot(xs, ys, color=S.FLUME, lw=2.0, solid_capstyle="round")
    m, _, g, _ = read(gp, layer="pence_spoil_route_1907_documented")
    for q in from_wkb(g):
        xs, ys = q.xy
        ax.plot(xs, ys, color=S.FLUME, lw=2.4, solid_capstyle="round")

    # Thurman St bridge (1905 steel deck truss) and the trestle collapse
    ax.plot([7635408, 7635000], [689053, 689170], color=S.INK, lw=2.2)
    ax.plot([7635100], [688740], marker="x", color=S.INK, ms=8, mew=2)

    def lab(x, y, text, ha="left", size=8.5, color=S.INK, style="normal", weight="normal"):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontstyle=style, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.18", fc=S.PAPER, ec="none", alpha=0.75))

    lab(7633180, 688760,"Scotch Nubbin\ncut face, Mar 1907", weight="bold", color=S.CUT)
    lab(7635150, 688600, "trestle collapse\n15 Feb 1907", size=7.5)
    lab(7635440, 689010, "Thurman St bridge", size=7.5)
    lab(7634700, 688900, "Balch Gulch", style="italic", color=S.MUTED)
    lab(7635720, 689520, "Emergency Hospital\n(Pence office)", size=7.5)
    lab(7635560, 690256, "Klondike building", size=7.5)
    lab(7635520, 691550, "the Trail and\nBridge of Nations", size=7.5)
    lab(7635180, 693130, "Government Building\n(fill behind it)", ha="right", size=7.5)
    lab(7634250, 691700, "Guild's Lake (1902)", style="italic", color="#3d6a80")
    lab(7636250, 689250, "1905 fairgrounds", style="italic", color=S.MUTED)
    S.north_arrow(ax, 0.93, 0.95)
    S.scale_bar(ax, x1 - 1350, y0 + 230, 1000)
    ax.text(x1 - 60, y0 + 90, "Today's ground (2019 lidar), 1902 lake and 1905 buildings", ha="right", va="bottom",
            fontsize=6.5, color=S.MUTED)
    S.save(fig, OUT / "ch5-route-map.jpg")


if __name__ == "__main__":
    scans()
    route_map()
    picture_vs_model()
