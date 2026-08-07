# Pipeline

Rebuilds the lookbook's dataset from the MET Open Access CSV. Every stage is
idempotent and resumable, and nothing here depends on a service that can
expire. See `../PLAN.md` for the reasoning.

## Status

| Stage | Script | State |
|---|---|---|
| 1 — mine the CSV | `mine.py` | **done** |
| gate — validate the rules | `validate.py` | **passing** |
| 2 — fetch image URLs + metadata | `fetch.py` | **ready** — run locally or via CI |
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

### Stage 2 without leaving a laptop on

The crawl takes ~7 hours at a polite rate. Two ways to run it:

**On GitHub's runners** — Actions tab → *Stage 2 — fetch MET metadata* → Run
workflow, with `rebuild-2026` selected as the branch. Or from the CLI:

```sh
gh api -X POST \
  repos/azuic/the-met-ceramics-lookbook/actions/workflows/fetch.yml/dispatches \
  -f ref=rebuild-2026 -f 'inputs[max_runtime]=17400'
```

State lives in `data/api_objects.jsonl.gz`, committed back to the branch after
each run, so runs chain across machines. Needs ~2 runs.

The workflow file is duplicated onto `master`. That is not an accident:
GitHub refuses to register a `workflow_dispatch` trigger unless the workflow
exists on the repository's default branch. Runs still execute the copy on
whichever branch they target.

`schedule:` is deliberately not used: GitHub only fires scheduled workflows
from the repository's **default** branch (`master` here), so it would silently
never run while this work lives on `rebuild-2026`.

**Locally, surviving a closed lid:**

```sh
caffeinate -is python3 pipeline/fetch.py
```

Either way it is resumable. Interrupting it costs only the in-flight request.

### Rate limits — measured, not guessed

The API sits behind Imperva and is genuinely aggressive:

| concurrency | result |
|---|---|
| 4 | ~12 req/s, occasional 403 |
| 8 | **403 on every request** |
| after a burst | IP soft-banned; recovers in ~30s once traffic stops |

The apparent "98 req/s" at concurrency 8 is 80 fast rejections, not
throughput. `fetch.py` is therefore serial with a self-tuning delay and a
backoff. Bursting does not make it faster, it makes it stop. Please do not
raise the rate to be clever — it is someone's free public API.

Measured on GitHub runners, which are throttled harder than a home
connection:

| pacing | 403s | effective |
|---|---|---|
| fixed 0.18s | 4 in 7 min | 1.34 req/s |
| adaptive, from 0.30s | 1 in 13 min | 1.66 req/s |

The adaptive pacer settles around **0.31s** (~3.2 req/s attempted, ~1.7 req/s
sustained once latency is counted). Request latency is now roughly equal to
the delay, so the remaining ceiling is round-trip time, not the WAF.

Full crawl is ~8 hours, i.e. two runs. Start a later run with `--delay 0.31`
so it does not rediscover the rate from scratch.

Note that a local run writes `data/api_objects.jsonl.gz` too, so if CI has
committed since, discard the local copy (`git checkout --`) before pulling —
the merge on next start will pick everything up by object ID anyway.

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
