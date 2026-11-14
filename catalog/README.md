# catalog/sources.csv: fields

One row per work (a photograph, a map sheet, a newspaper article, a letter).

| Field | Meaning |
|---|---|
| `id` | Stable identifier: collection prefix + the archive's own id, e.g. `ohs-bb000403`, `loc-stereo-2022654005` |
| `title` | Title as the archive gives it (or a descriptive title) |
| `date` | Date or date range as known |
| `creator` | Photographer, surveyor, publisher |
| `kind` | photo, map, document, letter, ephemera, publication, periodical, clipping, postcard, drawing, item |
| `collection` | Holding collection / series |
| `archive_id` | The archive's identifier |
| `url_original` | The holding archive's page for the item (blank where none is known yet) |
| `url_mirror` | Optional mirror (e.g. Internet Archive) |
| `rights` | `pd` public domain / no known restrictions; `credit` free to show with the credit line; `permission` the archive requires permission to reproduce; `unknown` |
| `credit` | Credit line to show with the item |
| `thumb` | Path to the thumbnail in `thumbs/`, only for `pd` and `credit` items |
| `place` | Place or township/range |
| `topics` | Subject terms |
| `used_in` | Stories, GIS layers or model pieces that rely on the item (to be filled) |
| `notes_ref` | Pointer into the research notes (to be filled) |
| `description` | Short description (first 500 characters) |
| `local_path` | Path in the research project's `sources/` folder (for rebuilding; not shown on the site) |

**Rights rule:** a thumbnail is published only for `pd` and `credit` items. `permission` items (Oregon Historical
Society, UW Special Collections) and `unknown` items are listed with a link and credit only.
