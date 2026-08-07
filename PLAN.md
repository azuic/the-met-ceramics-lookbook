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

**Mitigation, built in as a knob rather than a silent decision:** the miner
takes a `--cap-per-type N` parameter.

- `--cap-per-type 0` (off) → all 52,524, the literal 3C reading.
- `--cap-per-type 2500` → ~18k objects, every material legible, terracotta
  present but not overwhelming.

Sampling when capped is **stratified by department and color bucket**, not
`head -n`, so a cap thins each region evenly instead of amputating one.

Default in the committed config: **`--cap-per-type 2500`**, with the full run a
one-flag change. Flip it if you want the raw 52k. This is a taste call and it
is yours; the pipeline supports either without a rewrite.

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

### 4b. Glazed steatite — an open call for you

**759 public-domain objects** are baked or glazed steatite. Steatite is
soapstone, a mineral, so strictly it is not ceramic. But it is fired and
glazed, it sits in the same Egyptian cases, and it is visually
indistinguishable from faience — one MET medium string literally reads
**`"Faience (?) or glazed steatite, gray-green"`**. The museum's own cataloguer
could not tell them apart.

Recommendation: **include, tagged `faience/steatite`**, on the grounds that
this is a lookbook of fired, glazed surfaces rather than a mineralogy
catalogue. Flag it if you'd rather hold the line at clay-and-frit bodies; it is
a one-line change either way.

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

**Stage 2 — `fetch.py`** — MET API per object for `primaryImageSmall`, title,
date, culture, department, `objectURL`. Rate-limited, retried with backoff,
cached as one JSON per object. ~18k–52k calls; hours, but resumable.

**Stage 3 — `tiles.py`** — download `web-large`, center-crop to square, resize,
encode WebP. Measured on 12 real objects:

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
