r"""Finish a relief render for publishing: draw a clean double border over its edges, in the style of the printed
ones (a thick rule at the edge and a thin rule just inside it).

    python scripts/figures/relief_finish.py <render.png|jpg> [out.png|jpg] [--colour=222,230,236]
        [--flat=<flat render> --fade=build/relief/<id>/fade.png]
        [--mark=build/relief/<id>/relief.json --label="Title|subtitle" --label-at=0.22,0.86 --leader=0]

With --flat/--fade, the relief render is first blended into a flat render of the same sheet and light (relief_render
--flat 1) by the fade mask, so the relief dissolves into the paper at the edge of the surveyed ground.

Give a .png out for the published master: it is written lossless, with a progressive web JPEG (quality 90) beside it.

Sizes are fractions of the image width, so they scale with the render: thick rule 0.9%, gap 0.45%, thin rule 0.15%.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith("--")]
src = Path(args[0])
dst = Path(args[1]) if len(args) > 1 else src.with_name(src.stem + "-framed.jpg")
colour = (222, 230, 236)
for a in sys.argv[1:]:
    if a.startswith("--colour="):
        colour = tuple(int(v) for v in a.split("=", 1)[1].split(","))   # noqa: E501
img = cv2.imread(str(src), cv2.IMREAD_COLOR)
h, w = img.shape[:2]
opts = dict(a.split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
if "--flat" in opts:                                         # fade the relief into the flat render at the footprint edge
    flat = cv2.resize(cv2.imread(opts["--flat"], cv2.IMREAD_COLOR), (w, h), interpolation=cv2.INTER_AREA)
    m = cv2.resize(cv2.imread(opts["--fade"], cv2.IMREAD_GRAYSCALE), (w, h), interpolation=cv2.INTER_LINEAR)
    m = (m.astype(np.float32) / 255)[..., None]
    img = (flat * (1 - m) + img * m).round().astype(np.uint8)
bgr = colour[::-1]
if "--mark" in opts:                                         # outline a feature in red and label it with a leader line
    import json
    from PIL import Image, ImageDraw, ImageFont
    mk = json.loads(Path(opts["--mark"]).read_text())["mark"]
    pil = Image.fromarray(img[..., ::-1])
    dr = ImageDraw.Draw(pil)
    red, halo = (190, 30, 30), (255, 250, 240)
    lw = max(2, round(w * 0.0022))
    pts_all = [(x * w, y * h) for line in mk["lines"] for x, y in line]
    xs, ys = [p[0] for p in pts_all], [p[1] for p in pts_all]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    rx, ry = (max(xs) - min(xs)) * 0.95 + w * 0.012, (max(ys) - min(ys)) * 0.95 + w * 0.012   # a loose ring around it
    for wd, col in ((2 * lw + 4, halo), (2 * lw, red)):          # the ring at twice the line weight
        dr.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=col, width=wd)
    r = (rx + ry) / 2
    lx, ly = (float(v) * s for v, s in zip(opts.get("--label-at", "0.22,0.86").split(","), (w, h)))
    text = opts.get("--label", "")
    size = round(w * 0.022)
    font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", size)
    small = ImageFont.truetype("C:/Windows/Fonts/georgiai.ttf", round(size * 0.72))
    title, _, sub = text.partition("|")
    # leader from the label to the ring's edge
    d = np.hypot(cx - lx, cy - ly)
    ux, uy = (lx - cx) / d, (ly - cy) / d                    # the leader stops at the ellipse
    k = 1 / np.hypot(ux / rx, uy / ry)
    ex, ey = cx + ux * k, cy + uy * k
    if opts.get("--leader", "1") != "0":
        dr.line([(lx, ly), (ex, ey)], fill=halo, width=lw + 4)
        dr.line([(lx, ly), (ex, ey)], fill=red, width=lw)
    bx = dr.textbbox((0, 0), title, font=font)
    sb = dr.textbbox((0, 0), sub, font=small) if sub else (0, 0, 0, 0)
    tw, th = max(bx[2], sb[2]), bx[3] + (sb[3] + size * 0.35 if sub else 0)
    pad = size * 0.45
    x0 = lx - tw - pad * 2 if lx > cx else lx
    y0 = ly - th / 2 - pad
    dr.rounded_rectangle([x0, y0, x0 + tw + pad * 2, y0 + th + pad * 2], radius=pad * 0.6, fill=halo, outline=red,
                         width=lw)
    dr.text((x0 + pad, y0 + pad), title, font=font, fill=red)
    if sub:
        dr.text((x0 + pad, y0 + pad + bx[3] + size * 0.35), sub, font=small, fill=(90, 40, 30))
    img = np.asarray(pil)[..., ::-1].copy()
thick, gap, thin = (max(1, round(f * w)) for f in (0.009, 0.0045, 0.0015))
out = img.copy()
cv2.rectangle(out, (0, 0), (w - 1, h - 1), bgr, thickness=2 * thick)            # half of it falls outside the image
i = thick + gap
cv2.rectangle(out, (i, i), (w - 1 - i, h - 1 - i), bgr, thickness=thin, lineType=cv2.LINE_AA)
# rules printed on paper are slightly soft: blend them in a touch
mask = cv2.GaussianBlur((np.abs(out.astype(int) - img.astype(int)).sum(axis=2) > 0).astype(np.float32), (0, 0), 0.6)
out = (img * (1 - mask[..., None]) + out * mask[..., None]).astype(np.uint8)
if dst.suffix.lower() == ".png":                             # the master, lossless, plus a web JPEG beside it
    cv2.imwrite(str(dst), out, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    web = dst.with_suffix(".jpg")
    cv2.imwrite(str(web), out, [cv2.IMWRITE_JPEG_QUALITY, 90, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    print("framed", dst, "and", web, w, h)
else:
    cv2.imwrite(str(dst), out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("framed", dst, w, h)
