/* app.js — state, and the wiring between the field and the paper.
 *
 * Filters compose: material ∩ department ∩ colour-or-not. Changing any of them
 * rebuilds the index and hands it to the grid as a re-flow, so you watch the
 * collection contract rather than jump. */

const App = (() => {
  const S = {
    mat: [], dep: [], sort: 0, lattice: 1, monoOnly: false, tab: 0,
    sortOpen: false, catOpen: false, wheelAngle: -90, dragging: false,
    tearing: false, count: 0, scrollFrac: 0, overview: false, detailK: -1,
  };

  let buffer = null, prevCell = 0, tearTimer = 0;

  function set(patch) {
    Object.assign(S, patch);
    UI.update();
  }

  /* Rebuild the visible index from the current sort and filters. */
  function refresh(animate) {
    const D = Data.state;
    const ord = Data.order(S.sort);
    const mat = S.mat, dep = S.dep;
    const nMat = mat.length, nDep = dep.length;
    if (!buffer) buffer = new Int32Array(D.count);

    let m = 0;
    for (let j = 0; j < ord.length; j++) {
      const i = ord[j];
      // The monochrome set is a view of its own, not a filter alongside others:
      // either you are looking at the 15% that has no colour, or at the rest.
      if (S.monoOnly ? !D.mono[i] : D.mono[i]) continue;
      if (nMat) {
        let hit = false;
        for (let x = 0; x < nMat; x++) if (mat[x] === D.mat[i]) { hit = true; break; }
        if (!hit) continue;
      }
      if (nDep) {
        let hit = false;
        for (let x = 0; x < nDep; x++) if (dep[x] === D.dep[i]) { hit = true; break; }
        if (!hit) continue;
      }
      buffer[m++] = i;
    }

    Grid.setIndex(buffer.subarray(0, m), animate);
    set({ count: m });
  }

  function toggle(list, i) {
    const a = list.slice();
    const j = a.indexOf(i);
    if (j >= 0) a.splice(j, 1); else a.push(i);
    return a;
  }

  const actions = {
    set,
    setSort(i) {
      set({ sortOpen: false });
      if (i === S.sort) return;
      set({ sort: i });
      refresh(true);
    },
    openTab(t) {
      set(S.catOpen && S.tab === t ? { catOpen: false } : { catOpen: true, tab: t });
    },
    toggleMat(i) { set({ mat: toggle(S.mat, i) }); refresh(true); },
    toggleDep(i) { set({ dep: toggle(S.dep, i) }); refresh(true); },
    toggleMono() { set({ monoOnly: !S.monoOnly }); refresh(true); },
    setLattice(lat, angle) {
      set({ wheelAngle: angle });
      if (lat === S.lattice) return;
      Grid.setLattice(lat);
      set({ lattice: lat });
    },
    scrub(frac) { Grid.scrollToFraction(frac); },
    seeAll() {
      if (!S.overview) {
        prevCell = Grid.state.cellT;
        Grid.zoomTo(Grid.fitCell());
      } else {
        Grid.zoomTo(prevCell || 40);
      }
    },
    tear() {
      if (!(S.mat.length || S.dep.length || S.monoOnly) || tearTimer) return;
      set({ tearing: true });
      tearTimer = setTimeout(() => {
        tearTimer = 0;
        set({ mat: [], dep: [], monoOnly: false, tearing: false });
        refresh(true);
      }, 470);
    },
    step(d) {
      const k = S.detailK + d;
      if (k >= 0 && k < Grid.state.index.length) {
        S.detailK = k;
        Detail.open(Grid.state.index[k]);
      }
    },
  };

  function openAt(k) {
    S.detailK = k;
    Detail.open(Grid.state.index[k]);
  }

  function keys(e) {
    if (e.key === 'Escape') {
      if (Detail.isOpen()) { Detail.close(); S.detailK = -1; }
      return;
    }
    if (Detail.isOpen()) {
      if (e.key === 'ArrowLeft') actions.step(-1);
      if (e.key === 'ArrowRight') actions.step(1);
      return;
    }
    if (e.key === 'ArrowDown' || e.key === 'PageDown') Grid.page(1);
    if (e.key === 'ArrowUp' || e.key === 'PageUp') Grid.page(-1);
  }

  async function start() {
    const boot = document.getElementById('boot');
    try {
      await Data.load();
    } catch (err) {
      document.getElementById('bootNote').textContent =
        location.protocol === 'file:'
          ? 'Serve this over HTTP — run: python3 -m http.server'
          : 'Could not load data/ — run python3 pipeline/emit.py';
      console.error(err);
      return;
    }

    Detail.init(actions);
    UI.init(S, actions);
    Grid.init(document.getElementById('field'), {
      overview: (v) => set({ overview: v }),
      scroll: (f) => set({ scrollFrac: f }),
      open: openAt,
      blocked: () => Detail.isOpen(),
    });
    refresh(false);
    window.addEventListener('keydown', keys);
    boot.classList.add('gone');
    setTimeout(() => boot.remove(), 500);
  }

  return { start, state: S };
})();

App.start();
