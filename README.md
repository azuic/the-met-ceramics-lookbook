# The Met Ceramics Lookbook

Every public-domain ceramic object in the Metropolitan Museum of Art, as one
continuous field of colour.

Each object appears as a tight crop of its own glazed surface, not as a
catalogue photograph of a vase. The default order is hue-major, so the
collection reads as one long sweep from cobalt through turquoise, celadon,
copper green, terracotta, iron red, ochre, lustre, cream and manganese. You can
filter it, re-lattice it, zoom out until the whole collection fits on one
screen, and click any tile to open that object's catalogue card.

**[azuic.github.io/the-met-ceramics-lookbook](https://azuic.github.io/the-met-ceramics-lookbook/)**
· [mirror on Vercel](https://the-met-ceramics-lookbook.vercel.app)

## The numbers

51,521 objects were scanned. Of those, 44,354 passed crop quality control and
are in the field, split between 37,541 photographed in colour and 6,813 that
never were. The monochrome set is a view of its own, not a filter you apply
alongside the others.

## What is here

| | |
|---|---|
| `index.html`, `css/`, `js/` | the site. No build step, no package manager |
| `data/` | what the browser loads: `grid.bin`, 101 atlas sheets, 44 detail shards |
| `pipeline/` | the Python that fetches, crops, measures and packs `data/`. Has its own README |
| `DESIGN_BRIEF.md` | the product and interface brief |
| `PLAN.md` | the engineering plan, stage by stage |
| `legacy/` | the 2019 original this rebuilds |

GSAP is the only third-party code. It is vendored into `js/vendor/` instead of
hotlinked, and it drives the drag-to-tear on the receipt. Type comes from
Google Fonts. Everything else here is hand-written and served from this repo.

## Running it

Any static server, from the repo root:

```
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Opening the file directly will not work,
because the payload is fetched over HTTP.

## Deploying

`master` is the production branch for both surfaces. Pushing it rebuilds GitHub
Pages and deploys Vercel production. `.nojekyll` stops Pages running the Jekyll
pass over the atlas sheets.

## Provenance

Images and metadata come from the Metropolitan Museum of Art's Open Access
collection, and every object shown is public domain. The site rebuilds a 2019
project that stopped working once the CDN it relied on lapsed. This version
owns every byte it serves.
