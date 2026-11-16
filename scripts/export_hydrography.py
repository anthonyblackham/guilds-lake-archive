r"""Build gis/historic_hydrography.gpkg: the historic water of Guild's Lake and Balch Creek in one standard form.

    python scripts/export_hydrography.py

Reads the research project's layers read-only (lewis-clark-1905/qgis/...) and the USGS NHD extract
(lewis-clark-1905/data/nhd/balch_creek_nhd.geojson). Every layer has the same fields:

  name           what it is called ("Guild's Lake", "Balch Creek", "Pence Company Canal")
  kind           lake | creek | sewer | flume | spoil flume | canal | ditch | tunnel
  status         existing (as drawn at that date) | built | planned | abandoned | piped (buried in a pipe today) | open (today)
  date, date_to  the date the feature shows (text: "1852", "Aug 1902", "c. 1910"); date_to for a span
  level_ft_city  water level on the City of Portland datum (NAVD88 - 2.10 ft), where known
  method         hand (traced from the source) | derived (computed, see note) | modern data
  source         where it came from, in words
  source_id      the archive catalogue id of the source, where there is one (site/#<id>)
  flag           uncertainty, if any
  note           context

Layers: lakes (polygons), streams (lines), sewers (lines), water_works (flumes, canals, ditches; lines). Add a new
trace by adding a reader below; the fields stay the same.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from pyogrio import list_layers
from pyogrio.raw import read, write
from shapely import from_wkb, to_wkb
from shapely.affinity import translate
from shapely.geometry import LineString, MultiPolygon, Polygon, shape
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parents[1]
P = HERE.parent / "lewis-clark-1905"
Q = P / "qgis"
T = Q / "terrain"
OUT = HERE / "gis" / "historic_hydrography.gpkg"
TOPO = HERE / "gis" / "historic_topography.gpkg"
CRS = "EPSG:2913"
FIELDS = ["name", "kind", "status", "date", "date_to", "level_ft_city", "method", "source", "source_id", "flag", "note"]
HUBER_SHIFT = (20, -10)          # the same shift the exported Huber contours carry (plan 9 re-fit)


def layer(path, name):
    m, _, g, d = read(path, layer=name)
    f = dict(zip(m["fields"], d))
    return [(q, {k: v[i] for k, v in f.items()}) for i, q in enumerate(from_wkb(g)) if q is not None]


def rec(name, kind, status, date, source, source_id="", method="hand", date_to="", level=None, flag="", note=""):
    return {"name": name, "kind": kind, "status": status, "date": date, "date_to": date_to,
            "level_ft_city": level, "method": method, "source": source, "source_id": source_id, "flag": flag,
            "note": note}


def fair_time_lake(level=13.0, cell=10.0):
    """The lake at fair time: everything below `level` on the Huber & Maxwell 1902 ground (its traced contours and
    soundings, from historic_topography.gpkg), connected to the 1902 lake."""
    sys.path.insert(0, str(HERE / "scripts" / "figures"))
    import topo_cards as TC
    feats = []
    for L, _ in list_layers(TOPO):
        if L.startswith("huber_1902"):
            m, _, g, d = read(TOPO, layer=L)
            f = dict(zip(m["fields"], d))
            for q, e, k in zip(from_wkb(g), f["elev_city"], f["kind"]):
                if e is not None and np.isfinite(e) and k in ("contour", "sounding", "spot"):
                    feats.append((q, float(e)))
    lake02 = translate(layer(Q / "expo-model.gpkg", "huber_1902_lakebed_refit")[0][0], *HUBER_SHIFT)
    x0, y0, x1, y1 = lake02.buffer(1500).bounds
    gx, gy = np.meshgrid(np.arange(x0, x1, cell), np.arange(y1, y0, -cell))
    z = TC.own_surface(feats, gx.astype(np.float32), gy.astype(np.float32), near_ft=400.0)
    wet = (np.nan_to_num(z, nan=99) < level).astype(np.uint8)
    seed = np.zeros_like(wet)
    lk = np.array(lake02.exterior.coords)
    cv2.fillPoly(seed, [np.c_[(lk[:, 0] - x0) / cell, (y1 - lk[:, 1]) / cell].round().astype(np.int32)], 1)
    wet = np.maximum(wet, seed)
    n, lab = cv2.connectedComponents(wet)
    keep = np.isin(lab, np.unique(lab[(seed > 0) & (wet > 0)]))
    keep = cv2.morphologyEx(keep.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, hier = cv2.findContours(keep, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for i, c in enumerate(cs):
        if hier[0][i][3] != -1 or len(c) < 4:
            continue
        ring = [(x0 + (p[0][0] + 0.5) * cell, y1 - (p[0][1] + 0.5) * cell) for p in c]
        holes = [[(x0 + (p[0][0] + 0.5) * cell, y1 - (p[0][1] + 0.5) * cell) for p in cs[j]]
                 for j in range(len(cs)) if hier[0][j][3] == i and len(cs[j]) >= 4]
        pg = Polygon(ring, holes).buffer(0)
        if pg.area > 43560:
            polys.append(pg)
    return unary_union(polys).simplify(4)


def city_trunk_sewer(trace, near_ft=30.0):
    """The Balch Gulch trunk sewer from the City of Portland's storm pipe records (BES, Utilities_Sewer layer 7,
    extract in lewis-clark-1905/data/city_sewer/layer7.geojson): the large mains (48 in and up) along the user's
    rough trace of the line on the Port's 1924 reclamation map, grouped by install date and status."""
    import collections, datetime, json
    j = json.loads((P / "data" / "city_sewer" / "layer7.geojson").read_text())
    grp = collections.defaultdict(list)
    for ft in j["features"]:
        pr, q = ft["properties"], shape(ft["geometry"])
        if not pr.get("PIPESIZE") or pr["PIPESIZE"] < 48:
            continue
        if trace.buffer(near_ft).intersection(q).length < 0.8 * q.length:   # must run along the line, not cross it
            continue
        yr = (datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=pr["Install_Date"])).year             if pr.get("Install_Date") is not None else None
        ab = (datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=pr["Date_Abandoned"])).year             if pr.get("Date_Abandoned") else None
        mat = (pr.get("MATERIAL") or "").strip()
        grp[(yr, ab, pr["PIPESIZE"], mat)].append(q)
    mats = {"MONO": "monolithic concrete", "CSP": "corrugated steel", "CIPP": "cured-in-place liner",
            "RCP": "reinforced concrete", "HDPE": "HDPE"}
    src = ("City of Portland Bureau of Environmental Services, storm pipe records (portlandmaps.com "
           "Public/Utilities_Sewer, layer 7, downloaded 2026-11-15); selected along the line on the Port of Portland's "
           "Guilds Lake reclamation map, 31 May 1924 (City Archives M/2790)")
    rows = []
    for (yr, ab, size, mat), qs in sorted(grp.items(), key=lambda r: (r[0][0] or 9999)):
        desc = f"{size} in {mats.get(mat, mat.lower() or 'material not recorded')}"
        if yr == 1921:
            rows.append((unary_union(qs), rec("Balch Gulch trunk sewer", "sewer", "abandoned" if ab else "built",
                         "1921", date_to=str(ab) if ab else "", source=src, method="modern data",
                         note=f"{desc}, installed 1921 by the city's record" + (f", abandoned {ab}" if ab else
                         ", still in service") + ". Built straight across the open lake bed to carry Balch Creek; "
                         "the Port's fill heaved and broke it in 1925 ('Fill Damages Sewer', Oregonian, 20 Dec 1925, "
                         "p 33). Construction photos: City Archives A2001-008")))
        else:
            rows.append((unary_union(qs), rec("Balch Gulch trunk sewer (later pipe)", "sewer",
                         "abandoned" if ab else "built", str(yr) if yr else "", date_to=str(ab) if ab else "",
                         source=src, method="modern data",
                         flag="" if yr else "install date not recorded",
                         note=f"{desc} on the line of the 1921 trunk sewer" + (f", installed {yr}" if yr else ""))))
    return rows


def main():
    out = {}
    # ---------------------------------------------------------------- lakes
    rows = []
    gl = [q for q, _ in layer(Q / "lewis-and-clark-exposition.gpkg", "guilds-lake")]
    rows.append((unary_union(gl), rec("Guild's Lake", "lake", "existing", "1852",
                 "General Land Office meander survey (Butler Ives), 1938 re-plot (M/1542), traced by the user",
                 "map-m1542-meanders-of-guilds-lake-1852",
                 note="the lake as the 1852 surveyors walked its edge; about the 25 ft / average-high-water ring")))
    lake02 = translate(layer(Q / "expo-model.gpkg", "huber_1902_lakebed_refit")[0][0], *HUBER_SHIFT)
    rows.append((lake02, rec("Guild's Lake", "lake", "existing", "Aug 1902",
                 "Huber & Maxwell survey (Olmsted job 2399 plan 9), the user's outline re-fitted to the 14-corner "
                 "georeference", "map-job02399-plan09-huber-maxwell-survey-blu", level=8.0,
                 note="low water before the fair; 8 ft = the shore the soundings are measured from")))
    rows.append((fair_time_lake(), rec("Guild's Lake", "lake", "existing", "1905", "derived from the Huber & Maxwell "
                 "1902 contours and soundings; level from the Oregon Daily Journal (8 Mar 1907, p 5: 'eight feet of "
                 "water during the exposition') and Olmsted's planned El. 12", "map-job02399-plan09-huber-maxwell-"
                 "survey-blu", method="derived", level=13.0,
                 flag="derived: the 13 ft contour of the 1902 ground; only as complete as Huber's traced lines",
                 note="the fair-time lake (the shore raised by damming and dredging)")))
    out["lakes"] = (rows, "MultiPolygon")
    # ---------------------------------------------------------------- streams
    rows = []
    cl = sorted(layer(T / "balch_gulch_prefill_trace.gpkg", "gulch_creek_centerline"), key=lambda r: -r[0].length)
    rows.append((cl[0][0], rec("Balch Creek", "creek", "existing", "c. 1910",
                 "Contours along Forestry Extension (Russell & Blyth, Dept of Parks sheet 2): the creek traced by the "
                 "user", "pdx-archives-forestry-extension",
                 note="the open creek down Balch Gulch to the lake, before the gulch was filled")))
    if len(cl) > 1:
        rows.append((cl[1][0], rec("Balch Creek", "creek", "existing", "1896",
                     "USGS Portland quadrangle (Olmsted job 2640 copy): the creek traced by the user", "",
                     flag="the sheet's contours sit 40-90 ft low along the creek; position only")))
    import json
    nhd = json.loads((P / "data" / "nhd" / "balch_creek_nhd.geojson").read_text())
    by = {460: [], 428: []}
    for f in nhd["features"]:
        by.setdefault(f["properties"]["ftype"], []).append(shape(f["geometry"]))
    for ft, status, note in ((460, "open", "open channel today"),
                             (428, "piped", "in a pipe today: the conduit that carries the creek under the filled "
                                            "gulch and the industrial district")):
        if by.get(ft):
            rows.append((unary_union(by[ft]), rec("Balch Creek", "creek", status, "today",
                         "USGS National Hydrography Dataset, flowlines named Balch Creek (downloaded 2026-11-15)",
                         method="modern data", note=note)))
    out["streams"] = (rows, "MultiLineString")
    # ---------------------------------------------------------------- water works
    rows = []
    for q, a in layer(Q / "expo-model.gpkg", "pence_canal_trace_1906_hand_tps"):
        rows.append((q, rec(str(a["name"]), "flume" if "Flume" in str(a["name"]) else "canal", "planned", "1906",
                     "Map showing the general course of the Pence Company High Line Flume and Pence Company Canal "
                     "(1906), traced by the user and moved onto today's ground by 33 SAIL corners (thin-plate)",
                     "pdx-archives-a2009-009-3473",
                     note="the scheme as mapped; far more than was built (about 26 miles built against 35 claimed)")))
    sewers, sewer_trace, lake_rows = [], None, []
    for q, a in layer(T / "pence_flumes_1906_trace.gpkg", "flume_lines"):
        lake_name = str(a.get("name") or "")
        if any(w in lake_name.lower() for w in ("kittridge", "kittredge", "doane")):   # lake outlines go to `lakes`
            lake_rows.append((q, lake_name))
            continue
        if str(a.get("kind")).strip().lower() == "sewer":     # the user's rough trace selects the city's pipes
            sewer_trace = q
            continue
        # the user's trace of the water works drawn on the Forestry Extension sheet: kind, name and note as traced
        val = lambda k: "" if str(a.get(k)) in ("None", "nan") else str(a.get(k) or "").strip()
        nt, kd, nm = val("note"), val("kind").lower(), val("name")
        if "spoil" in nt.lower():
            kd = "spoil flume"
        flag = ""
        if not kd:
            kd, flag = "flume", "kind not given on the trace; taken as a flume"
        if "?" in nt:
            flag = (flag + "; " if flag else "") + "identification uncertain (" + nt + ")"
        pence = any(w in nt.lower() for w in ("pence", "nubbin"))
        if not nm or nm.lower() in (kd, "flume", "ditch", "tunnel"):
            nm = ("Pence " if pence else "") + kd
            nm = nm[0].upper() + nm[1:]
        rows.append((q, rec(nm, kd, "built", "1906-07" if pence else "c. 1910",
                     "Contours along Forestry Extension (Russell & Blyth, Dept of Parks sheet 2): drawn on the sheet, "
                     "traced by the user", "pdx-archives-forestry-extension", flag=flag,
                     note=nt if nt else ("as drawn on the sheet" if not pence else ""))))
    for q, a in layer(T / "scotch_nubbin_1907_photo.gpkg", "oregonian_1907_cut_and_flumes"):
        if str(a["kind"]) != "spoil flume":
            continue
        rows.append((q, rec("Pence spoil flume", "spoil flume", "built", "Mar 1907",
                     "Morning Oregonian, 11 Mar 1907, p 12 (the flume photograph), the user's linework placed on "
                     "today's ground", "news-oregonian-1907-03-11-p12", flag="placed from a photograph",
                     note=str(a["name"]).replace("_", " "))))
    out["water_works"] = (rows, "MultiLineString")
    if sewer_trace is not None:
        sewers += city_trunk_sewer(sewer_trace)
    out["sewers"] = (sewers, "MultiLineString")
    # Kittredge and Doane lakes: closed outlines in the same trace layer, made polygons, one feature per lake
    LAKE_SRC = {
        "kittredge": ("Kittredge Lake", "Dec 1922", "The Port of Portland, Topographic Map of Guild's Lake District, sheet "
                      "2 (surveyed Dec 1922), shoreline traced by the user", "map-pop-topographic-map-of-guilds-lake-distr",
                      "just before the Port's dredge fill, which took it in from 1923"),
        "doane": ("Doane Lake", "c. 1906-10", "Multnomah County survey G8/15, Doane's Lake and the Willamette River "
                  "(undated; after the SP&S bridge, c. 1906-08), shoreline traced by the user", "multco-g8-15",
                  "the third bottomland lake, north-west of Kittredge Lake toward Linnton"),
    }
    grouped = {}
    for q, nm in lake_rows:
        key = "doane" if "doane" in nm.lower() else "kittredge"
        pg = Polygon(q.coords).buffer(0) if q.geom_type == "LineString" else q
        grouped.setdefault(key, []).append(pg)
    lake_list = list(out["lakes"][0])
    for key, pgs in grouped.items():
        name, date, source, sid, note = LAKE_SRC[key]
        lake_list.append((unary_union(pgs), rec(name, "lake", "existing", date, source, sid, note=note)))
    out["lakes"] = (lake_list, "MultiPolygon")
    # ---------------------------------------------------------------- write
    if OUT.exists():
        OUT.unlink()
    for name, (rows, gtype) in out.items():
        geoms = []
        for q, _ in rows:
            if gtype == "MultiPolygon" and isinstance(q, Polygon):
                q = MultiPolygon([q])
            elif gtype == "MultiLineString" and isinstance(q, LineString):
                from shapely.geometry import MultiLineString
                q = MultiLineString([q])
            geoms.append(to_wkb(q))
        fields = {k: np.array([r[k] if r[k] is not None else (np.nan if k == "level_ft_city" else "")
                               for _, r in rows], dtype=float if k == "level_ft_city" else object) for k in FIELDS}
        write(OUT, np.array(geoms, dtype=object), [fields[k] for k in FIELDS], FIELDS, layer=name, driver="GPKG",
              crs=CRS, geometry_type=gtype, append=OUT.exists())
        print(f"{name}: {len(rows)}")
    print("wrote", OUT.relative_to(HERE), f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
