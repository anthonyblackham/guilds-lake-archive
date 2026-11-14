# Guild's Lake archive

An index of the historical sources behind a study of Guild's Lake, the 1905 Lewis and Clark Exposition grounds in
Portland, Oregon, and the hills that were sluiced and shovelled into the lake between 1906 and the 1920s
(the Scotch Nubbin, Westover Terraces, Balch Gulch).

This repository holds the **index**, not the archive itself: one row per source in `catalog/sources.csv`, a small
thumbnail where the rights allow, and a link to the holding institution's own copy. Full-resolution scans stay with
the archives that hold them.

| Folder | Contents |
|---|---|
| `catalog/` | `sources.csv` (the index) and its field guide |
| `thumbs/` | 640 px previews, only for public-domain and credit-line items |
| `site/` | the browsable index (generated) |
| `scripts/` | builders that regenerate the index from the research project |
| `gis/` | **historic_topography.gpkg**: contours and spot heights traced from the historic surveys, one layer per survey, CC BY 4.0 (see gis/README.md) |
| `stories/` | illustrated write-ups built from the archive (Lafe Pence and the Scotch Nubbin) |

Status: in progress. The catalogue covers the project photo and map catalogue, topo and survey sheets, newspapers, the UO PH037 Angelus prints and the LoC Olmsted papers (2,109 entries). Rebuild with `python scripts/build_catalog_table.py` then `python scripts/build_site.py`; open `site/index.html` through a local web server from the repo root (it loads thumbnails from `../thumbs/`).
