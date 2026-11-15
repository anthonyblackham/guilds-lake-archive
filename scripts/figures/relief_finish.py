r"""Finish a relief render for publishing: draw a clean double border over its edges, in the style of the printed
ones (a thick rule at the edge and a thin rule just inside it).

    python scripts/figures/relief_finish.py <render.png|jpg> [out.png|jpg] [--colour=222,230,236]
        [--flat=<flat render> --fade=build/relief/<id>/fade.png]

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
