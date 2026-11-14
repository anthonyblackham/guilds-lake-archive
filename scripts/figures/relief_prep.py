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
OWN_LINES = {"huber_1902"}   # surveys whose relief is interpolated straight from their own traced lines and heights
                             # (Huber's part of combined_dem predates the re-fitted plan 9 georeference)
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


def prep(sid, width, feather_ft, bevel):
    img, kind, ref, dx, dy = TC.SCANS[sid]
    A = TC.affine_from(kind, ref, 1)
    A[:, 2] += (dx, dy)                                      # sheet (col, row, 1) -> (E, N)
    w, h = Image.open(img).size
    out = BUILD / sid
    out.mkdir(parents=True, exist_ok=True)
    # texture: the whole sheet
    a = cv2.imread(str(img), cv2.IMREAD_COLOR)
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
    inside = (mk > 0) & np.isfinite(z)
    ft_px = np.hypot(A[0, 0], A[1, 0]) * k                   # feet per height-map pixel
    base = float(np.percentile(z[inside], 0.5))
    rel = np.where(inside, np.clip(z - base, 0, None), 0).astype(np.float32)
    dist = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5) * ft_px
    t = np.clip(dist / feather_ft, 0, 1)
    rel *= t * t * (3 - 2 * t)                               # smoothstep down to the paper at the footprint edge
    rel = np.minimum(rel, dist * bevel)                      # and where the edge cuts high ground, a bevel no steeper
                                                             # than `bevel` (rise per foot) instead of a cliff
    rel = cv2.GaussianBlur(rel, (0, 0), 0.7)
    top = float(rel.max())
    cv2.imwrite(str(out / "height.png"), np.round(rel / top * 65535).astype(np.uint16))
    meta = {"survey_id": sid, "sheet_px": [w, h], "height_px": [W, H], "ft_per_height_px": ft_px,
            "sheet_ft": [w * ft_px / k, h * ft_px / k], "relief_ft": top, "paper_level_city_ft": base,
            "feather_ft": feather_ft, "bevel": bevel, "surfaces": "own traced lines" if sid in OWN_LINES else TC.SURFACES[sid]}
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
    prep(a.survey_id, a.width, a.feather, a.bevel)
