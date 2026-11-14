r"""Showcase cards for the historic topography page: three images per survey, all in one square frame.

    python scripts/figures/topo_cards.py [survey_id ...]

For each survey in gis/historic_topography.gpkg (layer `surveys`):
  topography/cards/<id>-original.jpg   the georeferenced sheet (as printed), cropped to the frame
  topography/cards/<id>-contours.jpg   the traced contours / spot heights coloured by height (city datum) over today's
                                       ground (2019 lidar hillshade)
  topography/cards/<id>-model.jpg      an oblique view of the reconstructed surface built from them, same colours
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
from matplotlib.colors import LightSource  # noqa: E402
from pyogrio.raw import read  # noqa: E402
from shapely import from_wkb  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

P = S.PROJECT
G = P / "qgis" / "georeference"
T = P / "qgis" / "terrain"
GPKG = S.HERE / "gis" / "historic_topography.gpkg"
OUT = S.HERE / "topography" / "cards"
PX = 900               # each panel, square
OFFSET = 3.4           # M/1698, M/1697 sheets read this high (the hills surface is stored at sheet heights)
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
CMAP = LinearSegmentedColormap.from_list("topo", plt.get_cmap("terrain")(np.linspace(0.12, 0.82, 256)))   # no white top

SCANS = {   # survey_id: (image, georeference kind, georeference file, shift E, shift N)
    "usgs_1896": (G / "olmsted_02640-6_usgs1896_willamette_heights_local.png", "world",
                  G / "olmsted_02640-6_usgs1896_willamette_heights_local.pgw", 308, 57),
    "huber_1902": (G / "job02399_plan09_huber-maxwell-survey-blueprint.jpg", "points",
                   G / "job02399_plan09_huber-maxwell-survey-blueprint.jpg.points", 20, -10),
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
VIEW = {   # view azimuth for the oblique (my convention: -35 = from the south-east, -135 = from the north-east, 180 = from
           # the north): each survey seen from the side its ground faces (the hills fall north and east to the gulch and lake)
    "usgs_1896": -135, "m1698_1906": -135, "m1697_westover": -135, "forestry_ext_c1910": -135,
    "job5174_1910": 180, "huber_1902": 180, "olmsted_p6_1903": 180,
}
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


def scan_panel(sid, frame, cell):
    img, kind, ref, dx, dy = SCANS[sid]
    probe = cv2.imread(str(img), cv2.IMREAD_REDUCED_COLOR_4)
    scale = 1
    if probe is not None and max(probe.shape[:2]) * 4 > 9000:
        scale = 2 if max(probe.shape[:2]) * 4 <= 18000 else 4
    flag = {1: cv2.IMREAD_COLOR, 2: cv2.IMREAD_REDUCED_COLOR_2, 4: cv2.IMREAD_REDUCED_COLOR_4}[scale]
    a = cv2.imread(str(img), flag)
    A = affine_from(kind, ref, scale)
    A[:, 2] += (dx, dy)
    Ai = np.linalg.inv(np.vstack([A, [0, 0, 1]]))
    x0, x1, y0, y1 = frame
    gx, gy = np.meshgrid(np.linspace(x0, x1, PX), np.linspace(y1, y0, PX))
    col = Ai[0, 0] * gx + Ai[0, 1] * gy + Ai[0, 2]
    row = Ai[1, 0] * gx + Ai[1, 1] * gy + Ai[1, 2]
    return cv2.remap(a, col.astype(np.float32), row.astype(np.float32), cv2.INTER_AREA if scale == 1 else cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=(228, 222, 210))


def grid(name, frame, n):
    a = cv2.imread(str(T / f"{name}.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (T / f"{name}.tfw").read_text().split()]
    x0, x1, y0, y1 = frame
    gx, gy = np.meshgrid(np.linspace(x0, x1, n), np.linspace(y1, y0, n))
    mx, my = ((gx - w[4]) / w[0]).astype(np.float32), ((gy - w[5]) / w[3]).astype(np.float32)
    z = cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderValue=-9999)
    bad = cv2.remap((a < -9000).astype(np.float32), mx, my, cv2.INTER_LINEAR, borderValue=1)
    return np.where(bad < 1e-3, z, np.nan)           # no blending across no-data edges


def write_oblique(z, col, cellft, path, az=-35.0, el=34.0, vex=1.6):
    """Orthographic oblique render of a height grid (rows north -> south) with per-cell colours, z-buffered splats.
    Viewer to the south-east (az = view azimuth from north, degrees), looking down at el degrees."""
    n = z.shape[0]
    jj, ii = np.meshgrid(np.arange(n), np.arange(n))
    x = jj * cellft
    y = (n - 1 - ii) * cellft
    a = np.radians(az)
    xr = x * np.cos(a) - y * np.sin(a)                  # across the view
    yr = x * np.sin(a) + y * np.cos(a)                  # into the view (depth)
    e = np.radians(el)
    zr = z - np.nanmin(z)
    sy = yr * np.sin(e) + zr * vex * np.cos(e)          # up the screen
    W = H = PX
    sx = (xr - xr.min()) / (xr.max() - xr.min()) * (W * 0.9) + W * 0.05
    span = sy.max() - sy.min()
    k = (W * 0.9) / (xr.max() - xr.min())
    sv = H * 0.5 + (sy.min() + span / 2 - sy) * k
    img = np.full((H, W, 3), [0xf4 / 255, 0xef / 255, 0xe4 / 255], np.float32)
    zb = np.full((H, W), np.inf, np.float32)
    order = np.argsort(-yr.ravel())                     # far to near
    u0, v0 = sx.ravel()[order], sv.ravel()[order]
    dep, cc = yr.ravel()[order], col.reshape(-1, 3)[order]   # nearer = smaller depth
    r = max(1, int(np.ceil(k * cellft)))
    for du in range(r + 2):
        for dv in range(r + 7):
            u = (u0 + du).astype(int); v = (v0 + dv).astype(int)
            m = (u >= 0) & (u < W) & (v >= 0) & (v < H)
            uu, vv, dd, c = u[m], v[m], dep[m], cc[m]
            near = dd < zb[vv, uu]
            img[vv[near], uu[near]] = c[near]; zb[vv[near], uu[near]] = dd[near]
    cv2.imwrite(str(path), (np.clip(img, 0, 1)[..., ::-1] * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 86])


def features(sid):
    from pyogrio import list_layers
    out = []
    for L, _ in list_layers(GPKG):
        if L.startswith(sid):
            m, _, g, d = read(GPKG, layer=L)
            f = dict(zip(m["fields"], d))
            out += [(q, float(e) if e is not None else np.nan, k) for q, e, k in zip(from_wkb(g), f["elev_city"], f["kind"])]
    return out


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=PX / 6, facecolor=S.PAPER, pil_kwargs={"quality": 86})
    plt.close(fig)


def card(sid, footprint):
    bx0, by0, bx1, by1 = footprint.bounds
    side = max(bx1 - bx0, by1 - by0) * 1.04
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    frame = (cx - side / 2, cx + side / 2, cy - side / 2, cy + side / 2)
    OUT.mkdir(parents=True, exist_ok=True)
    feats = features(sid)
    vals = np.array([e for _, e, _ in feats if np.isfinite(e)])
    lo, hi = np.percentile(vals, 2), np.percentile(vals, 98)
    if hi - lo < 10:
        lo, hi = lo - 5, hi + 5
    norm = plt.Normalize(lo, hi)
    # 1. the sheet
    sc = scan_panel(sid, frame, side / PX)
    cv2.imwrite(str(OUT / f"{sid}-original.jpg"), sc, [cv2.IMWRITE_JPEG_QUALITY, 86])
    # 2. the traced lines over today's ground
    today = grid("balch_hills_dem", frame, 600) - 2.10
    gy_, gx_ = np.gradient(np.nan_to_num(today, nan=np.nanmin(today)), side / 600)
    sl = np.arctan(np.hypot(gx_, gy_) * 1.3)
    shade = np.clip(np.sin(0.7) * np.cos(sl) + np.cos(0.7) * np.sin(sl) * np.cos(np.radians(315) - np.arctan2(-gx_, gy_)), 0, 1)
    fig = plt.figure(figsize=(6, 6), facecolor=S.PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(shade, cmap="gray", extent=frame, vmin=-0.4, vmax=1.25, interpolation="bilinear")
    for q, e, k in feats:
        col = CMAP(norm(e)) if np.isfinite(e) else (0.55, 0.5, 0.45, 1)
        if q.geom_type == "Point":
            ax.plot(q.x, q.y, "o", ms=2.2, color=col, mec="none")
        else:
            for part in getattr(q, "geoms", [q]):
                x, y = part.xy
                ax.plot(x, y, color=col, lw=1.4 if k == "index" else 0.9)
    ax.set_xlim(frame[0], frame[1]); ax.set_ylim(frame[2], frame[3]); ax.set_aspect("equal"); ax.axis("off")
    cax = fig.add_axes([0.06, 0.05, 0.4, 0.022])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=CMAP), cax=cax, orientation="horizontal")
    cb.set_label("ft above the city datum", fontsize=7, color=S.INK); cb.ax.tick_params(labelsize=6.5, colors=S.INK)
    cax.patch.set_alpha(0)
    save(fig, f"{sid}-contours.jpg")
    # 3. the reconstructed surface: oblique view from the south-east, lit from the north-west; coloured where the survey
    #    reconstructs the ground, today's ground in grey around it for context
    n = 420
    z = np.full((n, n), np.nan)
    for name, dz in SURFACES[sid]:
        zz = grid(name, frame, n) - dz
        z = np.where(np.isfinite(z), z, zz)
    base = grid("balch_hills_dem", frame, n) - 2.10
    inside = np.isfinite(z)
    z = np.where(inside, z, base)
    z = np.where(np.isfinite(z), z, np.nanmin(z))
    cellft = side / n
    ls = LightSource(azdeg=315, altdeg=38)
    hs = ls.hillshade(z, vert_exag=1.6, dx=cellft, dy=cellft)
    col = CMAP(norm(z))[..., :3]
    col = np.clip(col * (0.45 + 0.75 * hs[..., None]), 0, 1)
    grey = (0.38 + 0.55 * hs)[..., None] * np.array([0.93, 0.91, 0.88])
    col = np.where(inside[..., None], col, grey * 0.9 + 0.08)
    rr, cc = np.nonzero(inside)                        # crop to the reconstructed area, plus a margin of context
    pad = int(0.15 * max(np.ptp(rr), np.ptp(cc))) + 4
    r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad, n - 1)
    c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad, n - 1)
    m = max(r1 - r0, c1 - c0)
    r0 = max(min(r0, n - 1 - m), 0); c0 = max(min(c0, n - 1 - m), 0)
    sl_ = (slice(r0, r0 + m + 1), slice(c0, c0 + m + 1))
    write_oblique(z[sl_], col[sl_], cellft, OUT / f"{sid}-model.jpg", az=VIEW.get(sid, -35.0))
    print(sid, "frame", round(side), "ft;", len(feats), "features; colour range", round(lo), "-", round(hi))
    return frame, (lo, hi)


def main():
    m, _, g, d = read(GPKG, layer="surveys")
    ids = dict(zip(m["fields"], d))["survey_id"]
    want = set(sys.argv[1:])
    for q, sid in zip(from_wkb(g), ids):
        if not want or sid in want:
            card(sid, q)


if __name__ == "__main__":
    main()
