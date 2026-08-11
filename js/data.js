/* data.js — loads the emitted payload and answers everything the grid asks.
 *
 * grid.bin is columnar and 4-byte aligned, so each column becomes a typed
 * array view over the same buffer with no copying. Catalogue text lives in
 * shards that are only fetched when a tile is actually opened. */

const Data = (() => {
  const S = {
    ready: false,
    meta: null,
    count: 0,
    colors: null,   // '#rrggbb' per object, built once
    orders: {},     // sort id -> Int32Array, computed lazily
    shards: new Map(),
  };

  const VIEWS = {
    Uint8: (buf, off, n) => new Uint8Array(buf, off, n),
    Uint16: (buf, off, n) => new Uint16Array(buf, off, n),
    Uint32: (buf, off, n) => new Uint32Array(buf, off, n),
    Int16: (buf, off, n) => new Int16Array(buf, off, n),
  };

  const HEX = [];
  for (let i = 0; i < 256; i++) HEX.push(i.toString(16).padStart(2, '0'));

  async function load() {
    const meta = await fetch('data/meta.json').then(r => {
      if (!r.ok) throw new Error('meta.json ' + r.status);
      return r.json();
    });
    const buf = await fetch('data/grid.bin').then(r => {
      if (!r.ok) throw new Error('grid.bin ' + r.status);
      return r.arrayBuffer();
    });

    const n = meta.count;
    S.meta = meta;
    S.count = n;

    const col = (name, width) => {
      const spec = meta.layout[name];
      return VIEWS[spec.type](buf, spec.offset, n * width);
    };
    S.id = col('id', 1);
    S.rgb = col('rgb', 3);
    S.mat = col('mat', 1);
    S.dep = col('dep', 1);
    S.fam = col('fam', 1);
    S.mono = col('mono', 1);
    S.year = col('year', 1);

    // Colour geometry is stored quantised; the sorts want it back as it was
    // measured, so unpack once into floats rather than per comparison.
    const qL = col('L', 1), qC = col('C', 1), qH = col('h', 1);
    const sc = meta.scale;
    S.L = new Float32Array(n);
    S.C = new Float32Array(n);
    S.h = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      S.L[i] = qL[i] / sc.L;
      S.C[i] = qC[i] / sc.C;
      S.h[i] = qH[i] / sc.h;
    }

    const colors = new Array(n);
    for (let i = 0; i < n; i++) {
      const k = i * 3;
      colors[i] = '#' + HEX[S.rgb[k]] + HEX[S.rgb[k + 1]] + HEX[S.rgb[k + 2]];
    }
    S.colors = colors;
    S.ready = true;
    return S;
  }

  /* Sort is a precomputed index array, so switching one never refetches
   * anything.
   *
   * Key 0 is the default sweep, and it runs family-major in palette order --
   * cobalt, turquoise, celadon, copper green, terracotta, iron red, ochre,
   * lustre, cream, manganese -- then by hue and lightness inside each family.
   * That is what makes the palette ring legible as a scrollbar: where the
   * thumb sits on the ring is the glaze you are looking at. Sorting on raw
   * chroma instead buries the collection's colour behind its 30% of
   * near-achromatic buff, which is the opposite of the point. */
  function order(sort) {
    if (S.orders[sort]) return S.orders[sort];
    const n = S.count;
    const key = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      if (sort === 0) key[i] = S.fam[i] * 1e7 + S.h[i] * 1e3 + S.L[i];
      else if (sort === 1) key[i] = S.mat[i] * 1e7 + S.fam[i] * 1e5 + S.h[i] * 10;
      else if (sort === 2) key[i] = S.dep[i] * 1e7 + S.fam[i] * 1e5 + S.h[i] * 10;
      else key[i] = S.year[i];
    }
    const idx = new Int32Array(n);
    for (let i = 0; i < n; i++) idx[i] = i;
    // Int32Array.sort with a comparator is a stable-enough numeric sort and
    // avoids boxing 44k indices into a plain array.
    idx.sort((a, b) => key[a] - key[b]);
    S.orders[sort] = idx;
    return idx;
  }

  /* Catalogue text for one object, by its index in the base order. */
  async function detail(i) {
    const size = S.meta.shard;
    const n = Math.floor(i / size);
    if (!S.shards.has(n)) {
      const name = String(n).padStart(3, '0');
      S.shards.set(n, fetch('data/detail/' + name + '.json')
        .then(r => (r.ok ? r.json() : null))
        .catch(() => null));
    }
    const rows = await S.shards.get(n);
    const row = rows && rows[i % size];
    if (!row) return null;
    const [title, medium, date, culture, country, objectName, image] = row;
    return {
      title, medium, date, culture, country, objectName,
      image: !image ? '' : (image[0] === '!' ? image.slice(1) : S.meta.imagePrefix + image),
      url: 'https://www.metmuseum.org/art/collection/search/' + S.id[i],
    };
  }

  return { state: S, load, order, detail };
})();
