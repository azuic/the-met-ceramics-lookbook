/* atlas.js — the crops, packed into sheets and fetched as they are needed.
 *
 * A sheet costs width x height x 4 bytes once decoded, so they are never all
 * resident: the least recently drawn sheet is dropped past a cap. Anything not
 * yet loaded draws as the object's flat colour, which is what the field would
 * have shown anyway, so nothing ever waits on a network round trip. */

const Atlas = (() => {
  const MAX_RESIDENT = 8;   // ~130 MB decoded at 2016px sheets
  const MAX_INFLIGHT = 4;

  const S = {
    ready: false,
    index: null,
    sheets: new Map(),      // n -> {img, used} once decoded
    pending: new Set(),
    clock: 0,
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

  function evict() {
    while (S.sheets.size > MAX_RESIDENT) {
      let oldest = null, oldestUsed = Infinity;
      for (const [n, sheet] of S.sheets) {
        if (sheet.used < oldestUsed) { oldestUsed = sheet.used; oldest = n; }
      }
      if (oldest === null) return;
      S.sheets.delete(oldest);
    }
  }

  function request(n) {
    if (S.pending.size >= MAX_INFLIGHT || S.pending.has(n)) return;
    S.pending.add(n);
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => {
      S.pending.delete(n);
      S.sheets.set(n, { img, used: ++S.clock });
      evict();
      if (S.onload) S.onload();
    };
    img.onerror = () => { S.pending.delete(n); };
    img.src = 'data/atlas/' + String(n).padStart(3, '0') + '.webp';
  }

  /* Where object i lives, or null if its sheet is not resident yet — in which
   * case the sheet is requested and the caller draws flat colour this frame. */
  function tile(i) {
    if (!S.ready) return null;
    const per = S.index.perSheet;
    const n = (i / per) | 0;
    const sheet = S.sheets.get(n);
    if (!sheet) { request(n); return null; }
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

  return { load, tile, cover, state: S };
})();
