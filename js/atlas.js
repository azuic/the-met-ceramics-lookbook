/* atlas.js — the crops, packed into sheets and fetched as they are needed.
 *
 * A sheet costs width x height x 4 bytes once decoded, so they are never all
 * resident. Anything not yet loaded draws as the object's flat colour, which is
 * what the field would have shown anyway, so nothing ever waits on a network
 * round trip.
 *
 * The cache is decided per frame rather than by a fixed cap, because the size
 * of the working set is not a constant. A screenful is only contiguous in the
 * packed order when the field is unfiltered and unsorted: a material filter or
 * a colour sort scatters the same ~900 cells across dozens of sheets, and
 * zooming out multiplies the cell count on top of that. Whenever the working
 * set outgrows the cache a plain LRU degenerates into thrash — each frame
 * evicts a sheet the next frame asks for again — and the tiles visibly blink
 * between crop and flat colour.
 *
 * The rule that avoids it: rank the sheets by how much of the screen each one
 * covers, hold exactly as many as the budget allows, and leave the rest flat.
 * Coverage that is partial but stable reads far better than coverage that is
 * complete but flickering.
 *
 * An earlier version held the frame's whole set or nothing at all, falling back
 * to the pure colour field past a hardcoded 14 sheets. That is a defensible
 * reading of the collection, but it is a cliff: the monochrome view — a
 * first-class view — sits at exactly 14 sheets on a 900-cell screenful, so any
 * repacking that redistributes those objects blanks it with no warning. Ranking
 * by coverage degrades one sheet at a time instead of all at once. */

const Atlas = (() => {
  /* Decoded sheets are the memory that matters — a 2016px sheet is 16 MB of
   * RGBA, so the budget buys ~15 of them, which covers a full screen at the
   * smallest cell size that still draws crops. In-flight sheets can overshoot
   * it by at most MAX_INFLIGHT before the next frame trims back. */
  const BUDGET = (navigator.deviceMemory && navigator.deviceMemory < 4)
    ? 96 * 1024 * 1024
    : 256 * 1024 * 1024;
  const MIN_RESIDENT = 4;
  const MAX_RESIDENT = 48;
  const MAX_INFLIGHT = 4;

  const S = {
    ready: false,
    index: null,
    sheets: new Map(),      // n -> {img, used} once decoded
    pending: new Set(),
    failed: new Set(),      // 404 or decode error — do not ask again every frame
    need: new Map(),        // n -> visible cells wanting it, this frame only
    keep: new Set(),        // the sheets this frame decided are worth holding
    clock: 0,
    cap: MIN_RESIDENT,
    onload: null,
  };

  async function load(onload) {
    S.onload = onload;
    let index;
    try {
      index = await fetch('data/atlas.json').then(r => (r.ok ? r.json() : null));
    } catch (e) {
      index = null;
    }
    if (!index) return false;

    // A stale atlas is worse than none: emit.py can reorder the base order,
    // which silently repoints every tile. Check the packing still describes
    // this payload before trusting a single pixel of it.
    const D = Data.state;
    if (index.count !== D.count || index.firstId !== D.id[0] || index.lastId !== D.id[D.count - 1]) {
      console.warn('atlas: packing does not match grid.bin — re-run pipeline/atlas.py');
      return false;
    }
    S.index = index;
    S.cap = capacity();
    S.ready = true;
    return true;
  }

  /* How many sheets fit the budget, read off the packing's own geometry rather
   * than hardcoded, so re-packing at a different tile size resizes the cache. */
  function capacity() {
    const px = S.index.cols * S.index.tile;
    const bytes = px * px * 4;
    return Math.max(MIN_RESIDENT, Math.min(MAX_RESIDENT, Math.floor(BUDGET / bytes)));
  }

  function beginFrame() { S.need.clear(); }

  /* Rank by coverage, keep the top of the ranking, evict from outside it first,
   * and fetch only what is being kept. Ranking by coverage rather than by
   * proximity to the viewport centre is what makes a scattered field behave:
   * the sheets holding the most visible cells win, whatever their number. */
  function endFrame() {
    if (!S.ready) return;

    const ranked = [...S.need.entries()]
      .sort((a, b) => (b[1] - a[1]) || (a[0] - b[0]))
      .map(e => e[0]);

    S.keep = new Set(ranked.slice(0, S.cap));

    // Unkept sheets are spent before kept ones, least recently drawn first. A
    // kept sheet is dropped only when nothing else remains, which is the case
    // a stable partial field rests on.
    while (S.sheets.size > S.cap) {
      let victim = null, victimRank = Infinity;
      for (const [n, sheet] of S.sheets) {
        const rank = (S.keep.has(n) ? 1e15 : 0) + sheet.used;
        if (rank < victimRank) { victimRank = rank; victim = n; }
      }
      if (victim === null) break;
      S.sheets.delete(victim);
    }

    for (const n of ranked) {
      if (S.pending.size >= MAX_INFLIGHT) break;
      if (!S.keep.has(n) || S.sheets.has(n) || S.pending.has(n) || S.failed.has(n)) continue;
      request(n);
    }
  }

  function request(n) {
    S.pending.add(n);
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => {
      S.pending.delete(n);
      S.sheets.set(n, { img, used: ++S.clock });
      if (S.onload) S.onload();
    };
    // Remember the failure. Without this a missing sheet is re-requested on
    // every single frame, forever, because nothing else records that it was
    // ever tried.
    img.onerror = () => { S.pending.delete(n); S.failed.add(n); };
    img.src = 'data/atlas/' + String(n).padStart(3, '0') + '.webp';
  }

  /* Where object i lives, or null if its sheet is not resident — in which case
   * the caller draws flat colour this frame. The want is recorded either way;
   * endFrame decides what to do about it. */
  function tile(i) {
    if (!S.ready) return null;
    const per = S.index.perSheet;
    const n = (i / per) | 0;
    S.need.set(n, (S.need.get(n) || 0) + 1);
    const sheet = S.sheets.get(n);
    if (!sheet) return null;
    sheet.used = ++S.clock;
    const k = i % per;
    const t = S.index.tile;
    return {
      img: sheet.img,
      sx: (k % S.index.cols) * t,
      sy: ((k / S.index.cols) | 0) * t,
      size: t,
    };
  }

  /* The source rectangle that fills a dw x dh destination without distorting
   * the crop — the lattices are not all square, and a stretched pot is worse
   * than a cropped one. */
  function cover(size, dw, dh) {
    const ar = dw / dh;
    let sw = size, sh = size;
    if (ar > 1) sh = size / ar; else sw = size * ar;
    return [(size - sw) / 2, (size - sh) / 2, sw, sh];
  }

  return { load, beginFrame, endFrame, tile, cover, state: S };
})();
