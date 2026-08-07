# Pipeline

Rebuilds the lookbook's dataset from the MET Open Access CSV. Every stage is
idempotent and resumable, and nothing here depends on a service that can
expire. See `../PLAN.md` for the reasoning.

## Status

| Stage | Script | State |
|---|---|---|
| 1 — mine the CSV | `mine.py` | **done** |
| gate — validate the rules | `validate.py` | **passing** |
| 2 — fetch image URLs + metadata | `fetch.py` | not started |
| 3 — crop and resize tiles | `tiles.py` | not started |
| 3b — crop quality control | `qc.py` | not started |
| 4 — extract colour | `color.py` | not started |
| 5 — pack atlases | `atlas.py` | not started |
| 6 — emit site data | `emit.py` | not started |

## Running

```sh
python3 pipeline/validate.py          # must PASS before anything else runs
python3 pipeline/mine.py              # downloads the CSV to cache/ on first run
python3 pipeline/mine.py --cap-per-type 10000
```

`mine.py` caches the 318 MB CSV in `cache/` and reuses it. Delete it to refresh.

## Files

| Path | Committed | Why |
|---|---|---|
| `classify.py` | yes | the rules |
| `validate.py` | yes | the gate |
| `mine.py` | yes | stage 1 |
| `data/legacy_2019.json` | **yes** | 2019 ground truth, extracted from the old `categorized_ceramics.js`. Irreplaceable — the gate depends on it. |
| `data/mine_summary.json` | yes | small; records what a run produced |
| `data/candidates.jsonl` | no | 23 MB, regenerates in ~40s |
| `cache/` | no | 318 MB CSV + downloaded imagery |

## The validation gate

`validate.py` asks two questions separately, because one combined accuracy
number would let them hide each other:

1. **Fidelity** — does a deliberately naive reconstruction of the *2019* rules
   reproduce the *2019* labels? Currently **99.11%**, threshold 99%. This
   tests whether we understood the original at all.
2. **Attribution** — where the *new* rules disagree with 2019, is every
   disagreement explained? Currently **0 unattributed**. Disagreements are
   sorted into: caused by a keyword we deliberately added; a 2019 false
   positive we now reject; a 2019 label its own medium string never supported;
   or a documented priority-order decision.

An unattributed disagreement fails the gate. That is the point.

## Known 2019 bugs, fixed rather than reproduced

- **`unglaze` was inverted.** All 1,014 objects carrying it were *glazed* —
  none were unglazed. The label meant the opposite of the truth.
- **`unsepcified`** was a typo bucket holding 730 objects alongside the
  correctly spelled `unspecified`. Merged.
- **Limestone catalogued as earthenware** — 12 ostraca reading `"Limestone
  with ink inscription"`. Now rejected as non-ceramic.
- **Plaster, stone, glass, stucco and empty media** were included as ceramics.
  31 objects, now rejected.

## Substring traps

Short keywords are dangerous against free-text medium strings. Measured, real:

| Pattern | Wrongly matched |
|---|---|
| `tile` | `Textiles` — 7,977 woven textiles |
| `paste` | `pasted onto`, `paste-resist dyeing` — prints and kimono |
| `ware` | `hardware` |
| `in[- ]?glaz` | `tin glaze` |
| `gres` | `"Ingres"` paper |
| `jasper`, `basalt`, `parian` | the minerals, and Parian marble |
| `sgraffito` | a drawing technique on paper |

Guards live in `classify.py`. Do not loosen them without re-running the gate.
