/* atlas.js — the crops, packed into sheets and fetched as they are needed.
 *
 * A sheet costs width x height x 4 bytes once decoded, so they are never all
 * resident: the least recently drawn sheet is dropped past a cap. Anything not
 * yet loaded draws as the object's flat colour, which is what the field would
 * have shown anyway, so nothing ever waits on a network round trip. */

const Atlas = (() => {
  // ~16 MB decoded per 2016px sheet. 14 is chosen to clear the monochrome
  // view, which is a first-class view and spans 9 sheets on a 900px viewport
  // and more on a taller one; beyond this the field falls back to colour.
  const MAX_RESIDENT = 14;
  const MAX_INFLIGHT = 4;

  const S = {
    ready: false,
    index: null,
    sheets: new Map(),      // n -> img, once decoded
    pending: new Set(),
    wanted: new Set(),      // the sheets this frame's viewport needs
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
    S.ready = true;
    return true;
  }

  function request(n) {
    if (S.pending.size >= MAX_INFLIGHT || S.pending.has(n)) return;
    S.pending.add(n);
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => {
      S.pending.delete(n);
      S.sheets.set(n, img);
      if (S.onload) S.onload();
    };
    img.onerror = () => { S.pending.delete(n); };
    img.src = 'data/atlas/' + String(n).padStart(3, '0') + '.webp';
  }

  /* The residency rule.
   *
   * Evicting by least-recently-used looks reasonable and is exactly wrong
   * here: a filtered view scatters its objects across far more sheets than can
   * be held, so every frame evicts sheets the next frame wants, and the field
   * blinks between crop and colour forever. Instead the viewport states which
   * sheets it needs, and that set is held whole or not at all.
   *
   * Declare the frame's needs with needBegin/need, then call needCommit: it
   * returns false when the view is too scattered to stream, and the caller
   * draws the colour field instead — which is a true reading of the
   * collection, not a degraded one. Zooming in narrows the span and the crops
   * come back. */
  function needBegin() { S.wanted.clear(); }

  function need(i) {
    if (S.ready) S.wanted.add((i / S.index.perSheet) | 0);
  }

  function needCommit() {
    if (!S.ready || S.wanted.size > MAX_RESIDENT) return false;
    for (const n of Array.from(S.sheets.keys())) {
      if (!S.wanted.has(n)) S.sheets.delete(n);
    }
    for (const n of S.wanted) {
      if (!S.sheets.has(n)) request(n);
    }
    return true;
  }

  /* Where object i lives, or null if its sheet is not resident. A pure
   * lookup: residency was already decided for this frame. */
  function tile(i) {
    if (!S.ready) return null;
    const per = S.index.perSheet;
    const img = S.sheets.get((i / per) | 0);
    if (!img) return null;
    const k = i % per;
    const t = S.index.tile;
    return {
      img,
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

  return { load, tile, cover, needBegin, need, needCommit, state: S };
})();
