# The Met Ceramics Lookbook — Product & Interface Brief

**For:** Claude Design
**From:** engineering / `PLAN.md`
**Date:** 2026-08-10
**Status:** data pipeline ~70% run; **no interface built yet**. This document is the handoff.

---

## 0. In one paragraph

The Met Ceramics Lookbook is a single-page, zero-dependency static site that shows
**every public-domain ceramic object in the Metropolitan Museum of Art — 51,521 of
them — as one continuous field of colour.** Each object appears as a tight crop of
its own glazed surface, not as a catalogue photograph of a vase. The default order
is hue-major, so the collection reads as a single sweeping gradient from cobalt
through turquoise, celadon, copper green, terracotta, iron red, ochre, cream and
manganese. You filter it, re-lattice it, zoom out until all 51,521 objects fit on
one screen, and click any tile to open the object's catalogue card.

It is a rebuild of a 2019 project that died when its CDN lapsed. The rebuild owns
every byte it serves.

**The thesis to design toward:** *at maximum zoom-out, a museum collection is
nothing but its colour.* Everything in the interface should be in service of that
sentence.

---

## 1. What already exists

| | |
|---|---|
| **`preview.png`** | Rendered grid mockup — floating modules over a real 51k-object crop field. Generated from real MET imagery. |
| **`preview-detail.png`** | Rendered detail-view mockup — the catalogue-card treatment. Real MET record (obj. 446207). |
| **`PLAN.md`** | 790-line engineering plan. The source of every number in this brief. |
| **`pipeline/`** | Python, six stages. Stages 1–2 done, 3 running, 4–6 pending. |

Both mockups are **direction, not specification.** They prove the design language
works on real imagery. They do not resolve layout, responsive behaviour, motion,
or roughly half the functions listed in §4. That is the job.

---

## 2. Material facts you must design around

These are measured, not estimated. Several of them are design constraints with
teeth.

**Scale**

| | |
|---|---:|
| Objects with usable imagery | **51,521** |
| Rejected by crop QC (crop landed on studio backdrop) | 6.4% → ~3,300 |
| **In the grid** | **~48,200** |
| Photographed in black-and-white only | 16.4% → ~8,400 |
| Screenfuls at ~120px tiles, 1440×900 | ~584 |
| Continuous scroll to exhaust the grid | ~2h 20m |

**The collection is lopsided, and that is the point.** Greek and Roman Art is 41.6%
of everything; terracotta is 42.9% of all material labels. Under the default
hue-major sort this does *not* clump into one giant red section — it spreads as a
large warm mass across the orange-red region, which reads as a fact about the
collection's colour rather than a broken filter. **Do not design anything that
re-clumps it by department.**

**Material distribution** (drives filter list ordering and the count column)

| | | | |
|---|---:|---|---:|
| terracotta | 22,295 | clay | 2,154 |
| porcelain | 9,400 | pottery | 1,945 |
| earthenware | 5,767 | stoneware | 1,554 |
| ceramic | 3,303 | fritware | 1,266 |
| faience | 3,129 | other/unspecified | 1,100 |

**Departments** (17 total; the tail is tiny)

Greek and Roman 21,621 · European Sculpture & Decorative Arts 7,768 · Asian 6,431 ·
Egyptian 4,906 · Islamic 3,218 · The American Wing 2,108 · Ancient Near Eastern
2,040 · Africa/Oceania/Americas 1,578 · Medieval 1,439 · then nine departments
under 400 each. **The long tail needs a designed answer** — a "more" affordance, a
scroll, or a cut-off.

**The hard rendering constraint**

Tiles are baked into sprite atlases at **96px** (grid tier) and **40px** (fast-scroll
tier), WebP. A tile displayed above ~120 CSS px will visibly soften.

> **Design the grid cell at 96–120px. Do not design a grid of 200px cells** — the
> pixels do not exist and adding them costs ~40MB of permanent git history. The
> full-resolution image is only available in the detail view, where it is
> hotlinked live from the Met.

**Three levels of detail** — this is a core interaction, see §4 F6:

1. **Overview** — no imagery at all. Each object is one flat swatch of its average
   OKLab colour. At 8px, all 51,521 fit a 229×229 grid: **the entire collection on
   one screen.** Costs ~1MB. This is the most overwhelming view available and the
   purest statement of the thesis.
2. **Scroll tier** — 40px atlases, ~20MB, entire collection resident in memory.
   Fast scrolling never hits a grey placeholder.
3. **Detail tier** — 96px atlases, streamed lazily for what is on screen and settled.

---

## 3. Design language (established, keep it)

The reference direction is **archival printed ephemera**: specimen labels, catalogue
cards, receipts, rubber stamps, tear-off perforations. It earns its place — a museum
collection *is* an archival object, and ceramic study collections already speak in
accession numbers.

The palette lands on its feet too: bone, ink, mustard, terracotta and cool grey are
simultaneously the interface colours and real glaze families. **The UI is made of
the same pigments as the objects.**

### Interface tokens

| Token | Hex | Use |
|---|---|---|
| `bone` | `#F3F1EC` | paper ground, module fill |
| `paper-edge` | `#D8D4CB` | hairlines, card edges |
| `ink` | `#262623` | primary type, active state |
| `muted` | `#928F86` | labels, counts, secondary |
| `faint` | `#BAB6AC` | rules, inactive |
| `accent` | `#C05A38` | terracotta — the single accent, active dot only |

### The glaze palette (10 families)

Filter values *and* a colour system. Names are ceramic vocabulary, deliberately —
generic red/orange/yellow would be wrong for this material.

| Family | Hex | Reads as |
|---|---|---|
| cobalt | `#263A8C` | deep blue underglaze |
| turquoise | `#2A9DA3` | alkaline copper glaze |
| celadon | `#B0C4AC` | pale grey-green |
| copper green | `#4A7C4A` | saturated green |
| terracotta | `#BC6A48` | orange-red body |
| iron red | `#96362C` | deep red, oxblood |
| ochre | `#BA8F3E` | yellow-brown, amber |
| cream | `#E2D8C2` | white, buff, undecorated body |
| manganese | `#3A3034` | black, dark brown-purple |
| lustre | `#9C7C3E` | gold, metallic |

Family boundaries in OKLab are tuned against the real distribution (Stage 4), so
**exact counts are not yet known — never show invented counts.** The mockup
deliberately omits them for this reason.

### Typography

| Role | Mockup used | Ship as (self-hosted woff2) |
|---|---|---|
| Wordmark | Didot | **Bodoni Moda** or Playfair Display |
| Values, object names, headings | Baskerville | any SIL OFL transitional serif |
| **All** labels, nav, filters, counts, metadata keys | Andale Mono, uppercase, tracked out | **IBM Plex Mono** or Space Mono |

The whole system is one move: **tracked-out uppercase mono label over a serif
value.** `MEDIUM` over *Stonepaste; polychrome painted*. `CULTURE` over *Iran,
Kashan*. It is how a specimen label is set and it does the work everywhere.

> **Web fonts must be committed to the repo.** A Google Fonts `<link>` is exactly
> the external-host dependency that killed the 2019 site. No CDN, no exceptions.

### Chrome: floating modules, not a rail

No docked sidebar. The chrome is a set of frosted panels scattered asymmetrically
over the grid — title module, palette cluster, material module, layout module, sort
module — staggered so they read as scattered objects rather than a table.

**One failure worth not repeating.** The first attempt put the modules behind a flat
dark scrim and it went muddy: a scrim only *dims* a busy mosaic, it does not quiet
it, so 51,521 competing details still fought the type. The fix is **heavy backdrop
blur** — blur destroys the high-frequency detail that made the field noisy.
**Blur, not opacity,** is what lets a delicate interface sit on a maximalist image.

**Each palette module carries a diffuse bloom of its own glaze colour** — the filter
is not a swatch beside a word, the card *is* a soft cloud of the pigment. Bloom
intensity must be **luminance-compensated**, or cream, celadon and lustre vanish
into the panel while cobalt and manganese shout.

### Controls

- Filters are **lists and cards, never chips or buttons.** Active is ink-coloured
  with a small terracotta dot; inactive is muted grey.
- The layout wheel is drawn as **shapes, not words** — ▭ ■ ◆ ⬡.
- Section headers are faint tracked caps.
- Custom cursor is inherited from 2019 and should survive.

---

## 4. Function inventory

Every function the product needs. **✅ = resolved in mockup · ◐ = partially resolved ·
⬜ = needs design.**

---

### F1 · The grid ◐

**What** The primary surface. A virtualized field of square crops, absolutely
positioned, filling the viewport edge to edge with no margin, no gutter, no page
chrome behind it. It is the background of everything.

**Behaviour** Only visible rows + ~2 screens of buffer exist in the DOM. Cells are
divs with an atlas as `background-image` and a computed `background-position`.
51,521 cells, ~30 atlas requests, a few hundred live DOM nodes.

**Intent** It should read as a *textile* or a *tile sample book*, not a search
result. Evenness is the goal — the 2019 grid worked because dead-centre crops
produced a flat, swatch-like texture field. Nothing should punctuate the field:
no borders, no hover cards, no badges.

**States** default · hover (subtle lightening, inherited from 2019) · filtered
(fewer cells, reflowed) · loading (see F16) · empty (see F15).

**Needs design** Gutter or none? Hover treatment at 96px. Whether the field
bleeds under the modules (mockup says yes — keep it).

---

### F2 · Palette filter — 10 glaze families ✅

**What** The signature control. Ten cards, each a soft bloom of its own pigment.

**Behaviour** Toggle. Multi-select within the dimension (union). Composes with F3
and F4 (intersection across dimensions).

**Intent** This is the product's front door and the thing people will screenshot.
`cobalt ∩ fritware` is the good stuff.

**Needs design** Multi-select visual (two active cards at once). How the cluster
reflows if a family ends up empty after Stage 4 tuning.

---

### F3 · Material filter — 10 terms ✅

**What** The 2019 type rail, preserved: fritware, faience, terracotta, ceramic,
pottery, earthenware, stoneware, clay, porcelain, other/unspecified. Right-hand
module, serif name + tracked mono count, terracotta dot on active.

**Important framing.** These nine 2019 labels are **not a taxonomy** — an audit
found they mix four levels of abstraction, and four of them are really tracking
*departments* wearing a material label (`ceramic` is 94% Ancient American pottery).
They are kept verbatim as **"as catalogued" — the museum's own word for it** — not
as material truth. If the module has a header or tooltip, that distinction should
survive in the copy. It is honest, and it is more interesting than a clean lie.

`faience` is **new** (3,129 objects, promoted out of "other") and will be the
strongest single source of turquoise and cobalt in the collection.

---

### F4 · Department / culture filter ⬜

**What** 17 departments. **Not in the mockup — needs designing from scratch.**

**Why it exists** The audit showed department is the latent variable doing most of
the work behind the material labels anyway, and it is simply more useful to someone
browsing. Promoting it to a first-class filter is more honest than leaving it
implicit.

**The problem** 9 departments carry 98% of objects; 8 more have under 400 each.
A flat list of 17 is a long, unbalanced module in a layout with no room for one.

**Needs design** Everything. Where it lives. Whether the tail collapses. Whether
it is a third module or shares a module with material via a toggle.

---

### F5 · Sort control ◐

**What** Reorders the entire grid. Mockup shows a small module reading
`SORTED BY / Hue · then lightness`.

**Options** hue-major (default) · lightness · chroma · material · department ·
date. Sort is a precomputed index array, so switching never re-fetches anything —
**it can and should animate.**

**Intent** Hue-major is the piece. Other sorts are the argument for why hue-major
is the piece. Switching sort should feel like the collection *rearranging itself*,
not like a page reload.

**Needs design** The picker itself — the mockup shows the current state but not how
you change it. And the transition: 48,000 cells cannot each animate, so probably
only the visible ~90 tween while the rest cut.

---

### F6 · Zoom / level of detail ⬜

**What** Moving between the three tiers in §2 — overview (8px flat swatches, whole
collection on one screen) → scroll tier → detail tier. **The single biggest gap in
the current design.**

**Why it matters** The overview tier is the thesis made literal and it is
*impossible* with per-object images. It is the most striking thing the product can
do and there is currently no designed way to reach it.

**Needs design — all of it**
- What is the control? Pinch/wheel? A slider? A dedicated "see everything" button?
- Is it continuous or three detents?
- What happens to the modules at overview? (The layout wheel must fade out —
  at 8px a hexagon is a rounding error.)
- **Anchor rule:** preserve the *object* at viewport centre across a tier change,
  never the pixel scroll offset — otherwise zooming teleports you.
- Is there a transition, or a cut?

---

### F7 · Layout wheel — 4 tessellations ◐

**What** A radial dial with four detents, each a tile lattice drawn from how real
tile sample books are laid out.

| Detent | Lattice |
|---|---|
| ▭ | rectangle — 3:4 portrait, showroom sample strip |
| ■ | **square — the 2019 grid, the default** |
| ◆ | diamond — squares set on point |
| ⬡ | hexagon — offset rows, honeycomb |

**Why it earns its place** In a *ceramics* lookbook the dial reads as a **potter's
wheel**. It restates the project's own subject, and it costs **zero new assets** —
every shape is a `clip-path` over the same square atlas tile.

**Two things that need care**
1. **Density differs per lattice**, so total scroll height changes when the wheel
   turns. Again: preserve the object at viewport centre, not the scroll offset.
2. Disable at the overview tier.

**Needs design** The mockup shows four flat glyphs in a module — it is not yet a
*wheel*. Is it actually rotary (drag, momentum, snap to detent)? If so it needs a
designed dial face, detent feedback, and a rotation affordance. The morph between
lattices is a straight lerp per visible cell and can be as expressive as you want.

---

### F8 · Detail view ✅

**What** Click a tile → the object becomes a catalogue card. See
`preview-detail.png`, which resolves this well.

**Composition** Full image tipped onto a paper mount at a slight angle, warm card
behind it, accession number set below like a print caption. The clicked crop shown
as a small chip labelled `THE CROP` — so the tile you picked out of the grid is
visibly the same surface as the object. Right side: a grey catalogue card, mono
field labels over serif values, hairline rules, an accession stamp bearing the
classification and object ID, an accession year, and a dashed tear-off reading
`TEAR HERE FOR THE FULL RECORD` that links to metmuseum.org. Three attribute blocks
close the page — palette, material, surface — each a filled dot in its own colour
over a serif heading.

**Fields** object name · medium (verbatim, the raw string) · place · date ·
department · credit line · accession number · dimensions.

**Image** hotlinked `web-large` from `images.metmuseum.org`, live. ~120KB.

**Needs design** Enter/exit transition from the grid — ideally the tile itself
expands into the mount. Prev/next between objects? Behaviour when the record has
missing fields (common: no culture, no date). Mobile layout (§6).

---

### F9 · The monochrome collection ⬜ — *decision needed*

**What** 16.4% of Met ceramic photographs — roughly **8,400 objects** — are
black-and-white archival record shots. Not grey objects: greyscale film. At least
one is a placeholder card reading *"CONSULT PRIMARY RECORD"* rather than a
photograph of anything.

**Why it is a design problem** Colour-sorting a black-and-white photograph sorts it
by **film exposure**, not by glaze. Left untreated these pile into the achromatic
band and a viewer reads them as "grey-glazed ceramics," which is simply false.

**Proposed treatment** Tag them `mono: true`, **exclude from the hue-sorted grid by
default**, and offer them as a browsable category of their own. *"The part of the
collection the museum has never photographed in colour"* is a real fact about the
archive, not a defect to hide.

**Needs design** Whether this is a filter, a toggle, or its own small surface — and
the copy, which has to explain a subtle idea in about eight words. **This one is a
judgement call and it is open.**

---

### F10 · Deep links ⬜

**What** `#cobalt/fritware/451490` — filter state + open object, restored on load.
The 2019 site had no way to link to anything.

**Needs design** Nothing visual necessarily, but: is there a share affordance? Does
the URL update visibly? Does an incoming deep link animate into place or arrive
composed?

---

### F11 · Filter composition, active state, and reset ⬜

**What** Three filter dimensions (palette, material, department) that compose by
intersection, each multi-select internally.

**Behaviour** Filtering **re-flows rather than jumps** — a filter changes which
cells are in the index, animated, so **you feel the collection contract.** This is
specified and it matters.

**Needs design — a real gap**
- With three dimensions active, where does the user *see* the current filter as one
  statement? ("cobalt + turquoise ∩ fritware ∩ Islamic Art — 412 objects")
- How do you clear one dimension? All of them?
- Where does the live result count live?
- The modules are scattered by design, which makes "what is currently on" hard to
  read at a glance. That tension needs resolving without docking them into a bar.

---

### F12 · Scroll-linked rail state ◐

**What** Inherited from 2019: scrolling updates which filter value is marked
current, so the rails narrate your position in the collection.

**Intent** Under hue-major sort this is genuinely lovely — the palette cluster
lights up cobalt → turquoise → celadon as you fall through the gradient. It turns
the filter into a **position indicator**.

**Needs design** How "current" differs visually from "active/selected" — they are
different states on the same cards and must not be confused.

---

### F13 · Title / about ◐

**What** Mockup has the wordmark module: `Ceramic / Lookbook`, then
`51,521 OBJECTS · OPEN ACCESS / THE METROPOLITAN MUSEUM OF ART`.

The 2019 version had a vertical hairline tab that expanded into an info panel.

**Needs design** The about content — what the project is, that the data is Met Open
Access, credit, a link to the pipeline. Plus the honest caveats worth stating:
~3,300 objects excluded because the crop landed on backdrop, 8,400 never
photographed in colour. **Stating those is better than hiding them.**

---

### F14 · Empty state ⬜

A filter combination with zero results is easy to reach (`lustre ∩ clay ∩ Musical
Instruments`). Needs a designed answer that does not break the full-bleed field.

---

### F15 · Loading & streaming ⬜

Atlases stream. First paint should be near-instant from the 40px tier, sharpening
as 96px atlases land. Needs: initial load treatment (the 2019 loader was a spinning
cube), and **the sharpening transition** — does a tile crossfade from 40px to 96px,
or snap? A field of 90 tiles all crossfading at once is a real moment, for better
or worse.

---

### F16 · Accessibility, motion, keyboard ⬜

- `prefers-reduced-motion`: the lattice morph, filter reflow and sort transition all
  need a reduced form.
- Keyboard: arrow-key traversal of a 48,000-cell virtualized grid, focus visibility
  on a tile, escape to close detail.
- The custom cursor must not break pointer accessibility.
- Contrast: mono labels are `muted` on `bone` — verify at final sizes.

---

## 5. Interaction principles

Four rules that emerged from the plan and should govern anything new:

1. **Preserve the object, not the scroll offset.** Every transform that changes
   density — lattice change, zoom tier, filter — must keep whatever was at viewport
   centre at viewport centre. Violating this teleports the user somewhere unrelated
   and is the single easiest way to make the product feel broken.
2. **Order and lattice are independent.** `order` is an index array from the sort;
   `lattice` is a pure function `index → {x, y, w, h}`. Turning the wheel swaps
   lattice only, so **the hue gradient stays continuous through a layout change.**
3. **Blur, not opacity.** Established the hard way. See §3.
4. **Never invent data.** The palette modules carry no counts because Stage 4 has
   not run. Plausible made-up numbers are how a mockup starts lying.

---

## 6. Responsive

**Effectively unsolved and needs a real answer.** The floating-module system is a
desktop composition; five scattered frosted panels do not survive a 390px viewport.

At mobile: the grid still works (2019 used 8 columns at 12.5vw). The chrome does
not. Open questions: does the module cluster become a sheet? Does the palette
filter become a horizontal scroller of blooms? Does the layout wheel survive at all?
Is the overview tier *better* on mobile, since the whole collection fits a phone
screen just as well as a desktop one?

Touch: pinch-to-zoom is the natural gesture for F6 and conflicts with browser zoom.

---

## 7. Hard technical constraints

Non-negotiable — the 2019 site died of exactly one of these.

| Constraint | Consequence for design |
|---|---|
| **Zero runtime dependencies** | No component library, no icon font, no animation library loaded from anywhere. Icons are inline SVG or glyphs. |
| **No external hosts, ever** | Fonts committed as woff2. No Google Fonts, no CDN. A `<script src="https://…">` is the failure mode being designed against. |
| **Static files only** | No server, no API at runtime, no auth, no personalisation, no saved state beyond the URL. |
| **Atlas-baked tiles at 96px** | The grid cell has a maximum useful size. See §2. |
| **Repo weight is permanent** | Every asset ships in git forever. Big decorative imagery is expensive in a way it usually is not. |
| **Must survive a decade untended** | Prefer CSS that will still parse in 2036 over anything clever. |

---

## 8. What we are asking for

Ranked by how much it unblocks:

1. **F6 — the zoom / level-of-detail interaction.** The overview tier is the best
   thing in the product and has no designed way in. Highest value.
2. **F11 — filter composition, active state, result count, reset.** Three
   dimensions with no unified readout is the biggest functional hole.
3. **F4 — the department filter,** including an answer for the 8-department tail.
4. **F7 — make the layout wheel actually a wheel.** Dial face, detents, rotation.
5. **F9 — the monochrome collection.** A judgement call plus about eight words of copy.
6. **§6 — mobile.** A composition, not a set of breakpoints.
7. **Motion spec** across F5, F7, F11, F8 — the four transitions that carry the
   product's feel.
8. **F14, F15** — empty and loading states.

**Deliverables that would be most useful:** desktop composition at 1440 and 1920
covering default / filtered / overview / detail, a mobile composition, the motion
spec, and a token sheet reconciling §3 against whatever you change.

**Latitude:** §3's design language is established and working — please build on it
rather than restart. Everything in §4 marked ⬜ is genuinely open. If something in
the established language is fighting a function, say so; it was arrived at by
iteration, not conviction.

---

## 9. Reference files

| File | What it shows |
|---|---|
| `preview.png` | Grid mockup, real imagery, floating modules |
| `preview-detail.png` | Detail view mockup, real Met record |
| `PLAN.md` | Full engineering reasoning, every number's provenance |
| `pipeline/README.md` | Data pipeline status and method |
| `index.html`, `style.css` | The 2019 original, still intact — the language being preserved |
