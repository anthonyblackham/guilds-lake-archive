r"""Figure for the Pence story, chapter 1 (the promoter).

    python scripts/figures/pence_ch1.py

  ch1-portrait   "Hon. Lafe Pence", The Sigma Chi Quarterly vol. 12 p. 123 (Google Books cRcTAAAAIAAJ), saved by the
                 user as lewis-clark-1905/sources/lafe-pence.jpg; cropped to the printed frame and caption.
"""
import cv2

import figstyle as S

OUT = S.HERE / "stories" / "pence" / "figures"


def main():
    a = cv2.imread(str(S.PROJECT / "sources" / "lafe-pence.jpg"))
    h, w = a.shape[:2]
    crop = a[int(h * 0.205):int(h * 0.762), int(w * 0.215):int(w * 0.885)]     # the frame and "HON. LAFE PENCE"
    ch, cw = crop.shape[:2]
    out = cv2.resize(crop, (700, round(ch * 700 / cw)), interpolation=cv2.INTER_AREA if cw > 700 else cv2.INTER_CUBIC)
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / "ch1-portrait.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("wrote stories/pence/figures/ch1-portrait.jpg", out.shape)


if __name__ == "__main__":
    main()
