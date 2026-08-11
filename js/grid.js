/* grid.js — the colour field.
 *
 * Two concerns stay separate, which is what makes the lattice wheel cheap:
 *   order   an index array produced by the sort and the filters
 *   lattice a pure function index -> {x, y, shape}
 * Turning the wheel swaps the lattice only, so the colour sweep survives a
 * layout change untouched.
 *
 * Everything is drawn to one canvas. At 44k objects the DOM is not a
 * candidate; a full field repaint touches only the rows on screen. */

const Grid = (() => {
  const MAX_CELL = 120;      // above this a 96px tile would visibly soften
  const OVERVIEW_CELL = 14;  // below this, shape and gutter stop meaning anything

  const G = {
    cell: 40, cellT: 40, scroll: 0, totalH: 1,
    lattice: 1, index: null, hoverK: -1, overview: false,
    dirty: true, animMap: null, animT0: 0,
    W: 1440, H: 900,
    gutter: true, reducedMotion: false,
    on: {},
  };

  let cv, ctx, raf, lastFrac = -1;

  /* --- lattice ---------------------------------------------------------- */

  function geom() {
    const s = G.cell, W = G.W;
    const lat = G.cell <= OVERVIEW_CELL ? 1 : G.lattice;
    if (lat === 0) return { lat, colW: s * 0.75, rowH: s, cols: Math.max(1, Math.ceil(W / (s * 0.75))) };
    if (lat === 1) return { lat, colW: s, rowH: s, cols: Math.max(1, Math.ceil(W / s)) };
    if (lat === 2) return { lat, colW: s, rowH: s / 2, cols: Math.ceil(W / s) + 1 };
    return { lat, colW: s, rowH: s * 0.866, cols: Math.ceil(W / s) + 1 };
  }

  function posOf(k, g) {
    const row = Math.floor(k / g.cols), col = k % g.cols;
    const off = (g.lat >= 2 && (row & 1)) ? g.colW / 2 : 0;
    return [col * g.colW - (g.lat >= 2 ? g.colW / 2 : 0) + off, row * g.rowH];
  }

  function blit(t, bx, by, bw, bh) {
    const c = Atlas.cover(t.size, bw, bh);
    ctx.drawImage(t.img, t.sx + c[0], t.sy + c[1], c[2], c[3], bx, by, bw, bh);
  }

  /* Draw one cell: the crop if its sheet is resident, otherwise the flat
   * colour. Both take the lattice's shape — the square and rectangle lattices
   * need no clip, the diamond and hexagon clip the blit to the path they
   * would otherwise have filled. */
  function paint(g, x, y, t) {
    const s = G.cell, gp = (G.gutter && s > OVERVIEW_CELL) ? 1 : 0;

    if (g.lat === 1 || g.lat === 0 || s <= OVERVIEW_CELL) {
      let bx, by, bw, bh;
      if (gp) {
        bx = x + gp; by = y + gp; bw = g.colW - gp * 2; bh = g.rowH - gp * 2;
      } else {
        // Cell size is fractional at the overview tier, and a fractional
        // fillRect antialiases its edges -- 229 rows of that reads as pale
        // banding across the whole collection. Snap to whole pixels so the
        // swatches tile exactly.
        const x0 = Math.round(x), y0 = Math.round(y);
        bx = x0; by = y0;
        bw = Math.round(x + g.colW) - x0;
        bh = Math.round(y + g.rowH) - y0;
      }
      if (t) blit(t, bx, by, bw, bh); else ctx.fillRect(bx, by, bw, bh);
      return;
    }

    if (g.lat === 2) {
      const cx = x + s / 2, cy = y;
      ctx.beginPath();
      ctx.moveTo(cx, cy - s / 2 + gp);
      ctx.lineTo(cx + s / 2 - gp, cy);
      ctx.lineTo(cx, cy + s / 2 - gp);
      ctx.lineTo(cx - s / 2 + gp, cy);
      ctx.closePath();
      if (t) {
        ctx.save(); ctx.clip();
        blit(t, x + gp, cy - s / 2 + gp, s - gp * 2, s - gp * 2);
        ctx.restore();
      } else ctx.fill();
      return;
    }

    const hh = s * 0.5774, cx = x + s / 2, cy = y + s * 0.5774;
    ctx.beginPath();
    ctx.moveTo(cx, cy - hh);
    ctx.lineTo(cx + s / 2 - gp, cy - hh / 2);
    ctx.lineTo(cx + s / 2 - gp, cy + hh / 2);
    ctx.lineTo(cx, cy + hh);
    ctx.lineTo(cx - s / 2 + gp, cy + hh / 2);
    ctx.lineTo(cx - s / 2 + gp, cy - hh / 2);
    ctx.closePath();
    if (t) {
      ctx.save(); ctx.clip();
      blit(t, x + gp, cy - hh, s - gp * 2, hh * 2);
      ctx.restore();
    } else ctx.fill();
  }

  const shape = (g, x, y) => paint(g, x, y, null);

  function hitTest(x, y) {
    if (!G.index || !G.index.length) return -1;
    const g = geom(), sy = y + G.scroll;
    const row = Math.floor(sy / g.rowH);
    if (row < 0) return -1;
    const off = (g.lat >= 2 && (row & 1)) ? g.colW / 2 : 0;
    const col = Math.floor((x + (g.lat >= 2 ? g.colW / 2 : 0) - off) / g.colW);
    if (col < 0 || col >= g.cols) return -1;
    const k = row * g.cols + col;
    return k < G.index.length ? k : -1;
  }

  /* Remember where every visible object currently sits, so that a filter or a
   * lattice change can be a re-flow rather than a jump. */
  function captureVisible() {
    const map = new Map();
    if (!G.index) return map;
    const g = geom();
    const r0 = Math.max(0, Math.floor(G.scroll / g.rowH) - 1);
    const r1 = Math.ceil((G.scroll + G.H) / g.rowH) + 1;
    for (let row = r0; row <= r1; row++) {
      for (let col = 0; col < g.cols; col++) {
        const k = row * g.cols + col;
        if (k >= G.index.length) break;
        const p = posOf(k, g);
        map.set(G.index[k], [p[0], p[1] - G.scroll]);
      }
    }
    return map;
  }

  /* The cell size at which the whole current selection fits one screen. */
  function fitCell() {
    const n = G.index ? G.index.length : 1;
    let s = Math.sqrt(G.W * G.H / Math.max(1, n));
    let guard = 0;
    while (s > 2 && Math.ceil(n / Math.ceil(G.W / s)) * s > G.H && guard++ < 200) s *= 0.985;
    return Math.max(2, s);
  }

  /* --- index and lattice changes ---------------------------------------- */

  function setIndex(next, animate) {
    const frac = G.totalH > 1 ? (G.scroll + G.H / 2) / G.totalH : 0;
    const map = (animate && !G.reducedMotion) ? captureVisible() : null;
    G.index = next;
    const g = geom();
    G.totalH = Math.max(1, Math.ceil(next.length / g.cols) * g.rowH);
    G.scroll = frac > 0 ? Math.max(0, frac * G.totalH - G.H / 2) : 0;
    if (map) { G.animMap = map; G.animT0 = performance.now(); }
    G.dirty = true;
  }

  /* Density differs per lattice, so preserve the object at the centre of the
   * viewport rather than the pixel offset — otherwise the dial teleports you. */
  function setLattice(lat) {
    if (lat === G.lattice) return;
    const map = G.reducedMotion ? null : captureVisible();
    const centreK = hitTest(G.W / 2, G.H / 2);
    G.lattice = lat;
    const g = geom();
    if (centreK >= 0) {
      G.scroll = Math.max(0, Math.floor(centreK / g.cols) * g.rowH + g.rowH / 2 - G.H / 2);
    }
    if (map) { G.animMap = map; G.animT0 = performance.now(); }
    G.dirty = true;
  }

  function zoomTo(cell) {
    G.cellT = Math.min(MAX_CELL, Math.max(fitCell(), cell));
    G.dirty = true;
  }

  /* --- frame ------------------------------------------------------------ */

  function tick() {
    if (Math.abs(G.cell - G.cellT) > 0.05) {
      const old = G.cell;
      G.cell += (G.cellT - G.cell) * (G.reducedMotion ? 1 : 0.16);
      const f = G.cell / old;
      G.scroll = Math.max(0, (G.scroll + G.H / 2) * f - G.H / 2);
      const g = geom();
      G.totalH = Math.max(1, Math.ceil((G.index ? G.index.length : 0) / g.cols) * g.rowH);
      G.dirty = true;
      const ov = G.cell <= OVERVIEW_CELL;
      if (ov !== G.overview) { G.overview = ov; emit('overview', ov); }
    }
    if (G.animMap && performance.now() - G.animT0 < 520) G.dirty = true;
    if (G.dirty) { G.dirty = false; draw(); }
    raf = requestAnimationFrame(tick);
  }

  function draw() {
    if (!ctx || !G.index) return;
    const W = G.W, H = G.H;
    ctx.fillStyle = '#F3F1EC';
    ctx.fillRect(0, 0, W, H);
    const idx = G.index;
    if (!idx.length) return;

    const g = geom();
    const totalRows = Math.ceil(idx.length / g.cols);
    G.totalH = Math.max(1, totalRows * g.rowH);
    const maxS = Math.max(0, G.totalH - H);
    if (G.scroll > maxS) G.scroll = maxS;
    if (G.scroll < 0) G.scroll = 0;

    const r0 = Math.max(0, Math.floor(G.scroll / g.rowH) - 2);
    const r1 = Math.min(totalRows - 1, Math.ceil((G.scroll + H) / g.rowH) + 2);

    let at = 1;
    if (G.animMap) {
      at = Math.min(1, (performance.now() - G.animT0) / 480);
      if (at >= 1) G.animMap = null;
    }
    const ease = 1 - Math.pow(1 - at, 3);
    const colors = Data.state.colors;
    // Below the overview threshold a 96px crop is a rounding error, and
    // loading sheets to draw it would be absurd — the whole collection on one
    // screen is a colour reading by definition.
    const tiles = G.cell > OVERVIEW_CELL && Atlas.state.ready;

    let hx = -1, hy = -1;
    const hk = G.hoverK;
    for (let row = r0; row <= r1; row++) {
      for (let col = 0; col < g.cols; col++) {
        const k = row * g.cols + col;
        if (k >= idx.length) break;
        const o = idx[k];
        const p = posOf(k, g);
        let x = p[0], y = p[1] - G.scroll;
        if (at < 1 && G.animMap && G.animMap.has(o)) {
          const q = G.animMap.get(o);
          x = q[0] + (x - q[0]) * ease;
          y = q[1] + (y - q[1]) * ease;
        }
        ctx.fillStyle = colors[o];
        paint(g, x, y, tiles ? Atlas.tile(o) : null);
        if (k === hk && G.cell > OVERVIEW_CELL) { hx = x; hy = y; }
      }
    }
    if (hx > -1) { ctx.fillStyle = 'rgba(255,255,255,0.38)'; shape(g, hx, hy); }

    const sf = maxS > 0 ? Math.min(1, G.scroll / maxS) : 0;
    if (Math.abs(sf - lastFrac) > 0.003) { lastFrac = sf; emit('scroll', sf); }
  }

  function emit(name, value) { if (G.on[name]) G.on[name](value); }

  /* --- input ------------------------------------------------------------ */

  function init(canvas, handlers) {
    cv = canvas;
    G.on = handlers || {};
    G.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const resize = () => {
      const d = window.devicePixelRatio || 1;
      G.W = window.innerWidth;
      G.H = window.innerHeight;
      cv.width = G.W * d;
      cv.height = G.H * d;
      ctx = cv.getContext('2d');
      ctx.setTransform(d, 0, 0, d, 0, 0);
      G.dirty = true;
      emit('resize');
    };
    resize();
    window.addEventListener('resize', resize);

    window.addEventListener('wheel', (e) => {
      if (G.on.blocked && G.on.blocked()) return;
      if (e.target.closest && e.target.closest('[data-mod]')) return;
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) zoomTo(G.cellT * Math.exp(-e.deltaY * 0.0022));
      else G.scroll += e.deltaY;
      G.dirty = true;
    }, { passive: false });

    window.addEventListener('mousemove', (e) => {
      if (e.target !== cv) {
        if (G.hoverK !== -1) { G.hoverK = -1; G.dirty = true; }
        return;
      }
      const k = hitTest(e.clientX, e.clientY);
      if (k !== G.hoverK) { G.hoverK = k; G.dirty = true; }
    });

    window.addEventListener('click', (e) => {
      if (e.target !== cv) return;
      const k = hitTest(e.clientX, e.clientY);
      if (k >= 0) emit('open', k);
    });

    raf = requestAnimationFrame(tick);
  }

  function scrollToFraction(f) {
    G.scroll = f * Math.max(0, G.totalH - G.H);
    G.dirty = true;
  }

  function page(dir) {
    G.scroll = Math.max(0, G.scroll + dir * G.H * 0.8);
    G.dirty = true;
  }

  return {
    state: G, init, setIndex, setLattice, zoomTo, fitCell,
    scrollToFraction, page, geom, hitTest,
    MAX_CELL, OVERVIEW_CELL,
  };
})();
