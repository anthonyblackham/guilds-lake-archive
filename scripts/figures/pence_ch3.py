r"""Figures for the Pence story, chapter 3 (the flume war, Dec 1905 - Mar 1906).

    python scripts/figures/pence_ch3.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch3-*.jpg. All scans as printed.
  ch3-broken-flume      Oregonian 27 Feb 1906 p. 10, "Policemen Riley and Burke on guard at the broken flume"
  ch3-giants            Oregonian 27 Feb 1906 p. 10, "Hydraulic giants attacking a hill on Portland Heights"
  ch3-birdseye          Oregonian 1 Mar 1906 p. 10, the bird's-eye view of the works (whole drawing)
  ch3-park-flume-map    the park flume, headgate and first attack (user's trace) on the lidar, with the 1897 park line
"""
import cv2

import figstyle as S

P = S.PROJECT
OUT = S.HERE / "stories" / "pence" / "figures"
NEWS = P / "sources" / "newspapers"


def fit(img, width):
    h, w = img.shape[:2]
    return cv2.resize(img, (width, round(h * width / w)), interpolation=cv2.INTER_AREA if w > width else cv2.INTER_CUBIC)


def write(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / name), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print("wrote", (OUT / name).relative_to(S.HERE))


def main():
    write(fit(cv2.imread(str(NEWS / "oregonian_1906-02-27_p10_truce-may-end-fight-of-flume_photo-broken-flume.jpg")), 1200),
          "ch3-broken-flume.jpg")
    write(fit(cv2.imread(str(NEWS / "oregonian_1906-02-27_p10_truce-may-end-fight-of-flume_photo-giants.jpg")), 1400),
          "ch3-giants.jpg")
    bird = cv2.imread(str(NEWS / "oregonian_1906-03-01_p10_eating-away-the-hill-birdseye_drawing.jpg"))
    write(fit(bird[95:1078, 15:2400], S.WIDTH_PX), "ch3-birdseye.jpg")     # the whole drawing, inside its dotted frame


def park_flume_map():
    """The park flume, the headgate box at its end and the first workings (user's trace on the Parks forestry
    extension sheet, qgis/terrain/pence_flumes_1906_trace.gpkg), over today's ground as grey hillshade ('past' style),
    with the 1897 Macleay Park line, Balch Creek (user's stream trace), Cornell Road and the 1896 knoll."""
    import json
    import matplotlib.patheffects as pe
    import numpy as np
    from pyogrio.raw import read
    from pyproj import Transformer
    from shapely import from_wkb
    from shapely.geometry import shape

    T = P / "qgis" / "terrain"
    X0, X1, Y0, Y1 = 7630250, 7634800, 686050, 688900
    cell = 4.0

    def grid(name):
        a = cv2.imread(str(T / f"{name}.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
        w = [float(v) for v in (T / f"{name}.tfw").read_text().split()]
        gx, gy = np.meshgrid(np.arange(X0, X1, cell), np.arange(Y1, Y0, -cell))
        z = cv2.remap(a, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32),
                      cv2.INTER_LINEAR, borderValue=-9999)
        return np.where(z > -9000, z, np.nan)

    today = grid("balch_hills_dem") - 2.10
    gy_, gx_ = np.gradient(np.nan_to_num(today, nan=np.nanmin(today)), cell)
    sl = np.arctan(np.hypot(gx_, gy_) * 1.4)
    shade = np.clip(np.sin(0.7) * np.cos(sl) + np.cos(0.7) * np.sin(sl) * np.cos(np.radians(315) - np.arctan2(-gx_, gy_)), 0, 1)
    # two panels in the same frame: the Parks sheet the flume was traced from (as georeferenced, TPS warp), and today
    asp = (Y1 - Y0) / (X1 - X0)
    fig = S.figure(asp * 2 + 0.02)
    hh = asp / (asp * 2 + 0.02)
    top = fig.add_axes([0, 1 - hh, 1, hh])
    g_ = P / "qgis" / "georeference" / "forestry_extension_contours_russell_blythe_mosaic_warped"
    sheet = cv2.imread(str(g_) + ".jpg")
    sw = [float(v) for v in open(str(g_) + ".jgw").read().split()]
    sgx, sgy = np.meshgrid(np.arange(X0, X1, cell), np.arange(Y1, Y0, -cell))
    sheet = cv2.remap(sheet, ((sgx - sw[4]) / sw[0]).astype(np.float32), ((sgy - sw[5]) / sw[3]).astype(np.float32),
                      cv2.INTER_LINEAR, borderValue=(228, 222, 210))[..., ::-1]
    top.imshow(sheet, extent=(X0, X1, Y0, Y1), interpolation="bilinear")
    top.set_xlim(X0, X1); top.set_ylim(Y0, Y1); top.set_aspect("equal"); top.axis("off")
    top.text(X1 - 60, Y1 - 60, "c. 1909-10: the Parks Department sheet, flumes in pencil", ha="right", va="top", fontsize=9.5,
             fontweight="bold", color=S.INK, bbox=dict(boxstyle="round,pad=0.3", fc=S.PAPER, ec="none", alpha=0.9))
    ax = fig.add_axes([0, 0, 1, hh])
    ax.imshow(shade, cmap="gray", extent=(X0, X1, Y0, Y1), vmin=-0.55, vmax=1.15, interpolation="bilinear")
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal"); ax.axis("off")
    ax.text(X0 + 1500, Y1 - 60, "Today: the flume traced from it", ha="left", va="top", fontsize=9.5,
            fontweight="bold", color=S.INK, bbox=dict(boxstyle="round,pad=0.3", fc=S.PAPER, ec="none", alpha=0.9))
    halo = [pe.withStroke(linewidth=2.5, foreground="white")]

    park = shape(json.loads((T / "macleay_park_1897_2913.geojson").read_text())["features"][0]["geometry"])
    for poly in getattr(park, "geoms", [park]):
        x, y = poly.exterior.xy
        ax.fill(x, y, color="#6f8f5a", alpha=0.13, lw=0)
        ax.plot(x, y, color="#4f6f3a", lw=1.4, ls=(0, (6, 3)))
    m, _, g, d = read(P / "qgis" / "terrain" / "balch_gulch_prefill_trace.gpkg", layer="gulch_creek_centerline")
    creek = max(from_wkb(g), key=lambda q: q.length)
    x, y = creek.xy
    ax.plot(x, y, color=S.WATER, lw=1.6)
    tr = Transformer.from_crs(4326, 2913, always_xy=True)
    done = set()
    for f in ("osm_roads_westover.json", "osm_roads_m1698.json"):
        for e in json.loads((T / f).read_text(encoding="utf-8")).get("elements", []):
            if e.get("tags", {}).get("name") == "Northwest Cornell Road" and "geometry" in e and e["id"] not in done:
                done.add(e["id"])
                x, y = tr.transform([q["lon"] for q in e["geometry"]], [q["lat"] for q in e["geometry"]])
                ax.plot(x, y, color="#9a8f7e", lw=1.3)
    k = grid("nubbin_1896_dem")
    kk = np.where(np.isfinite(k) & (k > today + 1), k, np.nan)
    ax.contour(np.arange(X0, X1, cell), np.arange(Y1, Y0, -cell), kk, levels=[350, 375, 400, 425], colors=S.INK,
               linewidths=0.8, linestyles="dashed")
    gp = T / "pence_flumes_1906_trace.gpkg"
    m, _, g, d = read(gp, layer="flume_lines")
    notes = dict(zip(m["fields"], d))["note"]
    for q, n in zip(from_wkb(g), notes):
        x, y = q.xy
        ax.plot(x, y, color="#8a5a2b" if n == "Spoil" else S.FLUME, lw=2.4, solid_capstyle="round", path_effects=halo)
    m, _, g, d = read(gp, layer="first_attack_area")
    names = dict(zip(m["fields"], d))["name"]
    for q, n in zip(from_wkb(g), names):
        x, y = q.exterior.xy
        if n == "Penstock":
            ax.fill(x, y, color=S.INK, lw=0); box = q.centroid
        else:
            ax.fill(x, y, color=S.CUT, alpha=0.35, lw=0); ax.plot(x, y, color=S.CUT, lw=1.4); attack = q.centroid
    first = from_wkb(read(gp, layer="flume_lines")[2][0])
    intake = min((first.coords[0], first.coords[-1]), key=lambda c: c[0])
    ax.plot(*intake, "o", color=S.WATER, mec=S.INK, ms=7)

    def lab(x, y, text, ha="left", color=S.INK, style="normal", weight="normal", size=8.5):
        ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontstyle=style, fontweight=weight,
                bbox=dict(boxstyle="round,pad=0.2", fc=S.PAPER, ec="none", alpha=0.85))

    lab(intake[0] + 60, intake[1] - 120, "intake on Balch Creek\n(about 245 ft outside the park)", size=7.5)
    lab(7631350, 686420, "Macleay Park (1897 boundary)", color="#4f6f3a", style="italic")
    lab(7631900, 687300, "the park flume", color="#a85e14", weight="bold")
    lab(box.x - 60, box.y + 110, "headgate box (\"AA\")", ha="right", size=7.5)
    lab(attack.x - 80, attack.y + 210, "first workings, in the\nvalley behind the knoll", ha="right", color=S.CUT, size=7.5)
    lab(7634260, 688790, "Scotch Nubbin\n(1896, dashed)", size=7.5)
    lab(7634250, 688170, "spoil down\nthe gulch", color="#8a5a2b", size=7.5)
    # "Balch Creek" laid along the creek itself, on a straight-ish stretch inside the park
    from shapely import Point as _Pt
    t = creek.project(_Pt(7632750, 686800))
    a_, b_ = creek.interpolate(t - 120), creek.interpolate(t + 120)
    mid = creek.interpolate(t)
    ang = np.degrees(np.arctan2(b_.y - a_.y, b_.x - a_.x)); ang = ((ang + 90) % 180) - 90
    nx, ny = -np.sin(np.radians(ang)), np.cos(np.radians(ang))        # nudge the text just off the line
    ax.text(mid.x + 28 * nx, mid.y + 28 * ny, "Balch Creek", rotation=ang, rotation_mode="anchor", ha="center",
            va="center", fontsize=8, color="#2f5f78", fontstyle="italic",
            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
    lab(7633520, 687300, "Cornell Road", color="#6d6354", style="italic", size=7.5)
    S.north_arrow(ax, 0.30, 0.95)
    S.scale_bar(ax, X0 + 150, Y1 - 260, 1000)
    ax.text(X1 - 40, Y0 + 30, "Today's ground: 2019 lidar", ha="right", va="bottom", fontsize=6.5, color=S.MUTED)
    S.save(fig, OUT / "ch3-park-flume-map.jpg")


if __name__ == "__main__":
    main()
    park_flume_map()
