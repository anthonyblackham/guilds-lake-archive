r"""Build a survey's finished relief render (the hero image on its topography card) in one go, with the settings
chosen for it:

    python scripts/figures/relief_make.py <survey_id>

Runs relief_prep.py, renders the sheet in Blender twice (relief, and flat with the same light when the sheet fades
its relief at the edge), then relief_finish.py for the border. Writes topography/renders/<id>-relief.png (lossless
master) and -relief.jpg (web copy); build_pages.py shows them on the card with CAPTION.
Blender: set BLENDER or install 5.2 in the default place.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
FIG = HERE / "scripts" / "figures"
BLENDER = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")

SETTINGS = {   # survey: relief_render.py options (heights x, sun, water ...), as chosen sheet by sheet
    "huber_1902": ["--vex", "5", "--sun-alt", "30", "--water", "1"],
}
CAPTION = {    # read by build_pages.py
    "huber_1902": "The sheet in relief: Guild's Lake in 1902 at its 8 ft shore, the peninsula and the hill above "
                  "Thurman Street raised from the traced contours (heights x5).",
}


def run(*cmd):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def make(sid):
    py = [sys.executable, "-P", "-E"]
    run(*py, FIG / "relief_prep.py", sid)
    build = HERE / "build" / "relief" / sid
    out = HERE / "topography" / "renders" / f"{sid}-relief.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    relief, flat = build / "render.png", build / "render_flat.png"
    opts = SETTINGS.get(sid, [])
    run(BLENDER, "-b", "-P", FIG / "relief_render.py", "--", sid, *opts, "--out", relief)
    finish = [*py, FIG / "relief_finish.py", relief, out]
    if (build / "fade.png").exists():
        run(BLENDER, "-b", "-P", FIG / "relief_render.py", "--", sid, *opts, "--flat", "1", "--out", flat)
        finish += [f"--flat={flat}", f"--fade={build / 'fade.png'}"]
    run(*finish)


if __name__ == "__main__":
    for s in sys.argv[1:]:
        make(s)
