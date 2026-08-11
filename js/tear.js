/* tear.js — the paper that comes off in your hand.
 *
 * Two things in the lookbook end in a piece you are meant to remove: the field
 * receipt, and the coupon at the foot of the catalogue card. They are the same
 * object — a sheet, a line of perforations, a stub below it — so both are made
 * here.
 *
 * A tear is not a slide. The stub hangs from the last corner still joined and
 * swings on it, while the split travels along the perforation from the
 * scissors outward. Ahead of the split the sheet is still holding on, so it
 * bows down to follow the stub rather than showing a gap; behind it the two
 * edges come apart along one ragged line that is generated once and shared.
 * The sheet keeps the negative of whatever the stub takes away, which is what
 * makes the halves read as one sheet torn rather than two printed apart.
 *
 * A sheet is in one of three states, and it stays in the last one: bare (it
 * never had a stub, and its edge is the printed one), joined (perforated, stub
 * attached), or torn (the stub is gone and the ragged edge it left is now the
 * sheet's own bottom edge). */

const Tear = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const PAD = 28;   // paper below the perforation on the sheet: always clipped
                    // away, but it is the slack the sheet bends into while the
                    // split travels, and the margin takes the layout back
  const LIP = 5;    // headroom above the perforation on the stub, for the rise
  const AMP = 3.6;  // how far a fibre may stray from the perforation
  const STEP = 6;   // vertex spacing — also the grain the split travels on
  const SOFT = 16;  // how far behind the split the edge finishes opening
  /* How far the clip reaches past the box. It has to clear two things, and the
   * second one is the reason it is this big: anything hanging outside the box
   * (the open-access stamp), and the whole spread of the drop-shadow. Clipping
   * is applied after filtering, so a clip that stops anywhere the shadow still
   * has alpha cuts it off mid-falloff and leaves a faint hard-edged rectangle
   * on the frosted backdrop. Past the falloff there is nothing left to cut. */
  const OUT = 150;
  const MAXA = 26;  // degrees of swing once it hangs by the corner alone
  const PULL = 62;  // pixels of drag from joined to hanging
  const GO = 0.42;  // past this much it is committed and lets go

  const slow = window.matchMedia('(prefers-reduced-motion: reduce)');

  function rand(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* Two octaves. The slow wander is where the tear drifts off the line over the
   * width of the paper; the jitter on top of it is the fibre. Jitter alone
   * reads as pinking shears, and wander alone reads as a bad cut. */
  function profile(w, seed) {
    const r = rand(seed);
    const span = 52;
    const ctrl = [];
    for (let i = 0; i <= Math.ceil(w / span) + 1; i++) ctrl.push((r() - 0.5) * 1.24 * AMP);
    const pts = [];
    for (let x = 0; x <= w; x += STEP) {
      const t = x / span, i = Math.floor(t), f = t - i;
      const m = (1 - Math.cos(f * Math.PI)) / 2;
      let y = ctrl[i] + (ctrl[i + 1] - ctrl[i]) * m;
      y += (r() - 0.5) * 0.75 * AMP;
      if (r() > 0.94) y += (r() - 0.5) * AMP;   // a fibre that pulled long
      pts.push([x, Math.max(-AMP, Math.min(AMP, y))]);
    }
    if (pts[pts.length - 1][0] < w) pts.push([w, (r() - 0.5) * AMP]);
    return pts;
  }

  function poly(list) {
    return 'polygon(' + list.map(q => q[0].toFixed(1) + 'px ' + q[1].toFixed(1) + 'px').join(',') + ')';
  }

  /* Everything drawn along the seam lives in one overlay: the fibre standing
   * up behind the split, and the perforations still to be broken ahead of it.
   * Both have to be generated per frame, because the split eats one and leaves
   * the other. The clip is measured from the border box while an absolutely
   * positioned child hangs off the padding box, so the overlay is shifted back
   * out over the border or it draws a pixel adrift of the edge it belongs to. */
  function fringe(host, perforated) {
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'tear-fringe');
    const edge = document.createElementNS(NS, 'path');
    edge.setAttribute('class', 'tear-fibre');
    svg.appendChild(edge);
    let perf = null;
    if (perforated) {
      perf = document.createElementNS(NS, 'path');
      perf.setAttribute('class', 'tear-perf');
      svg.appendChild(perf);
    }
    host.appendChild(svg);
    const cs = getComputedStyle(host);
    svg.style.transform = 'translate(' + -parseFloat(cs.borderLeftWidth) +
      'px,' + -parseFloat(cs.borderTopWidth) + 'px)';
    return { edge, perf };
  }

  /* sheet and stub must be the same width and adjacent in the flow, the stub
   * pulled up over the sheet's clipped-away padding by the stylesheet. onTear
   * fires the moment the last corner lets go rather than when the piece lands,
   * so the rest of the interface can react while it is still in the air. */
  function attach(opt) {
    const sheet = opt.sheet, stub = opt.stub;
    const onTear = opt.onTear || (() => {});
    const enabled = opt.enabled || (() => true);

    // Without GSAP, or for anyone who has asked for less movement, the stub is
    // simply a button: it does the thing, and the paper does not perform.
    if (!window.gsap || !window.Draggable || slow.matches) {
      const go = (e) => {
        if (!enabled()) return;
        if (e) e.preventDefault();
        if (opt.onCommit) opt.onCommit(e);
        onTear();
      };
      stub.addEventListener('click', go);
      return { rip: go, refresh: () => {}, rejoin: () => {}, busy: () => false, destroy: () => {} };
    }

    let pts = [], w = 0, seam = 0, stubH = 0, p = 0;
    let mode = 'bare', flying = false, fall = null;
    const sheetArt = fringe(sheet, true), stubArt = fringe(stub, false);

    // Draggable moves this instead of the stub, so the stub's transform stays
    // ours to write. It sits beside the stub on purpose: sharing an ancestor
    // means Draggable resolves the drag through the same scale and tilt the
    // paper is under, and reports distances in the units the geometry uses.
    const proxy = document.createElement('div');
    proxy.style.cssText = 'position:absolute;left:0;top:0;width:1px;height:1px;opacity:0;pointer-events:none';
    stub.parentNode.appendChild(proxy);

    function measure() {
      const nw = sheet.offsetWidth;
      if (!nw) return false;
      if (nw !== w) { w = nw; pts = profile(w, opt.seed || 11); }
      seam = sheet.offsetHeight - PAD;
      stubH = stub.offsetHeight || stubH;
      return true;
    }

    /* One pass builds both clips and both fringes from the same profile, so
     * whatever the sheet gives up is exactly what the stub carries off. Once
     * the stub is gone the sheet is drawn on its own, fully open and flat —
     * there is nothing left to bend towards. */
    function draw(alone) {
      if (!pts.length) return;
      const split = alone ? w * 2 : w * Math.min(1, p * 1.45);
      const tan = alone ? 0 : Math.tan(MAXA * p * Math.PI / 180);
      const bot = [], top = [];
      // Behind the split the paper has parted and shows fibre; ahead of it the
      // perforations are still intact, and they ride the bend with the sheet
      // because they are printed on it.
      const fib = [], prf = [], sfib = [];

      for (let k = 0; k < pts.length; k++) {
        const x = pts[k][0];
        const t = Math.max(0, Math.min(1, (split - x) / SOFT));
        const ragged = pts[k][1] * t;
        // Ahead of the split the sheet follows the stub down; behind it, it has
        // let go and settles onto the torn edge it was left with.
        const sy = seam + ragged + (w - x) * tan * (1 - t);
        bot.push([x, sy]);
        const step = x.toFixed(1) + ' ' + sy.toFixed(1);
        if (x <= split) fib.push((fib.length ? 'L' : 'M') + step);
        if (x >= split) prf.push((prf.length ? 'L' : 'M') + x.toFixed(1) + ' ' + (sy - 1).toFixed(1));
        if (alone) continue;
        const ty = LIP + ragged;
        top.push([x, ty]);
        if (x <= split) sfib.push((sfib.length ? 'L' : 'M') + x.toFixed(1) + ' ' + ty.toFixed(1));
      }

      sheet.style.clipPath = poly([[-OUT, -OUT], [w + OUT, -OUT], [w + OUT, bot[bot.length - 1][1]]]
        .concat(bot.slice().reverse()).concat([[-OUT, bot[0][1]]]));
      sheetArt.edge.setAttribute('d', fib.length > 1 ? fib.join('') : '');
      sheetArt.perf.setAttribute('d', mode === 'joined' && prf.length > 1 ? prf.join('') : '');
      if (alone) return;

      stub.style.clipPath = poly([[-OUT, top[0][1]]].concat(top)
        .concat([[w + OUT, top[top.length - 1][1]], [w + OUT, stubH + OUT], [-OUT, stubH + OUT]]));
      stubArt.edge.setAttribute('d', sfib.length > 1 ? sfib.join('') : '');

      // The swing is a rotation about the far corner, written as a rotation
      // about the near one plus the offset that makes the two identical. That
      // keeps the transform origin fixed, so nothing jumps as the split moves.
      const a = MAXA * p * Math.PI / 180;
      gsap.set(stub, {
        transformOrigin: '0px ' + LIP + 'px',
        rotation: -MAXA * p,
        x: w * (1 - Math.cos(a)),
        y: w * Math.sin(a),
      });
    }

    function setP(v) {
      p = Math.max(0, Math.min(1, v));
      draw(false);
    }

    /* Redraw whatever the paper is currently resting as. The receipt changes
     * height whenever a filter comes or goes, and the clip is in pixels, so it
     * has to be told. */
    function refresh() {
      if (flying || !measure()) return;
      if (mode === 'bare') {
        p = 0;
        draw(false);
        gsap.set(stub, { clearProps: 'transform,opacity' });
      } else if (mode === 'joined') {
        p = 0;
        draw(false);
      } else {
        draw(true);
      }
    }

    // The stub is back: the sheet is whole again, perforation and all.
    function rejoin() {
      if (flying) return;
      mode = 'joined';
      sheet.classList.add('joined');
      p = 0;
      stub.hidden = false;
      gsap.set(stub, { clearProps: 'transform,opacity' });
      gsap.set(sheet, { clearProps: 'transform' });
      if (measure()) draw(false);
    }

    /* Let go: finish the split, then the corner fails and it drops. Paper does
     * not fall flat — it turns out of plane on the way down, and that is most
     * of what tells you it is paper rather than a card. */
    function rip() {
      if (flying || !enabled()) return;
      if (!measure()) { onTear(); return; }
      flying = true;
      const drift = (opt.seed || 11) % 2 ? 14 : -11;
      const holder = { v: p };

      fall = gsap.timeline({
        onComplete: () => {
          flying = false;
          fall = null;
          mode = 'torn';
          sheet.classList.remove('joined');
          // It came off. Clearing the transform would otherwise hand it back
          // whole and in place, so it goes before the props do.
          stub.hidden = true;
          gsap.set(stub, { clearProps: 'transform,opacity' });
          gsap.set(sheet, { clearProps: 'transform' });
          stub.style.clipPath = '';
          stubArt.edge.removeAttribute('d');
          draw(true);
          if (opt.onSettle) opt.onSettle();
        },
      });

      fall.to(holder, {
        v: 1,
        duration: 0.13 * (1 - p) + 0.05,
        ease: 'power3.in',
        onUpdate: () => setP(holder.v),
      });
      fall.add(onTear);
      fall.to(stub, { y: '+=320', duration: 0.66, ease: 'power2.in' }, 'drop')
        .to(stub, { rotation: '-=34', x: '+=' + drift, duration: 0.66, ease: 'none' }, 'drop')
        .to(stub, {
          keyframes: { rotationY: [0, 26, -18, 9, 0], rotationX: [0, -14, 8, -4, 0] },
          duration: 0.66,
          ease: 'sine.inOut',
        }, 'drop')
        .to(stub, { opacity: 0, duration: 0.24, ease: 'power1.in' }, 'drop+=0.42')
        // The sheet lifts the instant the load comes off it.
        .fromTo(sheet, { y: -2.5 }, { y: 0, duration: 0.45, ease: 'power4.out' }, 'drop');
    }

    function springBack() {
      const holder = { v: p };
      gsap.to(holder, {
        v: 0,
        duration: 0.42,
        ease: 'power4.out',
        onUpdate: () => setP(holder.v),
        onComplete: () => setP(0),
      });
    }

    const drag = Draggable.create(proxy, {
      type: 'y',
      trigger: stub,
      cursor: 'grab',
      activeCursor: 'grabbing',
      allowContextMenu: true,
      dragClickables: true,
      onPress() {
        if (flying || !enabled()) return;
        measure();
        gsap.killTweensOf(stub);
        gsap.set(proxy, { y: 0 });
      },
      onDrag() {
        if (flying || !enabled()) return;
        setP(Math.pow(Math.max(0, this.y) / PULL, 1.15));
      },
      onDragEnd() {
        if (flying || !enabled()) return;
        if (p < GO) { springBack(); return; }
        if (opt.onCommit) opt.onCommit(this.pointerEvent);
        rip();
      },
      onClick() {
        if (flying || !enabled()) return;
        if (opt.onCommit) opt.onCommit(this.pointerEvent);
        rip();
      },
    })[0];

    /* Tearing the coupon off opens the record, and the new tab takes the focus
     * with it — which stops this page's frames and would leave the piece
     * hanging in mid-air until someone came back. If nobody is watching, the
     * paper lands immediately instead. */
    function hidden() {
      if (document.hidden && fall) fall.progress(1);
    }
    document.addEventListener('visibilitychange', hidden);

    // Reachable without a pointer. An anchor already turns Enter into a click,
    // so only elements that are not natively activatable need this.
    if (opt.keys !== false) {
      stub.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        if (flying || !enabled()) return;
        if (opt.onCommit) opt.onCommit(e);
        rip();
      });
    }

    if (opt.joined) rejoin(); else refresh();

    return {
      rip,
      refresh,
      rejoin,
      busy: () => flying,
      destroy() {
        if (fall) fall.kill();
        gsap.killTweensOf(stub);
        drag.kill();
        document.removeEventListener('visibilitychange', hidden);
        proxy.remove();
      },
    };
  }

  return { attach };
})();
