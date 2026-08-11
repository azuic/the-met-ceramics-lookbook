/* ui.js — the paper furniture floating over the field.
 *
 * Nodes are built once and updated in place, so the wheel's transform
 * transition and the receipt's tear survive a state change. */

const UI = (() => {
  const { el, fill } = DOM;
  const SORTS = ['Chroma', 'Material', 'Department', 'Date'];
  const NOTES = [
    'Kept verbatim — “as catalogued” is the museum’s own word for it',
    'Nine departments carry 98% — eight small ones share the last row',
  ];

  let S, act, n = {};

  function q(id) { return document.getElementById(id); }

  function init(state, actions) {
    S = state;
    act = actions;
    n = {
      ui: q('ui'), total: q('totalObjects'),
      sortPanel: q('sortPanel'), sortHead: q('sortHead'), sortCurrent: q('sortCurrent'), sortBody: q('sortBody'),
      catPanel: q('catPanel'), catBody: q('catBody'), catRows: q('catRows'),
      tabMat: q('tabMat'), tabDep: q('tabDep'), tabNote: q('tabNote'),
      monoBtn: q('monoBtn'), monoCount: q('monoCount'),
      wheelWrap: q('wheelWrap'), glazeRing: q('glazeRing'), ringThumb: q('ringThumb'),
      wheelHit: q('wheelHit'), wheelRing: q('wheelRing'), glyphs: q('glyphs'),
      receipt: q('receipt'), receiptDate: q('receiptDate'), receiptLines: q('receiptLines'),
      receiptFoot: q('receiptFoot'), countText: q('countText'), stub: q('stub'),
      seeAll: q('seeAll'), empty: q('empty'), emptyReset: q('emptyReset'),
    };

    const meta = Data.state.meta;
    n.total.textContent = (meta.scanned || meta.count).toLocaleString();
    n.monoCount.textContent = meta.monoCount.toLocaleString();
    n.receiptFoot.textContent =
      meta.count.toLocaleString() + ' of ' + (meta.scanned || meta.count).toLocaleString() + ' passed crop QC';
    n.receiptDate.textContent = new Date().toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
    }).toUpperCase();

    // The palette ring: the ten glaze families, in order, as one sweep.
    const hexes = meta.families.map(f => f.hex);
    n.glazeRing.style.background =
      'conic-gradient(from 0deg,' + hexes.join(',') + ',' + hexes[0] + ')';

    n.sortHead.addEventListener('click', () => act.set({ sortOpen: !S.sortOpen }));
    n.tabMat.addEventListener('click', () => act.openTab(0));
    n.tabDep.addEventListener('click', () => act.openTab(1));
    n.monoBtn.addEventListener('click', act.toggleMono);
    n.stub.addEventListener('click', act.tear);
    n.emptyReset.addEventListener('click', act.tear);
    n.seeAll.addEventListener('click', act.seeAll);
    n.glazeRing.addEventListener('pointerdown', ringScrub);
    n.wheelHit.addEventListener('pointerdown', wheelDown);

    buildSortRows();
    buildGlyphs();
    scale();
    window.addEventListener('resize', scale);
  }

  /* One transform keeps the modules proportional on short viewports. Children
   * are position:fixed, which resolves against this transformed ancestor. */
  function scale() {
    const k = Math.min(1, window.innerHeight / 780);
    n.ui.style.width = (100 / k).toFixed(3) + '%';
    n.ui.style.height = (100 / k).toFixed(3) + '%';
    n.ui.style.transform = 'scale(' + k.toFixed(4) + ')';
  }

  function buildSortRows() {
    fill(n.sortBody, SORTS.map((name, i) => el('div', {
      class: 'row', onclick: () => act.setSort(i),
    }, [
      el('span', { text: name }),
      el('span', { class: 'dot' }),
    ])));
  }

  function buildGlyphs() {
    // Rectangle, square, diamond, hexagon — how real tile sample books lay out.
    const shapes = [
      'width:11px;height:15px;border:1.5px solid ',
      'width:13px;height:13px;background:',
      'width:11px;height:11px;transform:rotate(45deg);background:',
      'width:14px;height:16px;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);background:',
    ];
    fill(n.glyphs, shapes.map((css, i) => el('div', {
      class: 'glyph',
      onclick: () => {
        if (n.wheelHit.dataset.dragged === '1') return;
        const cur = S.wheelAngle;
        const d = (((-90 * i - cur) % 360) + 540) % 360 - 180;
        act.setLattice(i, cur + d);
      },
    }, [el('div', { 'data-css': css })])));
  }

  /* The ring doubles as the scrollbar: drag anywhere on the palette to travel. */
  function ringScrub(e) {
    e.preventDefault();
    e.stopPropagation();
    const r = n.glazeRing.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const to = (px, py) => {
      const a = Math.atan2(py - cy, px - cx) * 180 / Math.PI;
      act.scrub(((((a + 90) % 360) + 360) % 360) / 360);
    };
    to(e.clientX, e.clientY);
    const move = ev => to(ev.clientX, ev.clientY);
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  /* Turning the wheel is continuous; letting go snaps to the nearest detent. */
  function wheelDown(e) {
    e.preventDefault();
    const r = n.wheelHit.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const a0 = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI;
    const start = S.wheelAngle;
    n.wheelHit.dataset.dragged = '0';
    act.set({ dragging: true });
    const move = (ev) => {
      const a = Math.atan2(ev.clientY - cy, ev.clientX - cx) * 180 / Math.PI;
      const d = a - a0;
      if (Math.abs(d) > 3) n.wheelHit.dataset.dragged = '1';
      act.set({ wheelAngle: start + d });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      const snapped = Math.round(S.wheelAngle / 90) * 90;
      act.set({ dragging: false });
      act.setLattice(((((-snapped / 90) % 4) + 4) % 4), snapped);
      setTimeout(() => { n.wheelHit.dataset.dragged = '0'; }, 50);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  function catalogueRows() {
    const meta = Data.state.meta;
    if (S.tab === 0) {
      return meta.materials.map((m, i) => row(
        m.name, m.count.toLocaleString(), S.mat.includes(i),
        () => act.toggleMat(i), 12.5
      ));
    }
    return meta.departments.map((d, i) => row(
      d.name, d.note || d.count.toLocaleString(), S.dep.includes(i),
      () => act.toggleDep(i), 11.5
    ));
  }

  function row(name, count, active, onclick, size) {
    return el('div', { class: 'row', onclick }, [
      el('span', {
        style: "font-family:'Libre Baskerville',Georgia,serif;line-height:1.3;font-size:" + size +
          'px;color:' + (active ? '#262623' : '#6E6C64'),
        text: name,
      }),
      el('span', { style: 'display:flex;align-items:center;gap:7px' }, [
        el('span', { class: 'count', text: count }),
        el('span', { class: 'dot' + (active ? ' on' : '') }),
      ]),
    ]);
  }

  let builtTab = -1, builtSel = '';

  function update() {
    const meta = Data.state.meta;

    n.sortCurrent.textContent = SORTS[S.sort].toLowerCase();
    n.sortBody.hidden = !S.sortOpen;
    Array.from(n.sortBody.children).forEach((r, i) => {
      r.firstChild.style.cssText =
        "font-family:'Libre Baskerville',Georgia,serif;font-size:12px;color:" +
        (i === S.sort ? '#262623' : '#928F86');
      r.lastChild.className = 'dot' + (i === S.sort ? ' on' : '');
    });

    // The catalogue panel sits under the sort panel and moves when it opens.
    n.catPanel.style.top = (S.sortOpen ? 216 : 82) + 'px';
    n.catBody.hidden = !S.catOpen;
    n.tabMat.className = 'tab' + (S.catOpen && S.tab === 0 ? ' on' : '');
    n.tabDep.className = 'tab' + (S.catOpen && S.tab === 1 ? ' on' : '');
    n.tabNote.textContent = NOTES[S.tab];

    const sel = S.tab + '|' + S.mat.join(',') + '|' + S.dep.join(',');
    if (sel !== builtSel || S.tab !== builtTab) {
      builtSel = sel;
      builtTab = S.tab;
      fill(n.catRows, catalogueRows());
    }

    n.monoBtn.textContent = S.monoOnly ? 'Back' : 'Show';
    n.monoBtn.style.cssText =
      'flex:none;padding:5px 10px;border:1px solid ' + (S.monoOnly ? '#262623' : '#BAB6AC') +
      ';font-size:8px;letter-spacing:0.18em;text-transform:uppercase;color:' +
      (S.monoOnly ? '#262623' : '#928F86');

    // Wheel: the ring turns, the glyphs counter-rotate so they stay upright.
    n.wheelRing.classList.toggle('settling', !S.dragging);
    n.wheelRing.style.transform = 'rotate(' + S.wheelAngle + 'deg)';
    Array.from(n.glyphs.children).forEach((g, i) => {
      g.style.transform =
        'rotate(' + (i * 90) + 'deg) translateY(-53px) rotate(' + (-i * 90 - S.wheelAngle) + 'deg)';
      const shape = g.firstChild;
      shape.style.cssText = shape.dataset.css + (S.lattice === i ? '#262623' : '#BAB6AC');
    });
    n.ringThumb.style.transform =
      'rotate(' + (S.scrollFrac * 360).toFixed(1) + 'deg) translateY(-93px)';
    n.wheelWrap.classList.toggle('faded', S.overview);

    const lines = [
      ['Material', S.mat.length ? S.mat.map(i => meta.materials[i].name).join(' + ') : 'all, as catalogued'],
      ['Dept', S.dep.length ? S.dep.map(i => meta.departments[i].short).join(' + ') : 'all 17'],
    ];
    if (S.monoOnly) lines.push(['Showing', 'never photographed in colour']);
    fill(n.receiptLines, lines.map(([k, v]) => el('div', { class: 'line' }, [
      el('span', { class: 'k', text: k }),
      el('span', { class: 'v', text: v }),
    ])));
    n.countText.textContent = S.count.toLocaleString();

    const hasFilters = S.mat.length > 0 || S.dep.length > 0 || S.monoOnly;
    n.stub.hidden = !hasFilters;
    n.stub.classList.toggle('tearing', S.tearing);

    n.seeAll.textContent = S.overview ? 'Return to the shelf' : 'See everything';
    n.empty.hidden = S.count !== 0;
  }

  return { init, update };
})();
