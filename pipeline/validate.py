"""Validation gate for the reconstructed classification heuristic.

Nothing downstream should run until this passes. See PLAN.md section 4.

The gate asks two separate questions, because a single accuracy number would
let them mask each other:

  GATE 1 - fidelity.  Does a reconstruction of the *2019* rules reproduce the
           *2019* labels?  This tests whether we understood the original at
           all.  Must be >= 99%.

  GATE 2 - attribution.  Where the *new* rules disagree with 2019, is every
           disagreement explained by a keyword we deliberately added?  An
           unattributed disagreement means an accidental regression.

Runs entirely offline against pipeline/data/legacy_2019.json, which carries
the 2019 medium strings alongside the 2019 labels.
"""

import json
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import (classify_type, classify_surface,  # noqa: E402
                      medium_supports, OTHER)

HERE = os.path.dirname(os.path.abspath(__file__))
LEGACY = os.path.join(HERE, "data", "legacy_2019.json")

FIDELITY_THRESHOLD = 99.0

# ---------------------------------------------------------------------------
# Reconstruction of the 2019 rules, used ONLY by this gate.
# Deliberately kept naive: no faience, no varietal names, no compound-only
# mineral guards. This is what we believe the original did, not what we want.
# ---------------------------------------------------------------------------

LEGACY_TYPE_RULES = [
    ("fritware",    ("stonepaste",)),
    ("terracotta",  ("terracotta", "terra-cotta", "terra cotta")),
    ("porcelain",   ("porcelain",)),
    ("earthenware", ("earthenware",)),
    ("stoneware",   ("stoneware",)),
    ("pottery",     ("pottery",)),
    ("ceramic",     ("ceramic",)),
    ("clay",        ("clay",)),
]
LEGACY_OTHER_HINTS = ("composite body", "paste", "glaze", "ware", "porcelaneous")


def legacy_classify_type(medium):
    m = (medium or "").lower()
    for label, keys in LEGACY_TYPE_RULES:
        if any(k in m for k in keys):
            return label
    if any(h in m for h in LEGACY_OTHER_HINTS):
        return OTHER
    return None


# Keywords added in the rebuild. A disagreement is "attributed" if the medium
# contains one of these -- i.e. we can name the rule that caused it.
ADDED_KEYWORDS = (
    "faience",
    "bone china", "pâte-sur-pâte", "pate-sur-pate", "parian ware",
    "parian porcelain",
    "creamware", "pearlware", "redware", "yellowware", "yellow ware",
    "delft", "delftware", "maiolica", "majolica", "terre de lorraine",
    "jasperware", "jasper dip", "black basalt", "basalt ware",
    "celadon", "raku", "ironstone", "shigaraki",
    "blackware", "black ware", "buff ware", "gray ware", "grey ware",
    "brown ware", "orange ware",
    "fritware", "frit ", "stone-paste", "stone paste", "mina'i", "minai",
    "biscuit", "bisque", "proto-stoneware",
)

# Materials that are simply not ceramic. Where the new rules return None and
# the 2019 medium names one of these, 2019 was wrong to include the object at
# all -- that is a correction, not a regression, and is counted separately.
NON_CERAMIC = (
    "plaster", "limestone", "sandstone", "stucco", "glass", "wood", "stone",
    "copper", "bronze", "silver", "gold leaf", "ivory", "polychrome",
)


def main():
    with open(LEGACY) as f:
        legacy = json.load(f)

    n = len(legacy)
    fid_ok = 0
    fid_bad = collections.Counter()
    fid_examples = collections.defaultdict(list)

    new_same = 0
    attributed = collections.Counter()
    rejected = collections.Counter()
    unsupported = collections.Counter()
    priority = collections.Counter()
    unattributed = []

    surf_same = 0
    surf_diff = collections.Counter()

    for oid, rec in legacy.items():
        med = rec["medium"]
        want = rec["type"]

        # ---- gate 1: does the reconstruction reproduce 2019? ----
        got_legacy = legacy_classify_type(med)
        if got_legacy == want:
            fid_ok += 1
        else:
            key = f"{want} -> {got_legacy}"
            fid_bad[key] += 1
            if len(fid_examples[key]) < 3:
                fid_examples[key].append(med[:78])

        # ---- gate 2: are the new rules' changes all deliberate? ----
        got_new = classify_type(med)
        if got_new == want:
            new_same += 1
        else:
            m = med.lower()
            hit = next((k for k in ADDED_KEYWORDS if k in m), None)
            if hit:
                attributed[f"{want} -> {got_new}  (via '{hit.strip()}')"] += 1
            elif got_new is None and (
                    not m.strip() or any(k in m for k in NON_CERAMIC)):
                rejected[med.strip()[:60] or "(empty medium)"] += 1
            elif not medium_supports(med, want):
                # 2019 asserted a type its own medium string never mentions
                unsupported[f"{want} -> {got_new}   {med.strip()[:52]!r}"] += 1
            elif medium_supports(med, got_new):
                # both types are named; our documented priority order decides
                priority[f"{want} -> {got_new}   {med.strip()[:52]!r}"] += 1
            else:
                unattributed.append((oid, want, got_new, med[:78]))

        # ---- informational: surface ----
        old_surf = set(s.replace("unsepcified", "unspecified")
                       for s in rec.get("surface", []))
        # 2019's "unglaze" was inverted; map it to what it actually meant
        old_surf = set("glazed" if s == "unglaze" else s for s in old_surf)
        if old_surf == set(classify_surface(med)):
            surf_same += 1
        else:
            surf_diff[f"{sorted(old_surf)} -> {sorted(classify_surface(med))}"] += 1

    fid_pct = 100.0 * fid_ok / n
    new_pct = 100.0 * new_same / n

    print("=" * 72)
    print(f"VALIDATION GATE   ({n:,} objects from the 2019 dataset)")
    print("=" * 72)

    print(f"\nGATE 1 - fidelity of the 2019 reconstruction")
    print(f"  reproduced : {fid_ok:,} / {n:,}   ({fid_pct:.2f}%)")
    print(f"  threshold  : {FIDELITY_THRESHOLD}%")
    if fid_bad:
        print(f"  mismatches :")
        for k, v in fid_bad.most_common(12):
            print(f"     {v:>5}  {k}")
            for ex in fid_examples[k][:2]:
                print(f"            e.g. {ex!r}")

    print(f"\nGATE 2 - attribution of the rebuild's changes")
    print(f"  unchanged from 2019      : {new_same:,} / {n:,}  ({new_pct:.2f}%)")
    print(f"  changed, and attributable: {sum(attributed.values()):,}")
    for k, v in attributed.most_common(14):
        print(f"     {v:>5}  {k}")
    print(f"  rejected as non-ceramic  : {sum(rejected.values()):,}"
          f"   (2019 false positives)")
    for k, v in rejected.most_common(10):
        print(f"     {v:>5}  {k!r}")
    print(f"  2019 label unsupported   : {sum(unsupported.values()):,}"
          f"   (its own medium never said so)")
    for k, v in unsupported.most_common(6):
        print(f"     {v:>5}  {k}")
    print(f"  priority-order decisions : {sum(priority.values()):,}"
          f"   (documented, PLAN.md 4d)")
    for k, v in priority.most_common(6):
        print(f"     {v:>5}  {k}")
    print(f"  changed, UNATTRIBUTED    : {len(unattributed):,}")
    for oid, want, got, med in unattributed[:12]:
        print(f"     {oid}: {want} -> {got}   {med!r}")

    print(f"\nINFORMATIONAL - surface agreement")
    print(f"  identical: {surf_same:,} / {n:,}  ({100.0*surf_same/n:.1f}%)")
    for k, v in surf_diff.most_common(8):
        print(f"     {v:>5}  {k}")

    ok = fid_pct >= FIDELITY_THRESHOLD and not unattributed
    print("\n" + "=" * 72)
    print("RESULT:", "PASS" if ok else "FAIL")
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
