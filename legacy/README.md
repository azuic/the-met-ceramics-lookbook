# The 2019 lookbook

The original site, kept whole as the reference dataset and as the thing the
rebuild is measured against. It is archived, not maintained.

`index.html` still runs, but every tile is blank: it drew its imagery from
`d1tutlfztia4ba.cloudfront.net`, and that distribution lapsed. Losing one
service that the project did not own is what killed it, and is the reason the
rebuild owns every byte it serves.

| File | What it holds |
|---|---|
| `index.html` | the 2019 entry point, verbatim |
| `style.css`, `js/scrollMonitor.js` | its stylesheet and scroll library |
| `categorized_ceramics.js` | 9,530 object IDs grouped by material |
| `grouped_types.js`, `medium.js` | the 2019 classification tables |
| `objects.js` | per-object origin and surface strings |

These tables are the origin of `pipeline/data/legacy_2019.json`, the snapshot
`pipeline/validate.py` checks the reconstructed heuristic against. The gate
treats that snapshot as ground truth, so do not edit these files: regenerating
the snapshot from an edited table would move the thing being measured.
