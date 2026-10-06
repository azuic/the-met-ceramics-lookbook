const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/receipt.js'), 'utf8'), context);
const paper = vm.runInContext('ReceiptPaper', context);

test('the unbroken section stays pinned throughout the tear', () => {
  for (const p of [0, .2, .5, .85, .98]) {
    const g = paper.geometry(p);
    assert.ok(Math.abs(g.attached - 240 * (1 - p)) < 1e-10);
    for (const x of [0, g.attached / 2, g.attached]) {
      for (const y of [0, 18, 36]) {
        const v = g.point(x, y);
        assert.equal(v.x, x);
        assert.equal(v.y, y);
        assert.equal(v.normal, 1);
      }
    }
  }
});

test('the fold follows the tear point past the middle and to the far edge', () => {
  for (const p of [.25, .5, .75, .9, 1]) {
    const g = paper.geometry(p);
    const turned = g.point(g.attached + 24, 0);
    assert.ok(turned.normal < 0, `paper immediately behind the tear must turn over at ${p}`);
    assert.ok(turned.y > 0, 'the free edge folds downward');
  }
  const done = paper.geometry(1);
  assert.equal(done.attached, 0);
  assert.ok(done.point(24, 0).normal < 0, 'the left end must also be folded before departure');
});

test('exit movement and fading cannot start while any seam remains attached', () => {
  for (const p of [0, .5, .9, .9999]) {
    const g = paper.geometry(p, 1);
    assert.equal(g.exit, 0);
    assert.equal(g.travel, 0);
    assert.equal(g.settle, 0);
    assert.equal(g.opacity, 1);
  }
  assert.equal(paper.geometry(1, .5).exit, .5);
  assert.equal(paper.geometry(1, 1).exit, 1);
});

test('the detached roll recoils near the seam before fading', () => {
  const held = paper.geometry(1);
  const tip = held.point(240, 18);
  for (const departure of [.01, .1, .3, .6, 1]) {
    const g = paper.geometry(1, departure), released = g.point(240, 18);
    const displacement = Math.hypot(released.x - g.travel - tip.x,
      released.y + g.settle - tip.y);
    assert.ok(displacement < 12, 'the roll must not fly away after separating');
    assert.ok(g.opacity >= 0 && g.opacity <= 1);
  }
  assert.equal(paper.geometry(1, .1).opacity, 1, 'make the break visible before fading');
  assert.equal(paper.geometry(1, 1).opacity, 0);
});

test('peeled material gathers around the starting tip in one growing roll', () => {
  let previousRadius = 0;
  for (const p of [.2, .5, .85, 1]) {
    const g = paper.geometry(p);
    assert.ok(g.radius > previousRadius, 'the roll grows as it takes up paper');
    previousRadius = g.radius;
    const tip = g.point(240, 18);
    assert.ok(Math.hypot(tip.x - g.attached, tip.z - g.radius) < g.radius * .8,
      'the original starting tip stays inside the roll');
    for (let x = g.attached; x <= 240; x += 1) {
      const v = g.point(x, 18);
      assert.ok(Math.abs(v.x - g.attached) <= g.radius + 1e-10,
        'no peeled material extends out as a loose flap');
    }
  }
});

test('the paper surface stays finite at both endpoints and throughout the fold', () => {
  for (const p of [0, .001, .25, .5, .75, .999, 1]) {
    for (let x = 0; x <= 240; x += 6) {
      for (const y of [0, 18, 36]) {
        assert.ok(Object.values(paper.geometry(p).point(x, y)).every(Number.isFinite));
      }
    }
  }
});

test('a wider detail slip rolls through its full width with the same pinned seam', () => {
  const width = 410;
  for (const progress of [0, .2, .5, .85, 1]) {
    const g = paper.geometry(progress, 0, width);
    assert.ok(Math.abs(g.attached - width * (1 - progress)) < 1e-10);
    assert.equal(g.point(g.attached, 18).x, g.attached);
    assert.equal(g.point(g.attached, 18).y, 18);
    if (progress) assert.ok(Math.abs(g.point(width, 18).x - g.attached) <= g.radius);
  }
  assert.equal(paper.geometry(1, 0, width).attached, 0);
});
