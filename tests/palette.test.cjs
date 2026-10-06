const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(file, name) {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'js', file), 'utf8'), context);
  return vm.runInContext(name, context);
}

const PaletteRing = load('palette.js', 'PaletteRing');
const stops = gradient => Array.from(gradient.matchAll(/rgb\((\d+),(\d+),(\d+)\) ([\d.]+)%/g),
  m => ({ colour: m.slice(1, 4).map(Number), at: Number(m[4]) }));

test('colour proportions follow an uneven collection instead of equal family slices', () => {
  const rgb = new Uint8Array(100 * 3);
  for (let i = 0; i < 100; i++) rgb.set(i < 5 ? [38, 58, 140] : [188, 106, 72], i * 3);
  const result = stops(PaletteRing.gradient(Int32Array.from({ length: 100 }, (_, i) => i), rgb));
  assert.deepEqual(result.find(s => s.at === 4.5).colour, [38, 58, 140]);
  assert.deepEqual(result.find(s => s.at === 5.5).colour, [188, 106, 72]);
  assert.deepEqual(result.find(s => s.at === 25.5).colour, [188, 106, 72]);
  assert.equal(result[0].at, 0);
  assert.equal(result.at(-1).at, 100);
});

test('filtered and reordered indices determine every colour stop, including monochrome', () => {
  const rgb = Uint8Array.from([38, 58, 140, 188, 106, 72, 180, 180, 180]);
  const result = stops(PaletteRing.gradient(Int32Array.from([1, 2, 0]), rgb));
  assert.deepEqual(result.slice(1, -1).map(s => s.colour), [
    [188, 106, 72], [180, 180, 180], [38, 58, 140],
  ]);
  const filtered = stops(PaletteRing.gradient(Int32Array.from([2]), rgb));
  assert.ok(filtered.every(s => s.colour.every(channel => channel === 180)));
  assert.equal(PaletteRing.gradient(new Int32Array(), rgb), 'none');
});

test('large colour maps stay bounded and average the actual crop colours', () => {
  const count = 36000;
  const index = Int32Array.from({ length: count }, (_, i) => i);
  const rgb = new Uint8Array(count * 3);
  for (let i = 0; i < count; i++) rgb.set(i % 2 ? [200, 100, 50] : [100, 50, 0], i * 3);
  const result = stops(PaletteRing.gradient(index, rgb));
  assert.equal(result.length, 182, '180 bins plus the two seam endpoints');
  assert.ok(result.every(s => String(s.colour) === '150,75,25'));
});

function grid(count, options = {}) {
  const grid = load('grid.js', 'Grid');
  Object.assign(grid.state, { W: 100, H: 100, cell: 20, cellT: 20,
    lattice: 1, index: Int32Array.from({ length: count }, (_, i) => i), ...options });
  return grid;
}

test('scrubbing centres the addressed colour at every lattice and clamps at the ends', () => {
  for (let lattice = 0; lattice < 4; lattice++) {
    const g = grid(500, { lattice });
    g.scrollToFraction(.25);
    const range = g.visibleRange();
    assert.ok(Math.abs(range.start + range.span / 2 - .25) < 1e-9);
    g.scrollToFraction(0);
    assert.equal(g.visibleRange().start, 0);
    g.scrollToFraction(1);
    const end = g.visibleRange();
    assert.ok(Math.abs(end.start + end.span - 1) < 1e-9);
  }
});

test('visible range excludes the empty slots in a partial last row', () => {
  const g = grid(103);
  g.scrollToFraction(1);
  const range = g.visibleRange();
  assert.equal(range.start, 80 / 103);
  assert.ok(Math.abs(range.span - 23 / 103) < 1e-9);
  assert.ok(Math.abs(range.start + range.span - 1) < 1e-9);
});

test('short and empty selections cover the ring; close zoom reports its true narrow range', () => {
  for (const count of [0, 1, 10]) {
    const g = grid(count);
    g.scrollToFraction(.7);
    assert.equal(g.visibleRange().start, 0);
    assert.equal(g.visibleRange().span, 1);
  }
  const g = grid(40000);
  assert.equal(g.visibleRange().span, 25 / 40000);
});
