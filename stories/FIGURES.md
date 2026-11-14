# Story figures: the standard

Figures are fixed files made for a story. They are not screenshots of the live 3D viewer, which keeps changing.
Each one is made by a script in `scripts/figures/` that reads the research project read-only, so it can be remade.

## Files
- JPEG, **1600 px wide** (portrait photos may be narrower), quality 88, in `stories/<story>/figures/`.
- Named `ch<chapter>-<short-slug>.jpg`. Numbers are not in the file names: the story builder numbers figures
  in the order they appear, and the text refers to them as `Figure {ch5-route-map}`.

## Captions
Every caption has three parts:
1. **Figure number**, then what it shows, in one or two plain sentences.
2. What the reader should notice, when it isn't obvious.
3. The source: for a scan, the paper or archive, date and page, with a link to its catalogue entry; for a figure made
   for the story, "Made for this story from ..." naming the sources it is built on. Say where a line is inferred
   rather than drawn from a source.

## Colours (same meaning in every figure)
| Colour | Hex | Means |
|---|---|---|
| Red | `#b3261e` | ground cut away at the time (historic cut faces) |
| Blue | `#2f6fb0` | ground cut away since (comparisons with the model) |
| Orange | `#d9822b` | flumes, ditches, pipelines |
| Grey-blue | `#6f9fb8` | historic water (the 1902 lake) |
| Brown-grey | `#8a7a62` | historic buildings |
| Ink | `#2a241c` | labels, structures (bridges), markers |

## Maps
- Today's ground as a soft grey hillshade (2019 lidar) under everything, so readers can find their way.
- North arrow and a scale bar in feet on every map; grid is Oregon State Plane North (EPSG:2913).
- Labels in plain words on a pale box; italics for areas and water, bold for the subject of the figure.
- A small grey note in a corner saying what the base layers are.

## Scans
- Shown as printed: cropped to the picture, not retouched. Annotated versions are separate figures.
