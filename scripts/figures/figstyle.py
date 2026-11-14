"""Shared look for the story figures (see stories/FIGURES.md).

Figures are fixed files made for a story, not views of the live viewer. They read the research project
(lewis-clark-1905) read-only and write into stories/<story>/figures/.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parents[2]          # guilds-lake-archive/
PROJECT = HERE.parent / "lewis-clark-1905"          # the research project (read only)
WIDTH_PX = 1600                                     # every figure is exported 1600 px wide
DPI = 200

# one palette for every story (also in stories/FIGURES.md)
INK = "#2a241c"        # labels, outlines
PAPER = "#f4efe4"      # figure ground
MUTED = "#6d6354"      # secondary labels, scale bar
CUT = "#b3261e"        # ground cut away (historic cut faces, red)
CUT_SINCE = "#2f6fb0"  # ground cut away since (model comparisons, blue)
FLUME = "#d9822b"      # flumes, ditches, pipelines (orange)
WATER = "#6f9fb8"      # historic water (1902 lake)
BUILT = "#8a7a62"      # historic buildings

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "text.color": INK,
    "axes.edgecolor": INK,
    "savefig.facecolor": PAPER,
})


def figure(aspect):
    """A figure WIDTH_PX wide with height = width * aspect."""
    w = WIDTH_PX / DPI
    return plt.figure(figsize=(w, w * aspect), dpi=DPI, facecolor=PAPER)


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=PAPER, pil_kwargs={"quality": 88})
    plt.close(fig)
    print("wrote", path.relative_to(HERE))


def north_arrow(ax, x, y, size=0.06):
    """North arrow in axes fraction coordinates (map grids here are EPSG:2913, grid north ~ true north)."""
    ax.annotate("N", xy=(x, y), xytext=(x, y - size), xycoords="axes fraction", ha="center", va="center",
                fontsize=10, fontweight="bold", color=INK,
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2))


def scale_bar(ax, x0, y0, feet, label=None):
    """Scale bar in data units (ft), lower-left at (x0, y0)."""
    ax.plot([x0, x0 + feet], [y0, y0], color=INK, lw=2.2, solid_capstyle="butt")
    for xx in (x0, x0 + feet / 2, x0 + feet):
        ax.plot([xx, xx], [y0, y0 + feet * 0.03], color=INK, lw=1)
    ax.text(x0 + feet / 2, y0 + feet * 0.06, label or f"{feet:,.0f} ft", ha="center", va="bottom", fontsize=8, color=INK)
