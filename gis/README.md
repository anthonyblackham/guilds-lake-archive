# Historic topography of Guild's Lake and the hills behind it

`historic_topography.gpkg` holds contour lines and spot heights traced from historic surveys of Guild's Lake, the
1905 Lewis and Clark Exposition grounds, and the hills to the south and west (the Scotch Nubbin, Blythswood,
Westover Terraces and Balch Gulch), from 1896 to about 1910, before and during the sluicing and filling that reshaped
them. They're traced from scans in the archives listed in the [catalogue](../catalog/sources.csv).

Licence: **CC BY 4.0** (see [LICENSE](LICENSE)). Credit: *Guild's Lake Archive, historic topography traces (Anthony
Blackham)*. The scans the lines were traced from belong to their archives; see each survey's `source_id` in the catalogue.

## Coordinate system and heights
- **CRS:** EPSG:2913, NAD83(HARN) / Oregon North, international feet.
- **Heights:** every feature has `elev_printed` (the figure on the sheet) and `elev_city`, the elevation on the
  **City of Portland datum**, which is **NAVD88 minus 2.10 ft** (so a 2019 lidar value minus 2.10 compares directly).
  Corrections made for each survey are listed in the `surveys` layer (`datum_correction_ft`).

## Layers
| Layer | What |
|---|---|
| `surveys` | one footprint per survey (hull of its traced features + 100 ft) with title, date, surveyor, contour interval, datum correction, how it was positioned, fit, catalogue `source_id`, feature count |
| `usgs_1896_contours` | USGS Portland quadrangle, the Scotch Nubbin's 25 ft rings |
| `huber_1902_contours`, `huber_1902_spot_heights` | Huber & Maxwell's survey for the exposition: 1 ft contours, high-water lines, roads and fences, and ~300 lake soundings |
| `olmsted_p6_1903_contours` | Olmsted plan 6, the main grounds at 1 ft |
| `m1698_1906_contours` | City Archives M/1698, Blythswood, 10 ft |
| `m1697_westover_contours` | City Archives M/1697, Westover Terraces, 25 ft |
| `job5174_1910_contours`, `job5174_1910_spot_heights` | Lewis-Wiley Co., Balch Gulch north of Thurman St, May 1910 |
| `forestry_ext_c1910_spot_heights`, `forestry_ext_c1910_contours` | Parks Dept "Contours along Forestry Extension": pencilled creek marks, stadia shots, and a sample of Russell & Blyth's contours |

## Fields (all feature layers)
`survey_id`, `elev_printed`, `elev_city`, `kind`, `method`, `flag`, `source_id`, `note`.

- **`method`** says how each line was made: `hand` (traced by hand), `raster_scribe` (the QGIS Raster Scribe
  plugin, then checked), `auto` (machine traced), `mixed` (machine pieces joined and edited by hand), `unknown`.
  **M/1698 mixes two methods**: 11 lines traced by hand and 44 with Raster Scribe, from a test of the two.
- **`flag`** marks known problems; blank means none known.

## Survey notes and known problems
- **USGS 1896:** a small summit on a 1:62,500 sheet, generalised by 100-250 ft. Traced on J. C. Olmsted's copy of the
  quadrangle and re-anchored so the knoll sits on today's remnant knob (+308 ft E, +57 ft N of the traced position),
  where its summit, the valley behind it and the 1907 newspaper picture all agree. Rings below 350 ft are flagged.
- **Huber & Maxwell 1902:** shifted +20 ft E, -10 ft N to fit Olmsted plan 6 where they overlap. The lake figures are
  **depths** below a shore at 8 ft (`elev_city` = 8 - depth); a few soundings had their decimal points restored.
  The Average High Water and 1894 high-water lines are given 25 and 30 ft; the "6 ft level" line has no height.
- **M/1698 and M/1697:** both sheets read 3.4 ft above the city datum and are corrected by -3.4 ft.
- **Job 5174:** five contours were extrapolated by the tracer to follow the original stream (flagged).
- **Forestry extension:** the stadia shots carry their own benchmark and read about 15 ft high against the city
  datum; `elev_city` = printed - 15. One Russell & Blyth 300 ft line reads ~15 ft below today's ground (flagged).
- Positions are as good as each sheet's georeference: see `fit` in `surveys` (a few feet on the large-scale sheets,
  hundreds of feet on the USGS quadrangle).

## Rebuilding
`python scripts/export_topography.py` regenerates the file from the project's working layers.
