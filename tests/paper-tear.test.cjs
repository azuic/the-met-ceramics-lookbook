const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup(reduced = false) {
  let now = 0, nextFrame = 0;
  const frames = new Map(), drawings = [];
  const context = vm.createContext({
    AbortController,
    window: { matchMedia: () => ({ matches: reduced }) },
    performance: { now: () => now },
    requestAnimationFrame: cb => { frames.set(++nextFrame, cb); return nextFrame; },
    cancelAnimationFrame: id => frames.delete(id),
    ReceiptPaper: { create: (canvas, options) => ({
      draw: (progress, departure = 0) => drawings.push({ canvas, width: options.width, progress, departure }),
    }) },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/paper-tear.js'), 'utf8'), context);
  const paper = vm.runInContext('PaperTear', context);
  function button(width = 240) {
    const node = new EventTarget(), classes = new Set(), attrs = new Map();
    Object.assign(node, {
      offsetWidth: width, hidden: false, canvas: {},
      classList: {
        add: (...items) => items.forEach(x => classes.add(x)),
        remove: (...items) => items.forEach(x => classes.delete(x)),
        toggle: (key, on) => on ? classes.add(key) : classes.delete(key),
        contains: key => classes.has(key),
      },
      querySelector: selector => selector === 'canvas' ? node.canvas : {},
      getBoundingClientRect: () => ({ width }),
      setAttribute: (key, value) => attrs.set(key, value),
      removeAttribute: key => attrs.delete(key),
      setPointerCapture: id => { node.capture = id; },
      hasPointerCapture: id => node.capture === id,
      releasePointerCapture: () => { node.capture = null; },
    });
    return node;
  }
  function fire(node, type, props = {}) {
    const event = new Event(type, { cancelable: true });
    Object.assign(event, { button: 0, pointerId: 1, isPrimary: true, clientX: 200, clientY: 20, detail: 1 }, props);
    node.dispatchEvent(event);
    return event;
  }
  async function advance(ms) {
    now += ms;
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach(cb => cb(now));
    await Promise.resolve();
  }
  return { paper, button, fire, advance, drawings, frames };
}

test('a short pull returns to rest without committing', async () => {
  const { paper, button, fire, advance, drawings } = setup();
  const node = button();
  let commits = 0;
  const control = paper.attach(node, { onCommit: () => commits++ });
  fire(node, 'pointerdown');
  fire(node, 'pointermove', { clientX: 190, clientY: 23 });
  fire(node, 'pointerup');
  fire(node, 'click');
  await advance(200);
  assert.equal(commits, 0);
  assert.equal(node.hidden, false);
  assert.equal(node.classList.contains('pulling'), false);
  assert.equal(drawings.at(-1).progress, 0);
  assert.equal(control.isActive(), false);
});

test('a full pull commits once, completes the seam, then releases', async () => {
  const { paper, button, fire, advance, drawings } = setup();
  const node = button(410);
  let commits = 0, completion;
  const control = paper.attach(node, { onCommit: () => { commits++; completion = control.tear(); } });
  fire(node, 'pointerdown');
  fire(node, 'pointermove', { clientX: 120, clientY: 25 });
  fire(node, 'pointerup');
  fire(node, 'click');
  await advance(400);
  assert.equal(node.hidden, false);
  assert.ok(drawings.every(d => !d.departure || d.progress === 1));
  await advance(600);
  assert.equal(await completion, true);
  assert.equal(commits, 1);
  assert.equal(node.hidden, true);
  assert.equal(drawings.at(-1).departure, 1);
  assert.ok(drawings.every(d => d.width === 410));
});

test('closing a detail cancels its release without affecting the receipt', async () => {
  const { paper, button, advance, drawings } = setup();
  const receipt = button(), detail = button(410);
  const a = paper.attach(receipt, { onCommit() {} });
  const b = paper.attach(detail, { onCommit() {} });
  const receiptDone = a.tear(), detailDone = b.tear();
  await advance(300);
  b.destroy();
  assert.equal(await detailDone, false);
  await advance(800);
  assert.equal(await receiptDone, true);
  assert.equal(receipt.hidden, true);
  assert.equal(detail.hidden, false);
  assert.equal(drawings.at(-1).canvas, receipt.canvas);
});

test('keyboard activation works with reduced motion; modified links retain native behaviour', async () => {
  const { paper, button, fire, frames } = setup(true);
  const node = button(410);
  let commits = 0, completion;
  const control = paper.attach(node, { onCommit: () => { commits++; completion = control.tear(); } });
  assert.equal(fire(node, 'click', { metaKey: true }).defaultPrevented, false);
  assert.equal(commits, 0);
  fire(node, 'click', { detail: 0 });
  assert.equal(await completion, true);
  assert.equal(commits, 1);
  assert.equal(node.hidden, true);
  assert.equal(frames.size, 0);
});
