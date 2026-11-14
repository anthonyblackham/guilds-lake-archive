r"""Figure for the Pence story, chapter 7 (what's left): the Scotch Nubbin today.

    python scripts/figures/pence_ch7.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch7-today-map.jpg:
today's ground (2019 lidar hillshade), the 1896 knoll as dashed contours (nubbin_1896_dem, re-anchored on the knob),
the cut face in the 11 Mar 1907 picture, the Thurman St bridge and a few modern street names (cached OpenStreetMap).
"""
import json

import cv2
import numpy as np
from pyogrio.raw import read
from pyproj import Transformer
from shapely import from_wkb

import figstyle as S

P = S.PROJECT
T = P / "qgis" / "terrain"
OUT = S.HERE / "stories" / "pence" / "figures"
X0, X1, Y0, Y1 = 7633400, 7635500, 688000, 689450
STREETS = {"Northwest 32nd Avenue": "NW 32nd Ave", "Northwest 33rd Avenue": "NW 33rd Ave",
           "Northwest Thurman Street": "NW Thurman St", "Northwest Aspen Avenue": "NW Aspen Ave"}


def grid(name, cell):
    a = cv2.imread(str(T / f"{name}.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (T / f"{name}.tfw").read_text().split()]
    gx, gy = np.meshgrid(np.arange(X0, X1, cell), np.arange(Y1, Y0, -cell))
    z = cv2.remap(a, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32),
                  cv2.INTER_LINEAR, borderValue=-9999)
    return np.where(z > -9000, z, np.nan)


def main():
    cell = 3.0
    today = grid("balch_hills_dem", cell) - 2.10
    knoll = grid("nubbin_1896_dem", cell)
    gy_, gx_ = np.gradient(np.nan_to_num(today, nan=np.nanmin(today)), cell)
    slope = np.arctan(np.hypot(gx_, gy_) * 1.4)
    aspect = np.arctan2(-gx_, gy_)
    az, alt = np.radians(315), np.radians(40)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)

    # hybrid base: the 2025 aerial photo (Portland Maps) shaded by the lidar hillshade, so the relief reads under trees
    photo = cv2.imread(str(T / "basemap_aerial_2025.jpg"))
    w = [float(v) for v in (T / "basemap_aerial_2025.jgw").read_text().split()]
    gx, gy = np.meshgrid(np.arange(X0, X1, cell), np.arange(Y1, Y0, -cell))
    photo = cv2.remap(photo, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32),
                      cv2.INTER_LINEAR)[..., ::-1].astype(np.float32) / 255
    photo = photo * 0.85 + 0.15 * photo.mean(-1, keepdims=True)          # a little desaturated, so the overlays lead
    MODE, OPACITY = globals().get("MODE", "blend"), globals().get("OPACITY", 0.5)
    LIDAR = 0.4    # share of plain grey hillshade mixed in (user: more weight to the lidar)
    relief = (0.25 + 0.95 * shade)[..., None]
    base = np.clip((1 - LIDAR) * photo * relief + LIDAR * np.clip(0.15 + 0.85 * shade, 0, 1)[..., None], 0, 1)
    if MODE == "overlay":   # the plain hillshade as on the grey map, the aerial on top at OPACITY
        grey = np.clip((shade + 0.5) / 1.65, 0, 1)[..., None]       # same mapping as imshow(vmin=-0.5, vmax=1.15)
        base = (1 - OPACITY) * grey + OPACITY * photo

    fig = S.figure((Y1 - Y0) / (X1 - X0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(base, extent=(X0, X1, Y0, Y1), interpolation="bilinear")
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal"); ax.axis("off")
    import matplotlib.patheffects as pe
    halo = [pe.withStroke(linewidth=2.6, foreground=S.INK)]
    # the 1896 knoll: contours where it stood above today's ground (white with a dark edge, to read on the photo)
    k = np.where(np.isfinite(knoll) & (knoll > today + 1), knoll, np.nan)
    xs = np.arange(X0, X1, cell); ys = np.arange(Y1, Y0, -cell)
    cs = ax.contour(xs, ys, k, levels=[350, 375, 400, 425], colors="white", linewidths=1.2, linestyles="dashed")
    for c in getattr(cs, "collections", [cs]):
        c.set_path_effects(halo)
    for t in ax.clabel(cs, fmt="%d", fontsize=7, inline=True, colors="white"):
        t.set_path_effects(halo)
    # the cut face in the 1907 picture
    m, _, g, d = read(T / "scotch_nubbin_1907_photo.gpkg", layer="oregonian_1907_cut_and_flumes")
    for q, n in zip(from_wkb(g), dict(zip(m["fields"], d))["name"]):
        if n.startswith("cut"):
            x, y = q.xy
            ax.fill(x, y, color=S.CUT, alpha=0.35, lw=0); ax.plot(x, y, color="#e0574c", lw=1.8, path_effects=halo)
    # Thurman St bridge
    ax.plot([7635408, 7635000], [689053, 689170], color="white", lw=2.4, solid_capstyle="butt", path_effects=halo)
    # modern street names along the streets (OpenStreetMap)
    tr = Transformer.from_crs(4326, 2913, always_xy=True)
    seen = set()
    for f in ("osm_roads_willamette_heights.json", "osm_roads_westover.json"):
        p = T / f
        if not p.exists():
            continue
        for e in json.loads(p.read_text(encoding="utf-8")).get("elements", []):
            n = e.get("tags", {}).get("name")
            if n not in STREETS or n in seen or "geometry" not in e:
                continue
            x, y = tr.transform([g_["lon"] for g_ in e["geometry"]], [g_["lat"] for g_ in e["geometry"]])
            x, y = np.array(x), np.array(y)
            inside = (x > X0 + 80) & (x < X1 - 80) & (y > Y0 + 80) & (y < Y1 - 80)
            if inside.sum() < 2:
                continue
            seen.add(n)
            i = np.flatnonzero(inside)[inside.sum() // 2]
            j = min(i + 1, len(x) - 1); h = max(i - 1, 0)
            ang = np.degrees(np.arctan2(y[j] - y[h], x[j] - x[h]))
            ang = ((ang + 90) % 180) - 90
            ax.text((x[i] + x[j]) / 2, (y[i] + y[j]) / 2, STREETS[n], rotation=ang, rotation_mode="anchor",
                    ha="center", va="center", fontsize=7.5, color="white", fontweight="bold",
                    path_effects=[__import__("matplotlib.patheffects", fromlist=["x"]).withStroke(linewidth=2.5, foreground=S.INK)])

    def lab(x, y, text, ha="left", color=S.INK, style="normal", weight="normal", size=8.5):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontstyle=style, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.2", fc=S.PAPER, ec="none", alpha=0.8))

    ax.plot([7634108], [688467], marker="^", color="white", ms=8, mec=S.INK, mew=1.2)
    lab(7634190, 688470, "today's knob, 374 ft:\nthe knoll's cut-down summit", weight="bold")
    lab(7633520, 688560, "the small valley\nbehind the knoll", style="italic", color=S.MUTED)
    lab(7633530, 688250, "cut face, Mar 1907", color=S.CUT)
    lab(7634900, 688520, "Balch Gulch", style="italic", color=S.MUTED)
    lab(7635210, 689020, "Thurman St bridge", ha="center", size=7.5)
    lab(7633480, 689380, "dashed: the knoll in 1896 (25 ft contours)", size=7, color=S.MUTED)
    from matplotlib.patches import FancyBboxPatch
    for (bx, by, bw, bh) in ((X1 - 150, Y1 - 215, 120, 195), (X1 - 1010, Y0 + 15, 990, 175)):   # pale panels on the photo
        ax.add_patch(FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0,rounding_size=12", fc=S.PAPER, ec="none",
                                    alpha=0.85, zorder=4))
    S.north_arrow(ax, 0.95, 0.93)
    S.scale_bar(ax, X1 - 700, Y0 + 90, 500)
    ax.text(X1 - 40, Y0 + 30, "Base: 2025 aerial photographs (City of Portland), shaded with the 2019 lidar",
            ha="right", va="bottom", fontsize=6.5, color=S.MUTED, zorder=5)
    for a in ax.lines[-4:] + ax.texts[-3:]:
        a.set_zorder(5)
    S.save(fig, globals().get("OUTFILE", OUT / "ch7-today-map.jpg"))


if __name__ == "__main__":
    main()
