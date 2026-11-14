r"""Showcase images for the historic topography page.

    python scripts/figures/topo_cards.py [survey_id ...]     the survey cards (all, or the ones named)
    python scripts/figures/topo_cards.py overview            the overview of every survey on today's ground

For each survey in gis/historic_topography.gpkg (layer `surveys`), three panels in the sheet's own frame and
orientation, cropped to the traced lines:
  topography/cards/<id>-original.jpg   the sheet as printed
  topography/cards/<id>-contours.jpg   the traced contours / spot heights coloured by height (city datum), over the
                                       sheet faded into a dark ground
  topography/cards/<id>-model.jpg      the reconstructed ground, shaded relief in the same colours
And topography/overview.jpg: every survey's lines on one height scale over today's ground (the 2025 aerial in grey,
multiplied onto the lidar hillshade), each titled on its main body.
Reads the research project (lewis-clark-1905) read-only. Scans are placed with the project's own georeferences (world
files or the QGIS .points GCPs, fitted affine here) plus the same shifts the exported lines carry.
"""
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
from matplotlib.colors import LightSource  # noqa: E402
from PIL import Image  # noqa: E402
from pyogrio import list_layers  # noqa: E402
from pyogrio.raw import read  # noqa: E402
from shapely import from_wkb  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

P = S.PROJECT
G = P / "qgis" / "georeference"
T = P / "qgis" / "terrain"
GPKG = S.HERE / "gis" / "historic_topography.gpkg"
OUT = S.HERE / "topography" / "cards"
PW = 1200              # panel width; height follows the sheet
DARK = np.array([0x12, 0x15, 0x1c]) / 255   # ground of the contour and relief panels
Image.MAX_IMAGE_PIXELS = None
OFFSET = 3.4           # M/1698, M/1697 sheets read this high (the hills surface is stored at sheet heights)
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
CMAP = LinearSegmentedColormap.from_list("ramp", plt.get_cmap("turbo")(np.linspace(0.08, 0.95, 256)))   # rainbow, no black ends

SCANS = {   # survey_id: (image, georeference kind, georeference file, shift E, shift N)
    "usgs_1896": (G / "olmsted_02640-6_usgs1896_willamette_heights_local.png", "world",
                  G / "olmsted_02640-6_usgs1896_willamette_heights_local.pgw", 308, 57),
    "huber_1902": (G / "job02399_plan09_huber-maxwell-survey-blueprint.jpg", "points",
                   G / "job02399_plan09_huber-maxwell-survey-blueprint.jpg.p6fit.points", 20, -10),   # the 14-corner fit the traces use
    "olmsted_p6_1903": (G / "job02399_plan06_topographic-survey_stitched.tif", "points",
                        G / "job02399_plan06_topographic-survey_stitched.tif.points", 0, 0),
    "m1698_1906": (G / "M1698_blytheswood-park-contour-map-1906.jpg", "world",
                   G / "M1698_blytheswood-park-contour-map-1906.jgw", 0, 0),
    "m1697_westover": (G / "westover_terraces_1917_mosaic.jpg", "world", G / "westover_terraces_1917_mosaic.jgw", 0, 0),
    "job5174_1910": (G / "job05174_plan01_north-of-thurman-sheet-balchs-gulch-contracts-1910_upright.jpg", "world",
                     G / "job05174_plan01_north-of-thurman-sheet-balchs-gulch-contracts-1910_upright.jgw", 0, 0),
    "forestry_ext_c1910": (G / "forestry_extension_contours_russell_blythe_mosaic_warped.jpg", "world",
                           G / "forestry_extension_contours_russell_blythe_mosaic_warped.jgw", 0, 0),
}
SHORT = {   # overview titles
    "usgs_1896": "USGS 1896", "huber_1902": "Huber & Maxwell 1902", "olmsted_p6_1903": "Olmsted plan 6, 1903",
    "m1698_1906": "Blytheswood 1906", "m1697_westover": "Westover c.1906-10", "job5174_1910": "Balch's Gulch 1910",
    "forestry_ext_c1910": "Forestry Ext. c.1910",
}
ANCHOR = {   # where each overview title sits (EPSG:2913 ft): on the main body of that survey's lines, placed by hand
    "huber_1902": (7635046, 692771), "olmsted_p6_1903": (7637262, 690178), "job5174_1910": (7635612, 689565),
    "usgs_1896": (7634103, 688716), "forestry_ext_c1910": (7633019, 687679), "m1698_1906": (7634716, 687396),
    "m1697_westover": (7636178, 686972),
}
TURN = {"m1697_westover"}   # sheets photographed on their side: panels turned 90 degrees clockwise so north is up
SURFACES = {   # survey_id: [(dem, shift to the city datum), ...] first with data wins; else today's lidar
    "usgs_1896": [("nubbin_1896_dem", 0.0)],
    "huber_1902": [("combined_dem", 0.0)],
    "olmsted_p6_1903": [("combined_dem", 0.0)],
    "m1698_1906": [("m1698_dem", OFFSET)],
    "m1697_westover": [("m1697_dem", OFFSET)],
    "job5174_1910": [("job5174_1910_dem", 0.0)],
    "forestry_ext_c1910": [("gulch_prefill_dem", 0.0)],
}


def affine_from(kind, path, scale):
    """2x3 matrix (col, row, 1) -> (E, N) for the image read at 1/scale."""
    if kind == "world":
        a, d, b, e, c, f = [float(v) for v in path.read_text().split()]
        A = np.array([[a, b, c - a / 2 - b / 2], [d, e, f - d / 2 - e / 2]])   # pixel-centre world file -> corner
    else:
        rows = [r.split(",") for r in path.read_text(encoding="utf-8").splitlines() if r and r[0].isdigit()]
        rows = [r for r in rows if r[4].strip() == "1"]
        src = np.array([[float(r[2]), -float(r[3]), 1.0] for r in rows])
        dst = np.array([[float(r[0]), float(r[1])] for r in rows])
        A = np.linalg.lstsq(src, dst, rcond=None)[0].T
    A[:, :2] *= scale
    return A


def sample(name, gx, gy, nodata=True):
    """A terrain raster sampled at map points; NaN across its no-data (unless nodata=False)."""
    a = cv2.imread(str(T / f"{name}.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (T / f"{name}.tfw").read_text().split()]
    mx, my = ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32)
    z = cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderValue=-9999)
    if not nodata:
        return z
    bad = cv2.remap((a < -9000).astype(np.float32), mx, my, cv2.INTER_LINEAR, borderValue=1)
    return np.where(bad < 1e-3, z, np.nan)


def features(sid):
    out = []
    for L, _ in list_layers(GPKG):
        if L.startswith(sid):
            m, _, g, d = read(GPKG, layer=L)
            f = dict(zip(m["fields"], d))
            out += [(q, float(e) if e is not None else np.nan) for q, e in zip(from_wkb(g), f["elev_city"])]
    return out


def height_norm(feats):
    vals = np.array([e for _, e in feats if np.isfinite(e)])
    lo, hi = np.percentile(vals, 1), np.percentile(vals, 99)
    if hi - lo < 10:
        lo, hi = lo - 5, hi + 5
    return plt.Normalize(lo, hi)


def jpg(path, rgb):
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), (np.clip(rgb, 0, 1)[..., ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 86])


def rendered(fig):
    fig.canvas.draw()
    out = np.asarray(fig.canvas.buffer_rgba())[..., :3] / 255
    plt.close(fig)
    return out


def card(sid, footprint):
    img, kind, ref, dx, dy = SCANS[sid]
    A = affine_from(kind, ref, 1)
    A[:, 2] += (dx, dy)                                      # (col, row, 1) -> (E, N)
    Ai = np.linalg.inv(np.vstack([A, [0, 0, 1]]))[:2]        # (E, N, 1) -> (col, row)
    feats = features(sid)
    norm = height_norm(feats)
    # the crop: the traced lines in sheet pixels, plus a margin
    P = np.vstack([np.asarray(part.coords) for q, _ in feats for part in getattr(q, "geoms", [q])])
    cr = P @ Ai[:, :2].T + Ai[:, 2]
    c0, r0 = cr.min(axis=0)
    c1, r1 = cr.max(axis=0)
    m = 0.04 * max(c1 - c0, r1 - r0)
    w, h = Image.open(img).size
    c0, r0, c1, r1 = max(0, c0 - m), max(0, r0 - m), min(w, c1 + m), min(h, r1 + m)
    turn = sid in TURN
    s = PW / ((r1 - r0) if turn else (c1 - c0))
    PH = int(round(((c1 - c0) if turn else (r1 - r0)) * s))

    def to_uv(cr):                                           # sheet (col, row) -> panel (u, v)
        if turn:                                             # turned clockwise: the sheet's top edge becomes the right
            return np.c_[(r1 - cr[:, 1]) * s, (cr[:, 0] - c0) * s]
        return (cr - (c0, r0)) * s

    # 1. the sheet as printed
    a = cv2.imread(str(img), cv2.IMREAD_COLOR)
    a = a[int(r0):int(r1), int(c0):int(c1)]
    if turn:
        a = cv2.rotate(a, cv2.ROTATE_90_CLOCKWISE)
    sheet = cv2.resize(a, (PW, PH), interpolation=cv2.INTER_AREA)[..., ::-1] / 255
    del a
    jpg(OUT / f"{sid}-original.jpg", sheet)
    # 2. the traced lines coloured by height, drawn in sheet pixels over the sheet faded into the dark ground
    fig = plt.figure(figsize=(PW / 100, PH / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.imshow(DARK * 0.85 + sheet * 0.15, extent=(0, PW, PH, 0))
    lw = 0.9 * PW / 1200
    for q, e in feats:
        col = CMAP(norm(e)) if np.isfinite(e) else (0.6, 0.6, 0.6, 1)
        for part in getattr(q, "geoms", [q]):
            uv = to_uv(np.asarray(part.coords) @ Ai[:, :2].T + Ai[:, 2])
            if part.geom_type == "Point":
                ax.plot(uv[:, 0], uv[:, 1], ".", color=col, ms=3 * lw)
            else:
                ax.plot(uv[:, 0], uv[:, 1], color=col, lw=lw, solid_capstyle="round")
    ax.set_xlim(0, PW)
    ax.set_ylim(PH, 0)
    cax = fig.add_axes([0.60, 0.045, 0.36, 18 / PH])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=CMAP), cax=cax, orientation="horizontal")
    cb.ax.tick_params(labelsize=10, colors="white")
    cb.outline.set_edgecolor("white")
    cb.set_label("ft above the city datum", color="white", fontsize=10)
    jpg(OUT / f"{sid}-contours.jpg", rendered(fig))
    # 3. the reconstructed ground in the same frame: rainbow by height, shaded relief lit from the panel's upper left,
    #    only inside the survey's footprint
    jj, ii = np.meshgrid(np.arange(PW) + 0.5, np.arange(PH) + 0.5)
    cc, rr = (c0 + ii / s, r1 - jj / s) if turn else (c0 + jj / s, r0 + ii / s)
    gx = (A[0, 0] * cc + A[0, 1] * rr + A[0, 2]).astype(np.float32)
    gy = (A[1, 0] * cc + A[1, 1] * rr + A[1, 2]).astype(np.float32)
    z = np.full(gx.shape, np.nan, np.float32)
    for name, dz in SURFACES[sid]:
        z = np.where(np.isfinite(z), z, sample(name, gx, gy) - dz)
    mk = np.zeros((PH, PW), np.uint8)
    ring = to_uv(np.asarray(footprint.exterior.coords) @ Ai[:, :2].T + Ai[:, 2])
    cv2.fillPoly(mk, [ring.round().astype(np.int32)], 1)
    inside = np.isfinite(z) & (mk > 0)
    zf = np.where(np.isfinite(z), z, np.nanmedian(z))
    cell = np.hypot(A[0, 0], A[1, 0]) / s                    # ft per panel pixel
    # shaded like the bare-earth lidar: grey hillshade lit from several directions (mostly the panel's upper left),
    # darkened on steep slopes, heights x2; then the height colours laid over it at half strength
    vex = 2.0
    hs = sum(wt * LightSource(azdeg=az, altdeg=40).hillshade(zf, vert_exag=vex, dx=cell, dy=cell, fraction=1.0)
             for az, wt in ((315, 0.5), (270, 0.2), (360, 0.2), (225, 0.1)))
    gyy, gxx = np.gradient(zf * vex, cell)
    grey = hs * (1 - 0.45 * np.clip(np.degrees(np.arctan(np.hypot(gxx, gyy))) / 70, 0, 1))
    col = grey[..., None] * (0.5 + 0.5 * CMAP(norm(zf))[..., :3]) * 1.1
    jpg(OUT / f"{sid}-model.jpg", np.where(inside[..., None], np.clip(col, 0, 1), DARK))
    print(sid, f"{PW}x{PH};", len(feats), "features; colour range", round(norm.vmin), "-", round(norm.vmax))


def overview(W=1800):
    m, _, g, d = read(GPKG, layer="surveys")
    f = dict(zip(m["fields"], d))
    dates = dict(zip(f["survey_id"], f["date"]))
    feats = {sid: features(sid) for sid in f["survey_id"]}
    P = np.vstack([np.asarray(part.coords) for fs in feats.values() for q, _ in fs for part in getattr(q, "geoms", [q])])
    frame = (P[:, 0].min() - 350, P[:, 0].max() + 350, P[:, 1].min() - 350, P[:, 1].max() + 350)
    fw, fh = frame[1] - frame[0], frame[3] - frame[2]
    H = int(W * fh / fw)
    cell = fw / W
    gx, gy = np.meshgrid(np.linspace(frame[0], frame[1], W), np.linspace(frame[3], frame[2], H))
    # today's ground: the 2025 aerial in grey, multiplied onto the lidar hillshade, darkened so the colours carry
    ph = cv2.imread(str(T / "basemap_aerial_2025.jpg"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    w = [float(v) for v in (T / "basemap_aerial_2025.jgw").read_text().split()]
    ph = cv2.remap(ph, ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32), cv2.INTER_AREA)
    hs = LightSource(azdeg=315, altdeg=40).hillshade(sample("balch_hills_dem", gx, gy, False), vert_exag=1.5,
                                                     dx=cell, dy=cell)
    base = 0.12 + 0.62 * np.clip(0.55 * ph * (0.35 + 0.85 * hs) + 0.45 * (0.15 + 0.8 * hs), 0, 1)
    norm = height_norm([x for fs in feats.values() for x in fs])
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.imshow(np.repeat(base[..., None], 3, axis=2), extent=frame)
    order = sorted(feats, key=lambda k: str(dates[k]))
    for sid in order:
        for q, e in feats[sid]:
            col = CMAP(norm(e)) if np.isfinite(e) else (0.6, 0.6, 0.6, 1)
            for part in getattr(q, "geoms", [q]):
                if part.geom_type == "Point":
                    ax.plot(part.x, part.y, ".", color=col, ms=1.6)
                else:
                    x, y = part.xy
                    ax.plot(x, y, color=col, lw=0.45)
    halo = [pe.withStroke(linewidth=3.5, foreground="black")]
    for sid in order:
        ax.text(*ANCHOR[sid], SHORT[sid], color="white", fontsize=13, fontweight="bold", ha="center", va="center",
                path_effects=halo)
    ax.set_xlim(frame[0], frame[1])
    ax.set_ylim(frame[2], frame[3])
    cax = fig.add_axes([0.70, 0.04, 0.27, 0.015])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=CMAP), cax=cax, orientation="horizontal")
    cb.ax.tick_params(labelsize=9, colors="white")
    cb.outline.set_edgecolor("white")
    cb.set_label("ft above the city datum", color="white", fontsize=9)
    jpg(S.HERE / "topography" / "overview.jpg", rendered(fig))
    print("overview", W, H)


def main():
    if sys.argv[1:] == ["overview"]:
        return overview()
    m, _, g, d = read(GPKG, layer="surveys")
    ids = dict(zip(m["fields"], d))["survey_id"]
    want = set(sys.argv[1:])
    for q, sid in zip(from_wkb(g), ids):
        if not want or sid in want:
            card(sid, q)


if __name__ == "__main__":
    main()
