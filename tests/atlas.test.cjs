const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'data/atlas.json')));

async function setup({ memory = 8, index = manifest } = {}) {
  const requests = [];
  let invalidations = 0;
  class Image {
    set src(url) { this.url = url; requests.push(this); }
  }
  const context = vm.createContext({
    navigator: { deviceMemory: memory }, Image, console: { warn() {} },
    Data: { state: { count: manifest.count, id: {0:manifest.firstId, [manifest.count - 1]:manifest.lastId} } },
    fetch: async () => ({ok:true, json:async () => index}),
  });
  vm.runInContext(fs.readFileSync(path.join(root, 'js/atlas.js'), 'utf8'), context);
  const atlas = vm.runInContext('Atlas', context);
  await atlas.load(() => invalidations++);
  const frame = (small, ids) => {
    atlas.beginFrame(small);
    const tiles = ids.map(i => atlas.tile(i));
    atlas.endFrame();
    return tiles;
  };
  return { atlas, requests, frame, invalidations: () => invalidations };
}

test('initial shelf requests only full crops; zoom-out shares four slots and stops large requests', async () => {
  const { atlas, requests, frame } = await setup();
  frame(false, [0, 441, 882, 1323, 1764]);
  assert.equal(requests.length, 4);
  assert.ok(requests.every(r => r.url.startsWith('data/atlas/')));
  const all = Array.from({length:manifest.count}, (_, i) => i);
  frame(true, all);
  assert.equal(requests.length, 4, 'both tiers use the same four slots');
  requests[0].onload();
  frame(true, all);
  assert.equal(requests.length, 5);
  assert.match(requests[4].url, /atlas-preview/);
  assert.equal(atlas.state.pending.size + atlas.state.preview.pending.size, 4);
});

test('overview eventually displays every object and reuses sheets across sorts and filters', async () => {
  const { atlas, requests, frame } = await setup();
  const all = Array.from({length:manifest.count}, (_, i) => i);
  let handled = 0;
  let tiles;
  for (let pass = 0; pass < 6; pass++) {
    tiles = frame(true, all);
    for (const req of requests.slice(handled)) req.onload();
    handled = requests.length;
  }
  assert.equal(requests.length, manifest.preview.sheets);
  assert.ok(tiles.every(t => t && t.size === 16));
  assert.ok(frame(true, all.reverse()).every(Boolean));
  assert.ok(frame(true, all.filter(i => i % 13 === 0)).every(Boolean));
  assert.equal(requests.length, manifest.preview.sheets, 'no refetch on filter/sort');
  assert.equal(atlas.state.pending.size, 0);
  const last = tiles[manifest.count - 1];
  const k = (manifest.count - 1) % manifest.preview.perSheet;
  assert.equal(last.sx, k % 64 * 16);
  assert.equal(last.sy, Math.floor(k / 64) * 16);
  // Cached thumbnails bridge the trip back in until a sharp crop arrives.
  const back = frame(false, [0]);
  assert.equal(back[0].size, 16);
  requests.at(-1).onload();
  assert.equal(frame(false, [0])[0].size, 96);
});

test('a failed preview releases the queue, stays a colour fallback, and does not retry every frame', async () => {
  const { atlas, requests, frame, invalidations } = await setup();
  const ids = Array.from({length:11}, (_, i) => i * 4096);
  frame(true, ids);
  requests[0].onerror();
  assert.equal(invalidations(), 1);
  frame(true, ids);
  assert.equal(requests.length, 5, 'the next sheet starts after the failure');
  assert.equal(requests.filter(r => r.url.endsWith('/000.webp')).length, 1);
  assert.equal(atlas.tile(0), null);
});

test('stale packing is rejected; older manifests without previews still work', async () => {
  const stale = await setup({index:{...manifest, firstId:0}});
  assert.equal(stale.atlas.state.ready, false);
  assert.equal(stale.atlas.tile(0), null);
  const old = {...manifest};
  delete old.preview;
  const { requests, frame } = await setup({index:old});
  assert.equal(frame(true, [0])[0], null);
  assert.equal(requests.length, 0);
  frame(false, [0]);
  assert.equal(requests.length, 1);
});

test('both decoded tiers fit the original memory budget on normal and low-memory devices', async () => {
  for (const memory of [2, 8]) {
    const { atlas } = await setup({memory});
    const budget = (memory < 4 ? 96 : 256) * 1024 * 1024;
    const resident = atlas.state.cap * (manifest.cols * manifest.tile) ** 2 * 4;
    assert.ok(resident + manifest.preview.decodedBytes <= budget);
    assert.ok(atlas.state.cap >= 1);
  }
});
