# The MET Ceramics Lookbook — Rebuild Plan (2026)

Rebuild of the 2019 lookbook, which went dark when its S3 bucket and the
`d1tutlfztia4ba.cloudfront.net` distribution lapsed.

---

## 1. State of the wreck

Verified 2026-08-06.

| Asset | Status |
|---|---|
| `categorized_ceramics.js` — 9,530 objects w/ type, surface, country, ISO, tokenized medium | **Intact** |
| `grouped_types.js` — the 9 type buckets | **Intact** |
| `index.html`, `style.css`, scrollMonitor grid | **Intact** |
| MET Open Access CSV | **Live** — 484,956 rows, 317 MB |
| MET Collection API | **Live** |
| `images.metmuseum.org` (`web-large`, `original`) | **Live**, hotlinkable, ~120 KB/img |
| `d1tutlfztia4ba.cloudfront.net` | **Dead** — DNS does not resolve |
| `resize-center/*.png` square tiles (the grid) | **Gone** — never in git |
| `resizes/*.png` 512px detail images | **1,547 of them recoverable** from commit `e55fd0a` |

Only the imagery was lost. Every piece of derived metadata survived in-repo.

**Root cause to design against:** the project depended on a mutable external
object store that nobody was paying attention to. The rebuild removes that
dependency entirely.

---

## 2. Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Rendering | **Vanilla JS + sprite atlases**, virtualized grid, zero runtime deps |
| 2 | Color navigation | **Glaze-palette rail** — ~10 families in ceramic vocabulary |
| 3 | Dataset | **Re-mine the current `MetObjects.csv`** |
| 4 | Asset hosting | **Committed to the repo**, deployed as static files. No object store. |

---

## 3. The consequence of re-mining — read this first

Re-mining the current CSV with the reconstructed 2019 heuristic yields
**52,524 public-domain ceramic objects**, up from 9,530. An 80-ID random
sample found **80/80 have images**, so effectively all of them are usable.

The problem is what that does to the *look* of the piece:

| Type | 2019 | 2026 re-mine |
|---|---:|---:|
| terracotta | 139 | **22,295** |
| porcelain | 1,319 | 9,274 |
| earthenware | 3,255 | 6,072 |
| other/unspecified | 75 | 4,770 |
| ceramic | 1,606 | 3,309 |
| clay | 232 | 2,209 |
| pottery | 1,580 | 1,936 |
| stoneware | 155 | 1,394 |
| fritware | 1,169 | 1,265 |
| **total** | **9,530** | **52,524** |

Top department among the new public-domain set is **Greek and Roman Art at
21,679 objects** — 41% of everything.

The 2019 lookbook reads as a field of cobalt and turquoise because it was
dominated by Islamic and Iranian fritware and earthenware. A full re-mine makes
it a **Greek-and-Roman terracotta project**: red, black, buff. That is a
different artwork, not a bigger version of the same one.

### 3a. Resolved: take all 52,524, no cap

The first draft of this plan defaulted to `--cap-per-type 2500`. That was set
before working through how the cap interacts with the **color-major default
sort**, and it was wrong. Reversed.

**Overwhelm is not the constraint — every option clears it by two orders of
magnitude.** On a 1440×900 viewport at ~120px tiles (~90 tiles visible):

| cap | total | terracotta | screenfuls | scroll |
|---:|---:|---:|---:|---:|
| 2,500 | 20,945 | 11.9% | 233 | 55 m |
| 5,000 | 29,883 | 16.7% | 332 | 79 m |
| 10,000 | 40,229 | 24.9% | 447 | 106 m |
| **none** | **52,524** | **42.4%** | **584** | **139 m** |

The threshold for "I cannot exhaust this" is somewhere around 15–20 screenfuls.
Every row above is far past it. Nobody perceives 52,000 as more numerous than
20,000 — both are simply *more than a person can hold*. The extra 32k does not
buy more overwhelm.

**What it does buy is a cleaner claim.** "Every public-domain ceramic in the
Met" is a stronger and more honest premise than "a sampled 21,000," and it
removes a set of arbitrary curatorial decisions that would otherwise need
defending.

**And the terracotta objection largely dissolves under color sort.** The 2019
grid was ordered by *material*, so a 42% bucket would have been a vast red
section you scroll through. The rebuild's default order is **hue-major**, where
those 22,295 terracotta objects do not clump as "the Greek and Roman department"
— they spread across the warm region as a large orange-red mass. That reads as a
*fact about the collection's color*, which is the entire subject of the piece,
rather than as a lopsided filter. The distribution stops being a defect and
becomes a finding.

The cap remains implemented (`--cap-per-type N`, stratified by department and
color bucket rather than `head -n`) but **defaults to off**. It stays in as an
escape hatch, not a recommendation.

### 3b. What makes 52k comfortable: three-tier level of detail

Measured tile costs (small samples, ±20%):

| Tile | Avg | × 52,524 |
|---|---:|---:|
| 40 px | 0.38 KB | **20 MB** |
| 72 px | 0.78 KB | 42 MB |
| 112 px | 1.4–1.7 KB | 73–90 MB |

Naively, scrolling the whole grid at 112px means pulling ~80 MB. Three tiers fix
that, and the top tier turns out to be free:

1. **Overview — no images at all.** At the fully zoomed-out level each object is
   a single flat swatch of its average OKLab color, drawn from `objects.bin`.
   52,524 swatches at 8px is a 229×229 grid — **the entire collection on one
   screen**, rendered from ~1 MB of data already computed in Stage 4. This is
   the most overwhelming view available, and it is impossible with per-object
   images. It is also the purest statement of the project's thesis: at maximum
   zoom-out the collection *is* nothing but its color.
2. **Scroll tier — 40px atlases, 20 MB total.** Small enough to hold the whole
   collection resident. Fast scrolling never hits a hole or a grey placeholder.
3. **Detail tier — 112px atlases, lazy.** Fetched only for what is actually on
   screen and settled.

So the full 52k costs ~20 MB to browse fluidly, with detail streamed on demand —
better behaved than a capped set loading 112px tiles eagerly.

**Remaining real cost of no cap:** the pipeline does ~52k API calls and
downloads ~6.3 GB of source imagery (cached to disk, gitignored, never
committed). That is hours of unattended running, resumable, and one-time.

---

## 4. Reconstructed classification heuristic

Recovered by mining token frequencies out of the 2019 labels. It is a
**first-match keyword priority** over the lowercased `Medium` string:

```
stonepaste | fritware | frit          → fritware
faience                               → faience          ← NEW, see 4a
terracotta | terra-cotta              → terracotta
porcelain | bone china | pâte-sur-pâte
  | parian ware | parian porcelain    → porcelain
earthenware | creamware | pearlware
  | redware | delft | maiolica
  | majolica | terre de lorraine      → earthenware
stoneware | jasperware | jasper dip
  | black basalt | basalt ware
  | celadon | raku | ironstone        → stoneware
pottery                               → pottery
ceramic                               → ceramic
clay                                  → clay
composite body | paste | glazed
  | glaze | ware | biscuit | bisque   → other/unspecified
otherwise                             → not a ceramic, skip
```

**Ordering hazards.** `stonepaste` must be tested before `stoneware`;
`earthenware` before `ware`; `bone china` before the bare `china` of
`ironstone china`.

**Substring traps — verified false positives, must NOT be matched bare:**

| Term | What it actually hits | Correct form |
|---|---|---|
| `tile` | **`Textiles`** — 7,977 woven textiles | `ceramic tile`, or Classification `Ceramics-Tiles` |
| `gres` | `"Ingres"` paper | `grès` w/ accent only |
| `parian` | Parian **marble** (25) | `parian ware`/`parian porcelain` |
| `jasper` | the mineral (204) | `jasperware`, `jasper dip` |
| `basalt` | the stone (64) | `black basalt`, `basalt ware` |
| `brick` | embroidery **brick stitch** | `mudbrick`, `fired brick` |
| `composition` | gesso/plaster ornament (117) | — exclude |
| `enamel on`, `cloisonn` | metalwork (638) | — exclude |
| `sgraffito` | a **drawing** technique on paper (12) | — exclude |
| `kaolin` | pigment on wooden objects (3) | — exclude |

**Validation gate — now two independent checks:**

1. **Against 2019 labels.** Re-running over the 9,530 surviving IDs must
   reproduce the original `type`. Target ≥99%.
2. **Against the MET's own taxonomy.** 20,103 public-domain objects carry a
   `Classification` starting with `Ceramics`. The medium rules already catch
   **19,926 of them — 99.1% recall**, with only 177 misses (112 of which were
   bone china, now fixed). Any future rule change must not regress this.

Classification is high-precision but low-recall — it labels only 20,103 of the
52,524 medium-matched objects, because Greek vases are classified `Vases`, not
`Ceramics`. So it is used as a **union input and a test**, never as a
replacement for medium matching.

### 4a. Faience — promoted to its own material

The single most consequential correction. **3,129 public-domain objects** have
`faience` in their medium, 2,547 of them from Egyptian Art. Under the 2019
rules they fall through to `other/unspecified` — they are **66% of that
bucket's 4,770**, which is why "other" ballooned from 75.

Egyptian faience is not really clay: it is a quartz-frit body that
self-glazes in the kiln, producing the copper-blue and turquoise that is the
most chromatically distinctive surface in the entire collection. For a project
whose whole subject is *color*, burying it in a bucket called "other" is the
worst available outcome. It gets its own material tab, and it will be the
strongest single source of the turquoise and cobalt palette families.

Promoting it drops `other/unspecified` from 4,770 to roughly 1,600 — which is
also what that bucket should be: a genuine remainder, not a dumping ground.

### 4b. Glazed steatite — resolved: EXCLUDE, on visual grounds

**758 glazed** + 463 unglazed public-domain steatite objects.

**Materially, it qualifies.** Steatite is soapstone, so it is not clay — but
neither is faience, which is a quartz-frit body. Once faience is admitted, the
operative criterion is no longer "made of clay" but "fired, glazed,
non-metallic." Glazed steatite passes every clause: firing converts talc to
enstatite irreversibly, and the glaze is the same alkaline copper glaze that
colours faience. The MET's own cataloguer could not always separate them —
one medium string reads **`"Faience (?) or glazed steatite, gray-green"`**.
On materials grounds the honest answer is yes, it belongs.

**It fails on photography, which is what actually matters here.** Inspecting
the objects settles it:

- They are **scarabs, stamp seals and cylinder seals** — the top object names,
  by a wide margin. Typical dimensions from the records: **1.34 × 1.07 cm**,
  **0.99 × 1.6 cm**, **3.81 × 0.97 cm**.
- At that size the MET photographs them adrift in a large field of studio grey,
  so a centre crop returns **backdrop, not object**.
- Many frames show the **modern plaster impression** taken from the seal rather
  than the artifact itself — grey cast material, none of the object's colour.

Measured on six glazed steatite crops against six ordinary ceramics:

| | mean saturation | mean luma σ |
|---|---:|---:|
| glazed steatite | **0.028** | 38.9 |
| ordinary ceramics | **0.165** | 44.1 |

Six times less saturated, with two of the six returning **exactly 0.000** —
pure greyscale. In a lookbook whose entire subject is colour, these contribute
grey squares.

**Excluded — but for the right reason.** Not "it isn't ceramic," because it
arguably is. It is excluded because its photography yields no colour.

### 4e. Roughly a sixth of the imagery has no colour at all

Found while tuning Stage 3b on a stratified sample of 890 real images.

**16.4% of MET ceramic photographs are black-and-white archival record
shots.** Not grey objects — greyscale film. The 5th percentile of whole-image
chroma is exactly `0.000`. Extrapolated across the collection that is roughly
**8,400 objects with no colour record whatsoever**, and at least one is a
placeholder card reading *"CONSULT PRIMARY RECORD"* rather than a photograph
of anything.

For a project whose entire subject is colour this is not a rounding error.
Colour-sorting a black-and-white photograph sorts it by **film exposure**, not
by glaze. Left untreated these objects would silently pile into the
achromatic band and be read by a viewer as "grey-glazed ceramics", which is
simply false.

Detection keys on the **95th percentile of whole-image chroma**, not the mean.
A genuinely white porcelain bowl shot in colour still has *some* coloured
pixels — backdrop cast, shadow, a label — while a greyscale scan has
literally none. The mean cannot separate those; the p95 does, cleanly.

**Proposed treatment — flag, exclude from colour sort, offer as its own
filter.** They stay in the dataset tagged `mono: true`, are excluded from the
hue-sorted grid by default, and become a browsable category of their own. That
is honest, and it is also genuinely interesting: "the part of the collection
the museum has never photographed in colour" is a real fact about the archive
rather than a defect to hide. **This one is a judgement call and it is yours.**

### 4c. The general lesson: crop quality control (new Stage 3b)

Steatite is the extreme case of a problem that affects the whole dataset. Any
small object — faience amulets and beads, seal stones, small fragments —
photographs as a speck in a wide studio field, and a centre crop returns
backdrop.

**This already happened in 2019.** The surviving thumbnail of the original grid
has visible flat grey and near-white squares scattered through it. Those are not
pale glazes; they are empty backdrop. Fixing it is a visible improvement to the
rebuild.

**The test must not be a saturation floor.** White porcelain, cream earthenware
and celadon are legitimately desaturated and belong in the grid — a naive
saturation cut would delete exactly the objects the `cream` palette family is
made of. Instead, Stage 3b detects **backdrop dominance**:

1. Sample the border ring of the *full* source image — on a studio shot this is
   the backdrop by construction.
2. Compute the fraction of the centre crop within a small ΔE of that colour.
3. If that fraction exceeds a threshold, the crop is mostly backdrop.
4. Before rejecting, **retry with a tighter crop** — many small objects are
   centred and recoverable at 30–40% of the frame. Only reject if the tight
   crop still fails.

This keeps a white porcelain bowl (fills the frame, low saturation, low
backdrop fraction) and drops a 1cm scarab (high backdrop fraction), which is
exactly the desired behaviour. Rejected objects stay in the dataset with a flag
so the count remains honest, and are excluded from the grid.

### 4d. Audit of the 2019 categories themselves

Two separate questions, with two different answers.

**As a mechanical rule, it is sound.** Only **18 of 9,528 objects (0.2%)** match
more than one keyword, so first-match ordering almost never decides anything
arbitrarily. Recall against the MET's own `Ceramics` classification is 99.1%.
The rule does what it claims to do, deterministically.

**As a taxonomy of materials, it is not one.** The nine buckets mix four
different levels of abstraction:

| Level | Buckets |
|---|---|
| The whole field | `ceramic` |
| The raw material | `clay` |
| A craft / form | `pottery` |
| A **body class** (the real axis) | `earthenware`, `stoneware`, `porcelain`, `fritware`, `faience` |
| A *variety* of a body class | `terracotta` (⊂ earthenware) |

The real ceramic taxonomy runs on body and vitrification temperature —
earthenware (porous, ~1000–1150 °C), stoneware (vitrified, ~1200–1300 °C),
porcelain (translucent, ~1300–1400 °C), plus the quartz-frit bodies (fritware,
faience) that sit outside that European triad. Only five of the nine buckets
name a body.

**What the other four are actually tracking: departments.**

| 2019 bucket | Dominant department | Share |
|---|---|---|
| `ceramic` | Arts of Africa, Oceania, and the Americas | **93.9%** |
| `fritware` | Islamic Art | 99.2% |
| `porcelain` | The American Wing | 80.8% |
| `terracotta` | Asian Art | 75.5% |
| `pottery` | Egyptian Art | 67.6% |
| `clay` | Asian Art | 63.8% |
| `earthenware` | Islamic Art | 49.0% |
| `stoneware` | The American Wing | 48.4% |

`ceramic` is not a material category — it is *Ancient American pottery*, at 94%
purity. `pottery` is largely *Egyptian ostraca and sherds*. The filter is a
department filter wearing a material label.

Corroborating this: for several buckets the medium string carries almost no
information at all. **59% of `ceramic` objects have the medium string literally
just "Ceramic"** (only 56 distinct strings across 1,606 objects); `porcelain` is
64% bare, `stoneware` 50%, `pottery` 48%. Those are records of which curator
typed which word.

**Verdict: the logic is fine, the labels overclaim.** And this is largely not
fixable — when the cataloguer wrote "Ceramic" and nothing else, the body is
genuinely unknown. Folding it into `earthenware` would be *inventing* data. The
vague buckets are an honest record of cataloguing uncertainty, and should be
presented as such rather than silently corrected.

**Resolution — split the one axis into two, and rename:**

- **Body** — `earthenware / stoneware / porcelain / fritware / faience /
  unspecified`. Defensible, technically real, used for grouping.
- **As catalogued** — the existing nine terms, kept verbatim, presented as *the
  museum's own word for it* rather than as material truth. This preserves the
  original piece's language and vocabulary while dropping the false claim.
- **Department / culture** — promoted to a filter in its own right, since the
  audit shows it is the latent variable doing most of the work anyway. It is
  also simply more useful to someone browsing.

**One deliberate exception.** `terracotta` is technically a variety of
earthenware, not a sibling to it, so a strict taxonomy would fold it in. Keeping
it separate anyway: unglazed iron-red body is one of the most visually distinct
surfaces in the collection, and this is a project about surface, not about
firing temperature. Where the technical and the visual taxonomy disagree here,
the visual one wins.

`surface` (transparent glaze, underglaze, tin glaze, slip, luster, unglazed…)
and `country`/`iso` are re-derived the same way, validated the same way. Note
the 2019 data contains a typo bucket, `unsepcified` (730 objects), merged into
`unspecified` on the rebuild.

---

## 5. Pipeline

Python, `pipeline/`, each stage idempotent, resumable, and cached to disk so a
crash never re-downloads. Committed alongside the site — the pipeline *is* the
insurance policy.

**Stage 1 — `mine.py`** — stream the 317 MB CSV, apply the heuristic, emit
candidate IDs + metadata. Never stores the CSV. ~2 min.

**Stage 2 — `fetch.py`** — **DONE, 2026-08-10.** MET API per object for
`primaryImageSmall`, title, date, culture, department, `objectURL`.

| | count |
|---|---:|
| candidates from stage 1 | 51,913 |
| gone — API returns 404 | 270 |
| fetched but no public image | 122 |
| **usable, with imagery** | **51,521** (99.2%) |

**51,521 is the real headline number, not 51,913.** The grid can only show
objects that have imagery, so the candidate count overstates it. Everything
user-facing should quote the usable figure.

Two lessons worth keeping. The API sits behind Imperva: concurrency 8 returns
403 on every request, and the apparent throughput at that setting is fast
rejections rather than data. `fetch.py` is serial with self-tuning
additive-increase/multiplicative-decrease pacing, which cut throttling from 4
events in 7 minutes to 1 in 13.

And **a 404 must be recorded, not merely counted as an error.** The first
version skipped them silently, so each of 20 scheduled runs re-asked the same
270 dead IDs, the crawl never reported complete, and the schedule burned
runners for two days. They are now tombstoned as `{"objectID": …,
"gone": true}`.

**Stage 3 — `tiles.py`** — download `web-large`, crop **a tight central
fraction** of the frame, resize, encode WebP.

> **Not a full centre crop.** This was wrong in the first draft and the
> preview caught it. MET photographs are whole-object studio shots; a
> square centre crop of one is still a whole vase floating on grey backdrop,
> and a grid of those reads as a museum catalogue rather than a lookbook.
> The 2019 grid shows patches of glaze, brushwork and motif, which means it
> kept roughly **a third of the frame** (`--crop 0.32`), landing inside the
> object. Compare `preview.png` against the 2019 thumbnail: same texture.
>
> This also raises the stakes on Stage 3b, since a tight crop on a small
> object lands on backdrop far more often than a loose one.

> **The 6.3 GB of source imagery is never stored.** Stage 3 streams: fetch one
> image, crop it, record its colour, discard it. Peak disk is a single image,
> not 6.3 GB. The durable outputs are the atlases (~90 MB) and the colour data
> (~1 MB) — everything else is transient by construction.
>
> On CI that is the only sane mode, since a runner's disk evaporates when the
> job ends. Locally, `pipeline/cache/images/` (gitignored) may keep originals
> so that re-cropping does not mean re-downloading — but see below, that is
> only worth it for a sample.
>
> **Do not casually regenerate the atlases.** Each full regeneration adds
> ~90 MB to git history *permanently*, and this repo already carries 547 MB of
> dead weight. Tune the QC thresholds against a local sample first, then
> produce the atlases once. Getting Stage 3b right before Stage 5 runs is
> worth real effort.

Measured on 12 real objects:

| Tile | Avg size | × 52,500 | × 18,000 (capped) |
|---|---:|---:|---:|
| 96 px | 1.37 KB | 73 MB | 25 MB |
| **112 px** | **1.71 KB** | **92 MB** | **31 MB** |
| 128 px | 2.12 KB | 114 MB | 39 MB |

**112 px at WebP q72** is the pick — comfortably above the ~120 px display size
on retina, and 31 MB capped is nothing to commit.

> The 2019 crop was a *center* crop (`resize-center/`). Keeping that. A
> saliency-based crop was considered and rejected: dead-center is what produced
> the flat, swatch-like texture field in the original, and chasing "interesting"
> regions would break that evenness.

> **Tuned 2026-08-10** on 890 stratified real images. Crop ladder
> `0.32 → 0.24 → 0.17`, reject above **40%** backdrop. The first attempt used
> a 60% threshold, which was so slack the ladder never engaged at all — 864 of
> 865 crops passed at the first rung. At 40% the ladder does its job and
> rejection lands at **6.4%**, concentrated exactly where it should be:
> Beads 50%, magical figurines 67%, sherds and fragments ~9%, while bowls,
> jars and vases sit at 3-4%.

**Stage 4 — `color.py`** — per tile, compute:
- average color in **OKLab** (perceptually uniform; averaging in sRGB muddies)
- dominant color via k-means (k=5) on OKLab, weighted by cluster mass
- chroma and lightness
- assigned glaze family (§6)

Two colors because they answer different questions: the average drives sort
position, the dominant drives the palette-family assignment. A blue-on-white
tile averages to pale grey but belongs under cobalt.

**Stage 5 — `atlas.py`** — pack tiles into 4480×4480 atlases, 40×40 = 1,600
tiles each. ~12 atlases capped, ~33 at full scale. Tiles are packed **in final
sort order** so a screenful of grid draws from one or two atlases.

**Stage 6 — `emit.py`** — write `data/objects.bin` (typed-array-friendly packed
records: id, atlas index, cell index, type, family, OKLab, country) plus a
small JSON sidecar for text. Binary because 52k × verbose JSON is several MB of
parse cost on load.

---

## 6. The glaze palette

Generic red/orange/yellow buckets would be wrong for this material. Families
are named in ceramic vocabulary, each a region in OKLab hue×chroma×lightness:

| Family | Reads as |
|---|---|
| cobalt | deep blue underglaze |
| turquoise | alkaline copper glaze |
| celadon | pale grey-green |
| copper green | saturated green |
| terracotta | orange-red body |
| iron red | deep red / oxblood |
| ochre | yellow-brown, amber |
| cream | white, buff, undecorated body |
| manganese | black, dark brown-purple |
| lustre | gold / metallic |

Boundaries get **tuned against the actual distribution**, not fixed a priori —
the histogram of the collection decides where cobalt ends and turquoise begins,
so no family ends up near-empty or absorbing a third of the set. Achromatic
tiles (chroma below threshold) route to cream or manganese by lightness before
hue is consulted.

**Ordering.** Within a family, sort by hue then lightness. Across the whole
grid the default sort is hue-major — the continuous rainbow sweep of the
original. Sort is a precomputed index array, so switching sort never re-fetches
anything.

---

## 7. Interface

Preserves the original's language — the type rail, the click-to-reveal detail,
the custom cursor — and adds the palette rail beneath it.

```
┌──────────────────────────────────────────────────────────┐
│ ▪fritware ▪terracotta ▪ceramic ▪pottery ▪earthenware ... │  material rail (existing)
│ ▪cobalt ▪turquoise ▪celadon ▪terracotta ▪ochre ▪cream ...│  palette rail (new)
├──────────────────────────────────────────────────────────┤
│ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ │
│ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ ███ │
└──────────────────────────────────────────────────────────┘
```

- Both rails are **filters that compose** — cobalt ∩ fritware is the good stuff.
- Each rail swatch is drawn in its own family color, sized by count, so the rail
  is itself a bar chart of the collection's palette.
- Scrolling still drives the rails' active state, as in the original.
- Filtering **re-flows rather than jumps** — a filter changes which cells are in
  the index, animated, so you feel the collection contract.
- Click a tile → full image (hotlinked `web-large`) + medium string, title,
  date, culture, department, and a link to metmuseum.org.
- **Deep links**: `#cobalt/fritware/451490` so a view is shareable. The original
  had no way to link to anything.

**Virtualization:** absolutely-positioned grid, only visible rows + 2 screens of
buffer in the DOM. Each cell is a div with the atlas as `background-image` and a
computed `background-position` — 52k cells, ~30 atlas requests, a few hundred
DOM nodes at a time.

### 7a. The layout wheel — four tessellations

A radial dial with four detents, each selecting a tile tessellation drawn from
how real tile sample books are laid out:

| Detent | Lattice | `clip-path` |
|---|---|---|
| ▭ | **rectangle** — 3:4 portrait, showroom sample strip | none, adjust `background-size` |
| ■ | **square** — the 2019 grid, the default | none |
| ◆ | **diamond** — squares set on point, diagonal lattice | `polygon(50% 0, 100% 50%, 50% 100%, 0 50%)` |
| ⬡ | **hexagon** — offset rows, honeycomb | 6-point `polygon(…)` |

In a *ceramics* lookbook the dial reads as a **potter's wheel**, which is what
justifies it as a control rather than an ornament. Real tile sample sets are
laid out exactly these ways, so the feature restates the project's own subject.

**It costs no new assets.** This is the thing that makes it worth doing. Tiles
stay square in the atlases; every shape is a `clip-path` over the same
background image. Rectangles are a `background-size`/`background-position`
change. So the wheel adds **zero bytes** to the 20 MB scroll tier and requires
no pipeline changes — Stages 3–5 are untouched.

**The architecture already supports it,** because two concerns are separate:

- **`order`** — an index array, produced by the sort (hue-major, material, etc.)
- **`lattice`** — a pure function `index → {x, y, w, h}`

The wheel swaps `lattice` only. Colour order is untouched, so the hue gradient
stays continuous through a layout change. A `Lattice` interface needs just
three things: cell size, a row-offset rule, and `scrollTop → visible index
range`. All four tessellations are regular lattices, so all four are a few
lines each. Hexagons use pointy-top with offset rows so row-major
virtualization still applies (row pitch = 0.75 × hex height).

**Two details that need care:**

1. **Density differs per lattice**, so total scroll height changes when the
   wheel turns. Preserve the *object* at viewport centre, not the pixel scroll
   offset — otherwise turning the dial teleports you somewhere unrelated.
2. **Disable shape at the overview tier.** At 8px swatches a hexagon is a
   rounding error; the wheel should fade out when fully zoomed out.

### 7c. Design language — printed ephemera

The reference direction is archival paper: receipts, specimen labels, rubber
stamps, tear-off perforations. It suits the subject better than it first
appears — a museum collection *is* an archival object, and ceramic study
collections already speak in accession numbers and catalogue cards.

The palette lands on its own feet too. Bone, ink, mustard, terracotta and
cool grey are simultaneously the interface colours and real glaze families:
`cream`, `manganese`, `ochre`, `terracotta`, `celadon`. The UI is made of the
same pigments as the objects.

**Typography**

| Role | Face |
|---|---|
| Wordmark | High-contrast Didone, roman over italic — two-line lockup |
| All labels, nav, filters, metadata | Monospace, **uppercase, tracked out** |
| Values in the detail view | Serif, regular, sentence case |

The tracked-out monospace label against a serif value is the whole system.
It is how a specimen label is set, and it does the work everywhere: `MEDIUM`
over *Stonepaste; polychrome painted*, `CULTURE` over *Iran, Kashan*.

> **Web fonts:** Didot and Andale Mono ship with macOS and cannot be
> deployed. Substitute **Bodoni Moda** or **Playfair Display** for the
> Didone and **IBM Plex Mono** or **Space Mono** for the labels — all
> SIL OFL. Self-host the woff2 files **in the repo**. A Google Fonts link is
> the same external-host dependency that killed the 2019 site.

**Navigation is floating modules, not a rail.**

No docked sidebar. The chrome is a set of frosted panels scattered over the
grid — a title module, a cluster of palette cards, a material module, a
layout module, a sort module — placed asymmetrically and staggered so the
cluster reads as scattered objects rather than as a table.

This took two attempts to get right, and the failure is worth recording. The
first version put the rails over the grid behind a **flat dark scrim**, and it
went muddy: a scrim only *dims* a busy mosaic, it does not quiet it, so 51,913
competing details still fought the type. The fix is a **heavy backdrop blur**,
which destroys the high-frequency detail that made the field noisy in the
first place. Blur, not opacity, is what lets a delicate interface sit directly
on a maximalist image.

**Each palette module carries a diffuse bloom of its own glaze colour.** The
filter is not a swatch beside a word — the card *is* a soft cloud of the
pigment. Bloom intensity is compensated for luminance, or the pale families
(cream, celadon, lustre) disappear into the panel while cobalt and manganese
shout.

**Controls**

- Filters are lists and cards, never chips or buttons. Active is ink-coloured
  with a small terracotta dot; inactive is muted grey.
- The layout wheel is drawn as **shapes rather than words** — ▭ ■ ◆ ⬡.
- Section headers are faint tracked caps.
- Serif for names, tracked mono for labels and counts.

**Never invent data, even in a mockup.** The palette modules deliberately
carry *no* counts: colour extraction is Stage 4 and has not run, and plausible
made-up numbers are how a mockup starts lying. The material module shows real
Stage 1 counts, read from `mine_summary.json`.

**Detail view** — the object card is a catalogue card: monospace field labels
over serif values, a dashed rule, an accession stamp bearing the object ID,
and the full image reproduced as if tipped onto the page.

**Detail view** is the payoff: the object becomes a catalogue card. Field
labels in tracked mono over serif values, hairline rules between rows, an
accession stamp, a `1912` accession year set like the reference's `1924`, and
a dashed tear-off carrying `TEAR HERE FOR THE FULL RECORD`. The image is
tipped onto a paper mount at a slight angle, with a warm card behind it and
the clicked crop shown as a small chip labelled `THE CROP` — so the tile you
picked out of the grid is visibly the same surface as the object.

Three attribute blocks close the page — palette, material, surface — each a
filled circle in its own colour over a serif heading, echoing the reference's
info row.

See `preview.png` (grid) and `preview-detail.png` (object), both generated by
`pipeline/preview.py` from real imagery and a real MET record.

### 7b. GSAP — recommendation: no, and one hard condition if yes

GSAP is unusually well matched to the *literal* request. `Draggable` with
`type: "rotation"`, `snap: [0, 90, 180, 270]` and `inertia: true` is close to a
one-line spinning dial with momentum and detents. That is a real saving and
should be acknowledged rather than waved off.

**But the second half of the job argues the other way.** The obvious companion,
the `Flip` plugin, exists to animate between two layouts whose positions must be
*measured* from the DOM. Ours do not need measuring — `lattice(index)` returns
the target position analytically, for both the old and new layout. The morph is
therefore a straight lerp between two computed points per visible cell, which is
a few lines inside the render loop we are already writing. Flip would also fight
the virtualizer, since the set of live elements changes mid-transition and Flip
assumes stable elements.

So GSAP would earn its place for one control — the dial — which is roughly
60–80 lines of pointer events, velocity tracking, rAF decay and snap-to-nearest.
Against that: the project's stated first principle is zero runtime
dependencies, and its whole premise is surviving a decade untended.

**Recommendation: hand-roll it.** Distance-based stagger, if wanted, is a
`transition-delay` computed from each cell's distance to the dial — about three
lines, not a library.

**If GSAP is used anyway, one condition is non-negotiable: vendor the file into
the repo. Never load it from a CDN.** A `<script src="https://cdn…">` tag is
precisely the failure that killed the 2019 site — an external host, outside our
control, that silently stops resolving. A committed, versioned copy has none of
that risk. The objection to GSAP here is mild; the objection to *CDN-loaded*
GSAP is the entire point of the rebuild.

---

## 8. Repo layout

```
/
  index.html            entry
  css/
  js/                   grid.js, rails.js, detail.js, data.js
  data/
    objects.bin
    meta.json
    palette.json
  atlases/              *.webp  ← the durable asset, in git
  pipeline/             mine.py fetch.py tiles.py color.py atlas.py emit.py
    cache/              gitignored — API + source images
  PLAN.md
```

Legacy 2019 files (`categorized_ceramics.js`, `grouped_types.js`, `medium.js`,
`objects.js`) stay put until the validation gate in §4 passes, then move to
`legacy/` as the reference dataset.

---

## 9. Phases

1. **Pipeline + validation gate** — stages 1–2, prove ≥99% agreement with 2019
   labels. Nothing else starts until this passes.
2. **Tiles, color, atlases** — stages 3–5, the long unattended run.
3. **Grid** — virtualized renderer, atlas cells, scroll. Feature parity with 2019.
4. **Rails** — material + palette, composing filters, scroll-linked state.
4b. **Layout wheel** — the `Lattice` interface and its four implementations.
5. **Detail view + deep links.**
6. **Polish** — reduced-motion, keyboard nav, the cursor, mobile.
7. **Deploy** — GitHub Pages or Vercel, both pure-static.

---

## 10. Risks

| Risk | Handling |
|---|---|
| **Character shift to Greek/Roman terracotta** | §3 — `--cap-per-type`, stratified sampling, default 2500 |
| Heuristic drift from 2019 | Validation gate against surviving labels; hard blocker |
| 18k–52k API calls | Rate-limited, resumable, disk-cached; re-runnable in pieces |
| MET reshuffles image URLs | URLs stored in our data; `fetch.py` re-run repairs. Tiles are ours and unaffected. |
| Repo weight | 31 MB capped / 92 MB full, in ~12–33 atlas files rather than 52k loose files — git handles that fine |
| Existing 547 MB of history | The old `resize_crops` blobs are dead weight. `git filter-repo` would drop the repo to ~10 MB. **Not doing this unilaterally** — it rewrites published history. Say the word. |
| Public-domain status changes | Re-runnable pipeline; non-PD objects drop out on the next run |

---

## 11. Why this one survives

- No object store, no CDN account, no credentials, no bill.
- Assets are versioned next to the code that renders them.
- No runtime dependencies — nothing to go stale or get a CVE.
- Deploys anywhere that serves static files.
- The pipeline is committed, so the whole thing is reproducible from the MET's
  public data even if every derived file were deleted.

The 2019 version died because one external thing it didn't own went away.
Nothing here is owned by anyone else.
