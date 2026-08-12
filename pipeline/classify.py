"""Medium-string classification for the MET ceramics lookbook.

Reconstructed from the 2019 dataset by mining token frequencies out of the
surviving labels, then corrected. See PLAN.md sections 4, 4a, 4b, 4d.

The rules are deliberately ordered. Read the comments before reordering.
"""

import re

# ---------------------------------------------------------------------------
# Body / material type
# ---------------------------------------------------------------------------
# First match wins. Order is load-bearing:
#   - "stonepaste" must be tested before "stoneware"
#   - "earthenware" must be tested before the bare "ware" fallback
#   - "bone china" must be tested before "ironstone" (which contains "stone")
#
# Bare mineral names are deliberately NOT matched. "jasper", "basalt" and
# "parian" name stones far more often than ceramic bodies in this collection;
# only the compound forms are ceramic. See PLAN.md section 4 for the audit.

TYPE_RULES = [
    ("fritware", (
        "stonepaste", "stone-paste", "stone paste", "fritware", "frit ",
        "mina'i", "minai",  # Persian enamelled stonepaste
    )),
    ("faience", (
        "faience",
    )),
    ("terracotta", (
        "terracotta", "terra-cotta", "terra cotta",
    )),
    ("porcelain", (
        "porcelain", "bone china", "pâte-sur-pâte", "pate-sur-pate",
        "parian ware", "parian porcelain",
    )),
    ("earthenware", (
        "earthenware", "creamware", "pearlware", "redware", "yellowware",
        "yellow ware", "delftware", "delft", "maiolica", "majolica",
        "terre de lorraine",
    )),
    ("stoneware", (
        "stoneware", "jasperware", "jasper dip", "black basalt", "basalt ware",
        "celadon", "raku", "ironstone", "shigaraki",
    )),
    # Archaeological colour-ware names. These are how excavation reports
    # describe undifferentiated fired vessels, so "pottery" is the honest
    # bucket -- and it is what 2019 did with them.
    ("pottery", (
        "pottery", "blackware", "black ware", "buff ware", "gray ware",
        "grey ware", "brown ware", "orange ware",
    )),
    ("ceramic", ("ceramic",)),
    ("clay", ("clay",)),
]

# Weak signals — only consulted if nothing above matched. These mean
# "probably ceramic, body unknown", which is an honest answer rather than a
# guess. Note "porcelaneous" is NOT folded into porcelain: it means
# porcelain-LIKE, and the distinction is real.
#
# These are far more dangerous than the strong rules above, because they are
# short and generic. Measured leakage from a naive version of this list:
#   "paste"  matched "pasted onto", "paste-resist dyeing"  -> prints, kimono
#   "ware"   matched "hardware"                            -> furniture
# So bare "paste" is gone, "ware" is checked as a whole word against a
# blocklist, and a veto list rejects media that name a non-ceramic craft.
OTHER_HINTS = (
    "composite body", "porcelaneous", "porcellaneous",
    "soft paste", "soft-paste", "hard paste", "hard-paste",
    "glazed", "glaze", "biscuit", "bisque",
)

# Words ending in -ware that are not ceramic.
WARE_BLOCKLIST = {
    "hardware", "silverware", "glassware", "flatware", "stemware",
    "ironware", "metalware", "software", "barware", "woodenware",
    "treenware", "enamelware", "tinware",
}

# If none of the strong rules matched and the medium names one of these, the
# object belongs to another craft entirely. Vetoes the weak hints only --
# a strong match like "porcelain" still wins, so "Silver, porcelain
# (Meissen), steel, gold, textile" is correctly kept as porcelain.
CRAFT_VETO = (
    "lithograph", "etching", "engraving", "woodcut", "woodblock", "albumen",
    "photograph", "oil on canvas", "watercolor", "watercolour", "gouache",
    "silk", "cotton", "wool", "linen", "embroider", "tapestry", "lace",
    "canvas", "paper", "parchment", "vellum", "leather", "feather",
)

_WARE_RE = re.compile(r"\b(\w*ware)\b")

OTHER = "other/unspecified"


def _weak_ceramic_signal(m):
    """Weak evidence that `m` describes a ceramic of unknown body."""
    if any(h in m for h in OTHER_HINTS):
        return True
    return any(w not in WARE_BLOCKLIST for w in _WARE_RE.findall(m))


def classify_type(medium):
    """Return a body type, or None if the medium is not ceramic at all."""
    m = (medium or "").lower()
    if not m:
        return None
    for label, keys in TYPE_RULES:
        if any(k in m for k in keys):
            return label
    if any(v in m for v in CRAFT_VETO):
        return None
    if _weak_ceramic_signal(m):
        return OTHER
    return None


# ---------------------------------------------------------------------------
# Surface treatment
# ---------------------------------------------------------------------------
# Ordered: specific glaze chemistries before the generic "glazed" catch-all,
# and "unglazed" before "glazed" so the negation is not swallowed by its own
# substring.
#
# Two 2019 bugs are fixed here rather than reproduced:
#   1. The 2019 label "unglaze" was applied to 1,014 objects, of which ZERO
#      were actually unglazed -- every one was glazed. The label meant the
#      exact opposite of the truth. It is "glazed" here.
#   2. "unsepcified" was a typo bucket holding 730 objects alongside the
#      correctly spelled "unspecified". Merged.

SURFACE_RULES = [
    # negation first, so it is not swallowed by its own substring
    ("unglazed",          r"unglaz|not glazed|without glaze"),
    # specific glaze chemistries.  The optional middle word matters:
    # "transparent colorless glaze" is common and a literal "transparent
    # glaze" match would miss it and fall through to the generic bucket.
    ("tin glaze",         r"tin[- ]glaz"),
    ("lead glaze",        r"lead[- ]glaz"),
    ("alkaline glaze",    r"alkaline[- ]glaz"),
    ("salt glaze",        r"salt[- ]glaz"),
    ("transparent glaze", r"(?:transparent|clear)(?:\s+\w+)?\s+glaz"),
    ("underglaze",        r"under[- ]?glaz"),
    ("overglaze",         r"over[- ]?glaz"),
    ("inglaze",           r"\bin[- ]?glaz"),
    # decoration techniques
    ("luster",            r"lustre|luster"),
    ("slip",              r"slip"),
    ("engobe",            r"engobe|sgraffito"),
    ("incise",            r"incis"),
    ("transfer print",    r"transfer[- ]print"),
    ("enamel",            r"enamel"),
    ("ink",               r"\bink\b"),
    ("pigment",           r"pigment"),
    ("paint",             r"paint"),
    ("lacquer",           r"lacquer"),
    ("postfire",          r"post[- ]?fire"),
    # generic -- only reached if no specific glaze above matched
    ("glazed",            r"glaz"),
]

SURFACE_PATTERNS = [(label, re.compile(pat)) for label, pat in SURFACE_RULES]

# Labels that already say something specific about the glaze. If any of these
# matched, the generic "glazed" adds nothing and is suppressed.
GLAZE_SPECIFIC = {
    "unglazed", "tin glaze", "lead glaze", "alkaline glaze", "salt glaze",
    "transparent glaze", "underglaze", "overglaze", "inglaze",
}

UNSPECIFIED = "unspecified"


def classify_surface(medium):
    """Return a list of surface treatments. Objects can have several."""
    m = (medium or "").lower()
    found = []
    saw_specific_glaze = False
    for label, pat in SURFACE_PATTERNS:
        if not pat.search(m):
            continue
        if label == "glazed" and saw_specific_glaze:
            continue
        if label in GLAZE_SPECIFIC:
            saw_specific_glaze = True
        found.append(label)
    return found or [UNSPECIFIED]


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "and", "the", "of", "on", "in", "with", "under", "over",
    "or", "to", "for", "at", "by", "from", "into", "onto", "is", "are",
}

_TOKEN_RE = re.compile(r"[a-zà-ÿ][a-zà-ÿ0-9-]*")


def tokenize(medium):
    """Lowercase word tokens, stopwords removed, order and duplicates kept."""
    return [t for t in _TOKEN_RE.findall((medium or "").lower())
            if t not in STOPWORDS]


def classify(medium):
    """Full classification of one medium string."""
    t = classify_type(medium)
    if t is None:
        return None
    return {
        "type": t,
        "surface": classify_surface(medium),
        "tokened": tokenize(medium),
    }


def medium_supports(medium, type_label):
    """True if `medium` contains a keyword that would justify `type_label`.

    Used by the validation gate to tell a deliberate priority decision apart
    from a 2019 label that its own medium string never supported.
    """
    m = (medium or "").lower()
    for label, keys in TYPE_RULES:
        if label == type_label:
            return any(k in m for k in keys)
    if type_label == OTHER:
        return any(h in m for h in OTHER_HINTS)
    return False
