r"""Export the project's traced historic topography as one public GeoPackage: gis/historic_topography.gpkg.

    python scripts/export_topography.py

Reads the research project (lewis-clark-1905) read-only; the user's QGIS layers there stay the working copies, this is
an export. One layer per survey (contours, spot heights) with a common schema, plus `surveys`, an index of each
survey's footprint and metadata. CRS EPSG:2913 (NAD83(HARN) / Oregon North, international feet).

Common fields
  survey_id     key into `surveys`
  elev_printed  the figure as it appears on the sheet (ft); for Huber & Maxwell lake soundings, the depth
  elev_city     elevation on the City of Portland datum (= NAVD88 - 2.10 ft), after the survey's correction
  kind          contour | index | spot | sounding | high_water | road | fence | stadia ...
  method        hand (traced by hand) | raster_scribe (QGIS Raster Scribe plugin, checked) | auto (machine traced)
                | mixed (auto pieces joined/edited by hand) | unknown
  flag          known problems, blank if none
  source_id     the sheet's entry in the Guild's Lake Archive catalogue (catalog/sources.csv)
  note          free text
"""
import sys
from pathlib import Path

import numpy as np
from pyogrio.raw import read, write
from shapely import from_wkb, to_wkb, union_all
from shapely.affinity import translate

HERE = Path(__file__).resolve().parent.parent
P = HERE.parent / "lewis-clark-1905"
OUT = HERE / "gis" / "historic_topography.gpkg"
EXPO = P / "qgis" / "expo-model.gpkg"
TER = P / "qgis" / "terrain"
CRS = "EPSG:2913"
FIELDS = ["survey_id", "elev_printed", "elev_city", "kind", "method", "flag", "source_id", "note"]

SURVEYS = [  # survey_id, title, date, surveyor, interval, datum_correction_ft, position, fit, source_id, catalogue note
    ("usgs_1896", "USGS Portland quadrangle (1:62,500), the Scotch Nubbin", "surveyed 1896", "U.S. Geological Survey (E. C. Barnard)",
     "25 ft", 0.0, "re-anchored on today's remnant knob: +308 E, +57 N from the traced position",
     "traced on J. C. Olmsted's copy (Olmsted job 2640 plan 6), shifted +500 E, +460 N to the Willamette Heights road and Thurman St, then +308 E, +57 N; a small summit at 1:62,500, generalised by 100-250 ft",
     "map-00058-02640-6-front-jpg6366319132355342"),
    ("huber_1902", "Map of Willamette Heights and Guild's Lake (Huber & Maxwell survey)", "August 1902", "Huber & Maxwell, Engineers",
     "1 ft (labelled every 5); lake soundings", 0.0, "+20 E, -10 N (fit to Olmsted plan 6 in their overlap)",
     "georeferenced in QGIS on street corners; shift fitted against plan 6 (mean |dz| 2.07 -> 1.45 ft)",
     "map-job02399-plan09-huber-maxwell-survey-blu"),
    ("olmsted_p6_1903", "Topographic survey of the main grounds (Olmsted job 2399 plan 6, sheets 1-2 stitched)", "c. 1903",
     "for Olmsted Brothers", "1 ft (index every 5)", 0.0, "as georeferenced", "14 street-corner GCPs, RMS 4.4 ft",
     "map-job02399-plan06-topographic-survey-stitc"),
    ("m1698_1906", "Contour map of Blytheswood Park, part of the Danford Balch DLC (City Archives M/1698)", "30 November 1906",
     "for Russell & Blyth", "10 ft (index every 50)", -3.4, "as georeferenced",
     "sheet reads 3.4 ft above the city datum (index-line fit against the 2019 lidar)", "pdx-archives-m1698"),
    ("m1697_westover", "Contour Map of Parts of Westover Terraces and Vicinity (City Archives M/1697)",
     "traced 22 March 1917 from surveys of c. 1906-10", "Dept of Public Works (Herner tracing)", "25 ft", -3.4,
     "as georeferenced (stitched from photographs)", "read 3.4 ft lower to match M/1698", "pdx-archives-m1697"),
    ("job5174_1910", "Lewis-Wiley Company: Balch's Gulch, north of Thurman Street (Olmsted job 5174 plan 1)", "10 May 1910",
     "Lewis-Wiley Co.", "contours ~5 ft, spot heights", 0.0, "as georeferenced", "matches Olmsted plan 6 within ~2 ft (median)",
     "map-job05174-plan01-north-of-thurman-sheet-b"),
    ("forestry_ext_c1910", "Contours along Forestry Extension, taken from map of Russell & Blythe (Dept of Parks sheet 2)",
     "c. 1909-10", "Dept of Parks, after Russell & Blyth", "contours from Russell & Blyth; pencilled creek marks and stadia shots",
     0.0, "thin plate spline warp", "TPS on street and section GCPs, RMS 7.7 ft (leave-one-out median 13.6 ft); "
     "stadia shots read ~15 ft high and are corrected by -15 ft", "pdx-archives-forestry-extension"),
]


def layer(path, name):
    m, _, g, d = read(path, layer=name)
    f = dict(zip(m["fields"], d))
    return [(q, {k: v[i] for k, v in f.items()}) for i, q in enumerate(from_wkb(g)) if q is not None]


def num(v):
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def s(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) or str(v) in ("None", "nan") else str(v)


def put(rows, name, geom_type):
    if not rows:
        return
    geoms = np.array([to_wkb(r[0]) for r in rows], dtype=object)
    cols = [np.array([r[1].get(k) for r in rows], dtype=object if k not in ("elev_printed", "elev_city") else float)
            for k in FIELDS]
    write(OUT, geoms, cols, fields=FIELDS, layer=name, driver="GPKG", geometry_type=geom_type, crs=CRS,
          append=OUT.exists() and name != "surveys", promote_to_multi=False)
    print(f"{name}: {len(rows)}")


def rec(sid, ep, ec, kind, method, flag="", note=""):
    src = next(x[8] for x in SURVEYS if x[0] == sid)
    return {"survey_id": sid, "elev_printed": ep, "elev_city": ec, "kind": kind, "method": method, "flag": flag,
            "source_id": src, "note": note}


def main():
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    out = {}
    # USGS 1896 Nubbin rings (user's trace), re-anchored on the knob
    rows = []
    for q, a in layer(TER / "scotch_nubbin_usgs1896.gpkg", "nubbin_usgs_contours_hand"):
        e = num(a["elev"])
        flag = "" if e is None or e >= 350 else "below 350 ft: traced running north along the Willamette Heights slope; placement doubtful after the re-anchoring"
        rows.append((translate(q, 308, 57), rec("usgs_1896", e, e, "contour", "hand", flag)))
    out["usgs_1896_contours"] = (rows, "LineString")
    # Huber & Maxwell 1902
    rows = []
    for q, a in layer(EXPO, "huber_contours_hand"):
        e, k = num(a["elev"]), s(a["kind"])
        kind = {"topo": "contour", "Average H.W.": "high_water", "H.W. 1894": "high_water", "6 FT Level": "level_line"}.get(k, k.lower())
        note = {"Average H.W.": "Average high water, given 25 ft", "H.W. 1894": "high water of 1894, given 30 ft",
                "6 FT Level": "'6 ft level' line, height unknown"}.get(k, "")
        rows.append((translate(q, 20, -10), rec("huber_1902", e, e, kind, "hand", s(a["flag"]), note)))
    out["huber_1902_contours"] = (rows, "LineString")
    rows = []
    for q, a in layer(EXPO, "huber_spot_heights"):
        v, k = num(a["value"]), s(a["kind"])
        if k == "bed":
            rows.append((translate(q, 20, -10), rec("huber_1902", v, None if v is None else round(8 - v, 2), "sounding", "hand",
                                                    s(a["note"]) if s(a["note"]) else "", "depth below the 8 ft shore; elev_city = 8 - depth")))
        else:
            rows.append((translate(q, 20, -10), rec("huber_1902", v, v, "spot", "hand", "", s(a["note"]))))
    out["huber_1902_spot_heights"] = (rows, "Point")
    # Olmsted plan 6
    rows = []
    for q, a in layer(EXPO, "p6_contours_joined"):
        e = num(a["elev"])
        method = {"user": "hand", "auto": "auto", "mixed": "mixed"}.get(s(a["status"]), "unknown")
        rows.append((q, rec("olmsted_p6_1903", e, e, "contour", method,
                            "" if method != "unknown" else "elevation not confirmed")))
    out["olmsted_p6_1903_contours"] = (rows, "LineString")
    # M/1698 (hand + Raster Scribe)
    rows = []
    for q, a in layer(EXPO, "m1698_contours_combined"):
        e = num(a["elev"])
        method = {"hand": "hand", "scribe": "raster_scribe"}.get(s(a["source"]), "unknown")
        rows.append((q, rec("m1698_1906", e, None if e is None else round(e - 3.4, 1),
                            "index" if s(a["kind"]) == "index" else "contour", method)))
    out["m1698_1906_contours"] = (rows, "LineString")
    # M/1697 Westover (the user's hand trace)
    rows = []
    for q, a in layer(EXPO, "m1697_contours_hand"):
        e = num(a["elev"])
        rows.append((q, rec("m1697_westover", e, None if e is None else round(e - 3.4, 1), "contour", "hand", s(a["flag"]))))
    out["m1697_westover_contours"] = (rows, "LineString")
    # job 5174
    rows = []
    for q, a in layer(TER / "job5174_gulch_trace.gpkg", "job5174_contours_hand"):
        e = num(a["elev"])
        rows.append((q, rec("job5174_1910", e, e, "contour", "hand", s(a["flag"]),
                            "extrapolated by the tracer to follow the original stream" if s(a["flag"]) == "extrapolated" else "")))
    out["job5174_1910_contours"] = (rows, "LineString")
    rows = [(q, rec("job5174_1910", num(a["elev"]), num(a["elev"]), "spot", "hand", "", s(a["note"])))
            for q, a in layer(TER / "job5174_gulch_trace.gpkg", "job5174_spot_heights_hand")]
    out["job5174_1910_spot_heights"] = (rows, "Point")
    # forestry extension sheet: creek marks, stadia shots, Russell & Blyth contours
    rows = []
    for q, a in layer(TER / "forestry_creek_spot_heights.gpkg", "forestry_creek_spot_heights"):
        v, fl = num(a["sheet_ft"]), s(a["flag"])
        if fl == "stadia":
            rows.append((q, rec("forestry_ext_c1910", v, None if v is None else round(v - 15, 1), "stadia", "hand",
                                "stadia shots read ~15 ft high (own benchmark); elev_city = printed - 15")))
        else:
            rows.append((q, rec("forestry_ext_c1910", v, v, "creek_mark", "hand", fl, s(a["note"]))))
    out["forestry_ext_c1910_spot_heights"] = (rows, "Point")
    rows = []
    for q, a in layer(TER / "pence_flumes_1906_trace.gpkg", "blyth_topo_trace"):
        e = num(a["elevation"])
        odd = e == 300 and q.bounds[1] > 688500
        rows.append((q, rec("forestry_ext_c1910", e, e, "contour", "hand",
                            "reads ~15 ft below today's ground: fill or a misread label" if odd else "",
                            "Russell & Blyth contour (sample traced to check the stadia datum)")))
    out["forestry_ext_c1910_contours"] = (rows, "LineString")

    # the index: one footprint per survey (hull of its traced features + 100 ft)
    idx = []
    for sid, title, date, who, interval, corr, pos, fit, src in SURVEYS:
        geoms = [g for k, (rows, _) in out.items() if k.startswith(sid) for g, _ in rows]
        idx.append((union_all(geoms).convex_hull.buffer(100), (sid, title, date, who, interval, corr, pos, fit, src,
                                                               sum(1 for k, (r, _) in out.items() if k.startswith(sid) for _ in r))))
    ifields = ["survey_id", "title", "date", "surveyor", "interval", "datum_correction_ft", "position", "fit", "source_id", "features"]
    write(OUT, np.array([to_wkb(g) for g, _ in idx], dtype=object),
          [np.array([v[i] for _, v in idx], dtype=object if i not in (5, 9) else float) for i in range(len(ifields))],
          fields=ifields, layer="surveys", driver="GPKG", geometry_type="Polygon", crs=CRS)
    print("surveys:", len(idx))
    for name, (rows, gt) in out.items():
        put(rows, name, gt)
    print("wrote", OUT.relative_to(HERE), f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
