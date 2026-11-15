r"""Inputs for the Blender relief renders: the whole survey sheet as a flat sheet of paper, with only the ground it
surveys rising out of it.

    python scripts/figures/relief_prep.py <survey_id> [--width 4096] [--feather 150] [--bevel 0.12]

Writes to build/relief/<id>/ (ignored by git):
  texture.jpg     the sheet as printed (whole sheet, at most 8192 px wide)
  height.png      16-bit height map on the same frame: 0 = the paper, 65535 = the highest ground
  relief.json     sheet size in feet, height range, the paper's level on the city datum, how it was made
The height is the survey's reconstructed ground (topo_cards.SURFACES) inside its footprint, measured up from the
lowest ground there (so the lake bed / lowest contour sits on the paper), and eased down to the paper over the last
`feather` feet inside the footprint, and nowhere steeper than `bevel` from the edge, so the survey doesn't stand on
a cliff where its footprint cuts across high ground. Everything outside stays flat paper.
Use relief_render.py to render it.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pyogrio.raw import read
from shapely import from_wkb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topo_cards as TC  # noqa: E402  the scans, their georeferences and the surfaces

Image.MAX_IMAGE_PIXELS = None
BUILD = TC.S.HERE / "build" / "relief"
OWN_LINES = {"huber_1902", "m1698_1906"}   # surveys whose relief is interpolated straight from their own traced lines and heights
                             # (Huber's part of combined_dem predates the re-fitted plan 9 georeference)
CROP = {   # the part of each scan that is published: (left, top, right, bottom) as fractions of the scan
    "huber_1902": (0.0225, 0.1045, 0.9945, 0.9185),        # just inside the printed border; relief_finish.py redraws it
}
EVEN_GROUND = {   # sheets with a faded band: (top fraction of the height to even out, feather fraction)
    "huber_1902": (0.16, 0.06),
}
FEATHER = {}                     # a wider ease down to the paper (ft), per sheet
FADE = {"huber_1902": 350.0}     # shading faded to the flat sheet over this far inside the footprint (relief_finish)
FLUSH = {"m1698_1906": None,   # sheets whose high ground runs to the edge: relief measured from the edge surface
         "huber_1902": 12.0}
FLUSH_REACH_FT = 700.0
WATER = {   # survey: (gpkg, layer, shift E/N like its traced lines, water level ft city datum, what it is)
    "huber_1902": (TC.P / "qgis" / "expo-model.gpkg", "huber_1902_lakebed_refit", (20, -10), 8.0,
                   "Guild's Lake, August 1902: the user's lake outline re-fitted to plan 9; level = the 8 ft shore the "
                   "soundings are measured from"),
}         # how far in from a high edge the partial flush reaches    # (None = all of it; a level = only where the edge is higher than that, ft city)
BEVEL = {"m1698_1906": 0.8, "huber_1902": 0.6}  # steeper edge allowance for hill sheets (rise per foot); others use --bevel
NEAR_FT = 300               # how far from a traced line or height the interpolated ground may reach
SURFACE_KINDS = {"contour", "index", "intermediate", "sounding", "spot"}


def from_own_lines(sid, A, k, W, H):
    """Ground interpolated (linear, Delaunay) from the survey's contours and spot heights, in height-map pixels."""
    from pyogrio import list_layers
    from scipy.interpolate import LinearNDInterpolator
    Ai = np.linalg.inv(np.vstack([A, [0, 0, 1]]))[:2]
    pts, zs = [], []
    for L, _ in list_layers(TC.GPKG):
        if not L.startswith(sid):
            continue
        m, _, g, d = read(TC.GPKG, layer=L)
        f = dict(zip(m["fields"], d))
        for q, e, kd in zip(from_wkb(g), f["elev_city"], f["kind"]):
            if e is None or not np.isfinite(e) or kd not in SURFACE_KINDS:
                continue
            for part in getattr(q, "geoms", [q]):
                if part.geom_type == "Point":
                    xy = np.array([[part.x, part.y]])
                else:                                        # densify every ~8 ft along the line
                    n = max(2, int(part.length / 8))
                    xy = np.array([part.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n)])
                pts.append((xy @ Ai[:, :2].T + Ai[:, 2]) / k)
                zs.append(np.full(len(xy), float(e)))
    P, Z = np.vstack(pts), np.concatenate(zs)
    f2 = 2                                                   # interpolate at half resolution, then scale up
    gx, gy = np.meshgrid((np.arange(W // f2) + 0.5) * f2, (np.arange(H // f2) + 0.5) * f2)
    z = LinearNDInterpolator(P, Z)(gx, gy).astype(np.float32)
    ok = np.isfinite(z)
    zf = cv2.GaussianBlur(np.where(ok, z, 0), (0, 0), 2.0) / np.maximum(cv2.GaussianBlur(ok.astype(np.float32), (0, 0), 2.0), 1e-6)
    z = np.where(ok, zf, np.nan)                             # soften the flat Delaunay terraces between contours
    z = cv2.resize(z, (W, H), interpolation=cv2.INTER_LINEAR)
    # only near what was traced: the triangulation's long edges across untraced ground are not the survey
    seen = np.full((H, W), 255, np.uint8)
    ij = np.round(P).astype(int)
    ok = (ij[:, 0] >= 0) & (ij[:, 0] < W) & (ij[:, 1] >= 0) & (ij[:, 1] < H)
    seen[ij[ok, 1], ij[ok, 0]] = 0
    near = cv2.distanceTransform(seen, cv2.DIST_L2, 5) * np.hypot(A[0, 0], A[1, 0]) * k <= NEAR_FT
    return np.where(near, z, np.nan)


def even_ground(a, band):
    """Bring the paper colour in the top `band` of the sheet to the colour of the paper below it. The paper colour is
    estimated at low resolution with a median filter (the drawn lines are thin, so they drop out); the difference to
    the target colour is added back at full resolution, faded out over `feather` below the band."""
    top, feather = band
    h, w = a.shape[:2]
    f = 8
    small = cv2.resize(a, (w // f, h // f), interpolation=cv2.INTER_AREA)
    ground = cv2.medianBlur(small, 2 * (max(w // f // 60, 5) // 2) + 1)
    ground = cv2.GaussianBlur(ground.astype(np.float32), (0, 0), max(w // f // 120, 2))
    hh = h // f
    target = np.median(small[int(hh * (top + feather)):int(hh * 0.6)].reshape(-1, 3), axis=0).astype(np.float32)
    rows = np.arange(hh) / hh
    wt = np.clip((top + feather - rows) / feather, 0, 1)[:, None, None]
    corr = cv2.resize((target - ground) * wt, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.clip(a.astype(np.float32) + corr, 0, 255).astype(np.uint8)


def paper_level(g):
    """The paper's brightness around each pixel (median at low resolution, so lines and lettering drop out)."""
    h, w = g.shape
    f = 8
    small = cv2.resize(g, (w // f, h // f), interpolation=cv2.INTER_AREA)
    small = cv2.medianBlur(small, 2 * (max(w // f // 80, 5) // 2) + 1)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def line_mask(a, thresh=22.0):
    """The drawn (white) linework and lettering, whole strokes: pixels clearly brighter than the paper around them."""
    g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    m = (g.astype(np.float32) - paper_level(g) > thresh).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))   # drop single-pixel grain
    return cv2.dilate(m, np.ones((5, 5), np.uint8))


def clean_patch(a, mask, size, rows=(0.35, 0.95)):
    """The emptiest square of paper on the sheet: fewest drawn pixels, then the most even tone."""
    h, w = a.shape[:2]
    g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    best, at = None, None
    for y in range(int(h * rows[0]), int(h * rows[1]) - size, size // 4):
        for x in range(0, w - size, size // 4):
            ink = mask[y:y + size, x:x + size].mean()
            if ink > 0.002:
                continue
            tone = cv2.resize(g[y:y + size, x:x + size], (8, 8), interpolation=cv2.INTER_AREA).std()
            if best is None or tone < best:
                best, at = tone, (y, x)
    y, x = at
    return a[y:y + size, x:x + size].copy()


def tile_paper(patch, h, w, seed=7):
    """Paper of any size from one patch: tiles at half-patch spacing, randomly flipped, blended with Hann windows."""
    P = patch.shape[0]
    rng = np.random.default_rng(seed)
    win = np.outer(np.hanning(P), np.hanning(P)).astype(np.float32)[..., None] + 1e-3
    acc = np.zeros((h + 2 * P, w + 2 * P, 3), np.float32)
    wsum = np.zeros((h + 2 * P, w + 2 * P, 1), np.float32)
    for y in range(0, h + P // 2, P // 2):
        for x in range(0, w + P // 2, P // 2):
            t = patch
            if rng.random() < 0.5:
                t = t[::-1]
            if rng.random() < 0.5:
                t = t[:, ::-1]
            acc[y:y + P, x:x + P] += t.astype(np.float32) * win
            wsum[y:y + P, x:x + P] += win
    return (acc / wsum)[P // 2:P // 2 + h, P // 2:P // 2 + w]


def clone_paper(a, band):
    """Replace the paper of the top band with clean paper cloned from the emptiest part of the sheet (tiled, matched to
    the paper just below the band), keeping the band's drawn linework and lettering."""
    top, feather = band
    h, w = a.shape[:2]
    b = int(h * (top + feather))                             # band height, including the feather
    mask = line_mask(a)
    paper = tile_paper(clean_patch(a, mask, max(256, w // 14)), b, w)
    below = a[b:b + max(50, h // 40)].reshape(-1, 3)
    below = below[mask[b:b + max(50, h // 40)].reshape(-1) == 0]
    sample = paper[::7, ::7].reshape(-1, 3)                  # median of a sample (a float32 mean over the band drifts)
    paper += (np.median(below, axis=0) - np.median(sample, axis=0)).astype(np.float32)
    keep = cv2.GaussianBlur(mask[:b].astype(np.float32), (0, 0), 1.0)[..., None]
    wt = np.clip((b - np.arange(b)) / max(1, int(h * feather)), 0, 1)[:, None, None]   # 1 in the band -> 0 at its foot
    band_px = a[:b].astype(np.float32)
    new = paper * (1 - keep) + band_px * keep
    out = a.copy()
    out[:b] = np.clip(band_px * (1 - wt) + new * wt, 0, 255).astype(np.uint8)
    return out


def edge_surface(z, inside):
    """A smooth (harmonic) surface through the ground along the footprint's edge: the edge values are held and the
    inside relaxed coarse-to-fine, so it reaches the middle of big footprints."""
    H, W = z.shape
    ins = inside.astype(np.uint8)
    ring = ins - cv2.erode(ins, np.ones((3, 3), np.uint8))
    ry, rx = np.nonzero(ring)
    # outside the footprint: the nearest edge value, so every level has a clean held border
    _, lab = cv2.distanceTransformWithLabels((ring == 0).astype(np.uint8), cv2.DIST_L2, 5,
                                             labelType=cv2.DIST_LABEL_PIXEL)
    lut = np.zeros(lab.max() + 1, np.float32)
    lut[lab[ry, rx]] = z[ry, rx]
    held_val = np.where(ins > 0, np.where(ring > 0, z, 0), lut[lab]).astype(np.float32)
    held = (ring > 0) | (ins == 0)
    b = None
    for f in (32, 16, 8, 4, 2, 1):                           # coarse to fine
        w, h = max(8, W // f), max(8, H // f)
        hv = cv2.resize(np.where(held, held_val, 0), (w, h), interpolation=cv2.INTER_AREA)
        hw = cv2.resize(held.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
        hm = hw > 0.5
        hv = np.where(hm, hv / np.maximum(hw, 1e-6), 0)
        b = (np.where(hm, hv, float(z[ry, rx].mean())) if b is None
             else cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)).astype(np.float32)
        for _ in range(200 if f > 1 else 60):
            b = np.where(hm, hv, cv2.blur(b, (3, 3)))
    return b


def prep(sid, width, feather_ft, bevel):
    img, kind, ref, dx, dy = TC.SCANS[sid]
    A = TC.affine_from(kind, ref, 1)
    A[:, 2] += (dx, dy)                                      # sheet (col, row, 1) -> (E, N)
    w, h = Image.open(img).size
    out = BUILD / sid
    out.mkdir(parents=True, exist_ok=True)
    a = cv2.imread(str(img), cv2.IMREAD_COLOR)
    if sid in CROP:                                          # trim the sheet to its map; the sheet frame moves with it
        x0, y0, x1, y1 = CROP[sid]
        c0, r0, c1, r1 = round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)
        a = a[r0:r1, c0:c1]
        A[:, 2] += A[:, 0] * c0 + A[:, 1] * r0
        w, h = c1 - c0, r1 - r0
    if sid in EVEN_GROUND:                                   # even out a faded band of paper (lines kept)
        a = clone_paper(even_ground(a, EVEN_GROUND[sid]), EVEN_GROUND[sid])
    # texture: the (cropped) sheet
    if a.shape[1] > 8192:
        a = cv2.resize(a, (8192, round(a.shape[0] * 8192 / a.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "texture.jpg"), a, [cv2.IMWRITE_JPEG_QUALITY, 92])
    del a
    # height map on the sheet's own pixel frame
    W = min(width, w)
    H = round(h * W / w)
    k = w / W                                                # sheet pixels per height-map pixel
    jj, ii = np.meshgrid((np.arange(W) + 0.5) * k, (np.arange(H) + 0.5) * k)
    gx = (A[0, 0] * jj + A[0, 1] * ii + A[0, 2]).astype(np.float32)
    gy = (A[1, 0] * jj + A[1, 1] * ii + A[1, 2]).astype(np.float32)
    if sid in OWN_LINES:                                     # only what is traced on this sheet rises; untraced ground
        z = from_own_lines(sid, A, k, W, H)                  # stays paper until it is traced
    else:
        z = np.full((H, W), np.nan, np.float32)
        for name, dz in TC.SURFACES[sid]:
            z = np.where(np.isfinite(z), z, TC.sample(name, gx, gy) - dz)
    m, _, g, d = read(TC.GPKG, layer="surveys")
    fps = dict(zip(dict(zip(m["fields"], d))["survey_id"], from_wkb(g)))
    Ai = np.linalg.inv(np.vstack([A, [0, 0, 1]]))[:2]
    mk = np.zeros((H, W), np.uint8)
    cr = (np.asarray(fps[sid].exterior.coords) @ Ai[:, :2].T + Ai[:, 2]) / k
    cv2.fillPoly(mk, [cr.round().astype(np.int32)], 1)
    lake = None
    if sid in WATER:                                         # the lake outline belongs to the surveyed ground too: where
        wg, wl, (wdx, wdy), level, what = WATER[sid]         # no traced height reaches it, give it a bed just under water
        _, _, g2, _ = read(wg, layer=wl)
        lake = np.zeros((H, W), np.uint8)
        for q in from_wkb(g2):
            for pg in getattr(q, "geoms", [q]):
                rings = [pg.exterior] + list(pg.interiors)
                pts = [((np.asarray(r.coords) + (wdx, wdy)) @ Ai[:, :2].T + Ai[:, 2]) / k for r in rings]
                cv2.fillPoly(lake, [pts[0].round().astype(np.int32)], 255)
                for hole in pts[1:]:
                    cv2.fillPoly(lake, [hole.round().astype(np.int32)], 0)
        z = np.where((lake > 0) & ~((mk > 0) & np.isfinite(z)), level - 3.0, z)
        z = np.where(lake > 0, np.minimum(z, level - 0.5), z)  # the outline is the shore: inside it, the bed stays under water
        mk = np.maximum(mk, (lake > 0).astype(np.uint8))
    inside = (mk > 0) & np.isfinite(z)
    ft_px = np.hypot(A[0, 0], A[1, 0]) * k                   # feet per height-map pixel
    flush = sid in FLUSH
    if flush:                                                # relief measured from a smooth surface that follows the
        base_s = edge_surface(z, inside)                     # ground along the footprint edge, so high edges sit flush
        above = FLUSH[sid]                                   # with the paper; ridges rise, ravines sink in. With a level
        if above is not None:                                # given, only edge ground above it is flushed (low shores
            base_s = np.clip(base_s - above, 0, None)        # keep their full rise), and only near that edge
            d_edge = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5) * np.hypot(A[0, 0], A[1, 0]) * k
            base_s *= np.clip(1 - d_edge / FLUSH_REACH_FT, 0, 1) ** 2
        z = np.where(inside, z - base_s, np.nan)
    base = 0.0 if flush and FLUSH[sid] is None else float(np.percentile(z[inside], 0.5))
    rel = np.where(inside, z - base if flush and FLUSH[sid] is None else np.clip(z - base, 0, None), 0).astype(np.float32)
    dist = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5) * ft_px
    t = np.clip(dist / feather_ft, 0, 1)
    rel *= t * t * (3 - 2 * t)                               # smoothstep down to the paper at the footprint edge
    rel = np.clip(rel, -dist * bevel, dist * bevel)                      # and where the edge cuts high ground, a bevel no steeper
                                                             # than `bevel` (rise per foot) instead of a cliff
    rel = cv2.GaussianBlur(rel, (0, 0), 0.7)
    lo, top = float(min(rel.min(), 0)), float(rel.max())
    cv2.imwrite(str(out / "height.png"), np.round((rel - lo) / (top - lo) * 65535).astype(np.uint16))
    meta = {"survey_id": sid, "sheet_px": [w, h], "height_px": [W, H], "ft_per_height_px": ft_px,
            "sheet_ft": [w * ft_px / k, h * ft_px / k], "relief_ft": top - lo, "paper_frac": -lo / (top - lo), "paper_level_city_ft": base,
            "feather_ft": feather_ft, "bevel": bevel, "flush": flush, "surfaces": "own traced lines" if sid in OWN_LINES else TC.SURFACES[sid]}
    if lake is not None:                                     # the lake as its own mask, at its own level
        wm = cv2.dilate(lake, np.ones((5, 5), np.uint8))     # reach just under the shore so it meets the ground
        wm[~inside] = 0
        cv2.imwrite(str(out / "water.png"), wm)
        meta["water"] = {"level_city_ft": level, "level_rel_ft": level - base, "what": what}
    if sid in FADE:                                          # 0 at the footprint edge -> 1 FADE ft inside: relief_finish
        t2 = np.clip(dist / FADE[sid], 0, 1)                 # blends the flat render into the relief render with it
        cv2.imwrite(str(out / "fade.png"), np.round(t2 * t2 * (3 - 2 * t2) * 255).astype(np.uint8))
        meta["fade_ft"] = FADE[sid]
    (out / "relief.json").write_text(json.dumps(meta, indent=1))
    print(sid, f"sheet {meta['sheet_ft'][0]:.0f} x {meta['sheet_ft'][1]:.0f} ft; relief {top:.0f} ft above "
          f"{base:.1f}; height map {W}x{H}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("survey_id")
    ap.add_argument("--width", type=int, default=4096)
    ap.add_argument("--feather", type=float, default=150.0)
    ap.add_argument("--bevel", type=float, default=0.12)
    a = ap.parse_args()
    prep(a.survey_id, a.width, FEATHER.get(a.survey_id, a.feather) if a.feather == 150.0 else a.feather,
         BEVEL.get(a.survey_id, a.bevel) if a.bevel == 0.12 else a.bevel)
