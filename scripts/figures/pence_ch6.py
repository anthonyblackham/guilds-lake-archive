r"""Figures for the Pence story, chapter 6 (the shovels, and the money runs out, 1907-1909).

    python scripts/figures/pence_ch6.py

Reads the research project (lewis-clark-1905) read-only; writes stories/pence/figures/ch6-*.jpg.
  ch6-knoll-section   W-E section through the Scotch Nubbin: 1896 knoll (nubbin_1896_dem, re-anchored on the knob),
                      the March 1907 upper bound from the picture's hill edge (scripts/cam1907/profile.json), today
  ch6-money-timeline  loans and bank failures, 1905-1909, as reported (dates and sums from data/pence_timeline.csv)
"""
import json
from datetime import date

import cv2
import matplotlib.dates as mdates
import numpy as np

import figstyle as S

P = S.PROJECT
OUT = S.HERE / "stories" / "pence" / "figures"
CITY = 2.10   # city datum = NAVD88 - 2.10 ft


def raster(name):
    a = cv2.imread(str(P / "qgis" / "terrain" / f"{name}.tif"), cv2.IMREAD_UNCHANGED).astype(np.float32)
    w = [float(v) for v in (P / "qgis" / "terrain" / f"{name}.tfw").read_text().split()]

    def at(x, y):
        c = ((np.asarray(x) - w[4]) / w[0]).astype(np.float32)
        r = ((np.asarray(y) - w[5]) / w[3]).astype(np.float32)
        v = cv2.remap(a, c.reshape(1, -1), r.reshape(1, -1), cv2.INTER_LINEAR, borderValue=-9999)[0]
        return np.where(v > -9000, v, np.nan)
    return at


def knoll_section():
    prof = json.loads((P / "scripts" / "cam1907" / "profile.json").read_text())
    n = prof["line_N"]
    e = np.arange(7633500, 7634700, 5.0)
    today = raster("balch_hills_dem")(e, np.full_like(e, n)) - CITY
    knoll = raster("nubbin_1896_dem")(e, np.full_like(e, n))
    knoll = np.where(np.isfinite(knoll), np.maximum(knoll, today), today)
    be = np.array(prof["E"]); bound = np.array(prof["bound"], float) - CITY
    bound = np.interp(e, be, bound, left=np.nan, right=np.nan)
    bound = np.where(np.isfinite(bound), np.clip(bound, today, knoll), np.nan)   # between today and the uncut knoll
    x = e - 7634108.0                                   # ft from today's knob top
    fig = S.figure(0.45)
    ax = fig.add_axes([0.08, 0.14, 0.9, 0.8])
    ax.set_facecolor(S.PAPER)
    ax.fill_between(x, 250, today, color="#d9cfbd", lw=0)
    ok = np.isfinite(bound)
    ax.fill_between(x[ok], today[ok], bound[ok], color=S.CUT, alpha=0.18, lw=0, label="March 1907: somewhere in this band")
    ax.plot(x, knoll, color=S.INK, lw=1.6, ls=(0, (5, 3)), label="1896 survey (before any cutting)")
    ax.plot(x, today, color=S.INK, lw=1.8, label="today (2019 lidar)")
    ax.annotate(f"1896 knoll: {np.nanmax(knoll):.0f} ft on this line\n(summit 429 ft, just north of it)",
                xy=(x[np.nanargmax(knoll)], np.nanmax(knoll)), xytext=(-560, 418),
                fontsize=8, color=S.INK, arrowprops=dict(arrowstyle="-", color=S.MUTED, lw=0.8))
    ax.annotate("March 1907:\nno higher than about 391 ft", xy=(60, 386), xytext=(170, 405), fontsize=8, color=S.CUT,
                arrowprops=dict(arrowstyle="-", color=S.CUT, lw=0.8))
    ax.annotate("today's knob, 374 ft\n(houses on Auburn St)", xy=(0, 374), xytext=(140, 352), fontsize=8, color=S.INK,
                arrowprops=dict(arrowstyle="-", color=S.MUTED, lw=0.8))
    ax.annotate("the small valley behind the knoll", xy=(-350, 328), xytext=(-560, 300), fontsize=8, color=S.MUTED,
                arrowprops=dict(arrowstyle="-", color=S.MUTED, lw=0.8))
    ax.set_xlim(x[0], x[-1]); ax.set_ylim(260, 440)
    ax.set_xlabel("feet east of today's knob top (section west-east along N 688,467)", fontsize=8)
    ax.set_ylabel("feet above the city datum", fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=7.5)
    ax.grid(True, color="#e4dccb", lw=0.6)
    ax.legend(loc="lower left", frameon=False, fontsize=7.5)
    S.save(fig, OUT / "ch6-knoll-section.jpg")


EVENTS = [  # date, row colour (0 = money, 1 = events), label height, label
    (date(1905, 9, 1), 0, 0.45, "Oregon Trust & Savings\nlends $9,475 on the\nhydraulic plant (1905)"),
    (date(1906, 6, 1), 0, 0.95, "Title Guarantee & Trust,\nvia Colonial Investment:\n$220,000 (Pence) to\n$399,000 (examiners)"),
    (date(1907, 2, 15), 1, -0.35, "trestle collapse,\nPurdin killed"),
    (date(1907, 5, 9), 1, -0.78, "McCabe's shovels\nhired"),
    (date(1907, 6, 22), 0, 0.45, "debt moved to\nColonial Investment"),
    (date(1907, 8, 20), 1, -1.18, "Oregon Trust & Savings\nfails"),
    (date(1907, 10, 28), 1, -0.35, "Title Guarantee\ncloses its doors"),
    (date(1908, 2, 7), 0, 0.95, "examiners: Pence\ncompanies owe $399,000"),
    (date(1908, 8, 20), 1, -0.78, "Pence in court,\npays four silver dollars"),
    (date(1909, 6, 26), 1, -0.35, "park flume\nremoved"),
    (date(1909, 11, 21), 0, 0.45, "Lewis & Wiley buy\nthe land"),
]


def money_timeline():
    fig = S.figure(0.42)
    ax = fig.add_axes([0.03, 0.12, 0.94, 0.84])
    ax.set_facecolor(S.PAPER)
    d0, d1 = date(1905, 6, 1), date(1910, 2, 1)
    ax.axhline(0, color=S.INK, lw=1.2)
    for y in range(1905, 1911):
        dd = date(y, 1, 1)
        if d0 <= dd <= d1:
            ax.plot([dd, dd], [-0.06, 0.06], color=S.INK, lw=1)
            ax.text(dd, -0.13, str(y), ha="center", va="top", fontsize=8.5, fontweight="bold", color=S.INK)
    ax.axvspan(date(1907, 8, 20), date(1907, 11, 6), color=S.CUT, alpha=0.10, lw=0)
    ax.text(date(1907, 9, 28), 1.33, "the panic of 1907", ha="center", fontsize=7.5, color=S.CUT, fontstyle="italic")
    for dd, row, lvl, text in EVENTS:
        col = "#8a5a2b" if row == 0 else S.INK
        ax.plot([dd, dd], [0, lvl * 0.92], color=col, lw=0.8)
        ax.plot([dd], [0], "o", color=col, ms=4)
        right = text.startswith("Title Guarantee\n")      # clear of the Oregon Trust stem just before it
        ax.text(dd, lvl, ("  " if right else "") + text.replace("\n", "\n  " if right else "\n"),
                ha="left" if right else "center", va="bottom" if lvl > 0 else "top", fontsize=7, color=col, linespacing=1.15)
    ax.text(d0, 1.42, "money", fontsize=8, color="#8a5a2b", fontweight="bold", va="top")
    ax.text(d0, -1.42, "events", fontsize=8, color=S.INK, fontweight="bold", va="bottom")
    ax.set_xlim(d0, d1); ax.set_ylim(-1.45, 1.45)
    ax.axis("off")
    S.save(fig, OUT / "ch6-money-timeline.jpg")


if __name__ == "__main__":
    knoll_section()
    money_timeline()
