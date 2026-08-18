# The Met Ceramics Lookbook

Every public-domain ceramic object in the Metropolitan Museum of Art, as one
continuous field of colour.

Each object appears as a tight crop of its own glazed surface rather than as a
catalogue photograph of a vase, and the default order is hue-major — so the
collection reads as a single sweep from cobalt through turquoise, celadon,
copper green, terracotta, iron red, ochre, lustre, cream and manganese. Filter
it, re-lattice it, zoom out until the whole collection fits on one screen, and
click any tile to open that object's catalogue card.

**[azuic.github.io/the-met-ceramics-lookbook](https://azuic.github.io/the-met-ceramics-lookbook/)**
· [mirror on Vercel](https://the-met-ceramics-lookbook.vercel.app)

## The numbers

51,521 objects scanned, of which 44,354 passed crop quality control and are in
the field: 37,541 photographed in colour and 6,813 never photographed in
colour, which are a view of their own rather than a filter alongside the rest.

## What is here

| | |
|---|---|
| `index.html`, `css/`, `js/` | the site — no build step, no package manager |
| `data/` | what the browser loads: `grid.bin`, 101 atlas sheets, 44 detail shards |
| `pipeline/` | the Python that fetches, crops, measures and packs `data/` — see its own README |
| `DESIGN_BRIEF.md` | the product and interface brief |
| `PLAN.md` | the engineering plan, stage by stage |
| `legacy/` | the 2019 original this rebuilds |

The only third-party code is GSAP, vendored into `js/vendor/` rather than
hotlinked, for the drag-to-tear on the receipt. Type is served from Google
Fonts. Everything else is hand-written and served from this repo.

## Running it

Any static server, from the repo root:

```
python3 -m http.server 8000
```

Then open <http://localhost:8000>. It has to be served over HTTP rather than
opened as a file, because the payload is fetched.

## Deploying

`master` is the production branch for both surfaces: pushing it rebuilds GitHub
Pages and deploys Vercel production. `.nojekyll` keeps Pages from running the
Jekyll pass over the atlas sheets.

## Provenance

Images and metadata come from the Metropolitan Museum of Art's Open Access
collection, and every object shown is public domain. This is a rebuild of
a 2019 project that stopped working when the CDN it depended on lapsed; the
rebuild owns every byte it serves.
