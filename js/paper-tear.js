/* Shared pull, cancel, and release behaviour for the receipt and museum link. */
const PaperTear = (() => {
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function attach(button, { text, onCommit, onIdle = () => {}, canStart = () => true }) {
    const listeners = new AbortController();
    let renderer, pull = null, amount = 0, motion = null;
    let tearing = false, disposed = false, suppressClick = false;
    let width = 240;

    function prepare() {
      width = button.offsetWidth || 240;
      renderer = ReceiptPaper.create(button.querySelector('canvas'), {
        width, text, label: button.querySelector('.stubLabel'),
      });
    }

    function cancelMotion() {
      if (!motion) return;
      cancelAnimationFrame(motion.frame);
      motion.resolve(false);
      motion = null;
    }

    function animate(to, duration, roll = false) {
      cancelMotion();
      const from = amount;
      return new Promise(resolve => {
        const run = { frame: 0, resolve };
        motion = run;
        const start = performance.now(), releaseDuration = roll ? 220 : 0;
        const tick = now => {
          const elapsed = now - start;
          const t = duration ? Math.min(1, elapsed / duration) : 1;
          const initialSlope = from > 0 ? 1 : 0, finalSlope = 0.12;
          const ease = roll
            ? (initialSlope + finalSlope - 2) * t * t * t
              + (3 - 2 * initialSlope - finalSlope) * t * t + initialSlope * t
            : 1 - Math.pow(1 - t, 2);
          amount = t === 1 ? to : from + (to - from) * ease;
          const departure = roll ? Math.max(0, Math.min(1, (elapsed - duration) / releaseDuration)) : 0;
          renderer.draw(amount, departure);
          if (elapsed < duration + releaseDuration) run.frame = requestAnimationFrame(tick);
          else { motion = null; resolve(true); }
        };
        run.frame = requestAnimationFrame(tick);
      });
    }

    function down(e) {
      if (disposed || tearing || !canStart() || e.button !== 0 || !e.isPrimary || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      cancelMotion();
      prepare();
      button.classList.remove('pulling');
      suppressClick = false;
      amount = 0;
      pull = { id: e.pointerId, x: e.clientX, y: e.clientY, moved: false,
        scale: button.getBoundingClientRect().width / width };
      button.setPointerCapture(e.pointerId);
    }

    function move(e) {
      if (!pull || e.pointerId !== pull.id) return;
      const dx = (e.clientX - pull.x) / pull.scale, dy = (e.clientY - pull.y) / pull.scale;
      if (Math.hypot(dx, dy) > 4) pull.moved = true;
      amount = Math.min(1, (Math.max(0, dy) + Math.max(0, -dx) * 0.9) / (width * 0.75));
      if (!reducedMotion()) {
        button.classList.toggle('pulling', amount > 0);
        renderer.draw(amount);
      }
    }

    function finish(e) {
      if (!pull || e.pointerId !== pull.id) return;
      const commit = e.type === 'pointerup' && amount >= 48 / (width * 0.75);
      suppressClick = pull.moved;
      const id = pull.id;
      pull = null;
      if (button.hasPointerCapture(id)) button.releasePointerCapture(id);
      if (commit) { onCommit(); return; }
      if (!reducedMotion() && amount > 0) {
        animate(0, 180).then(completed => {
          if (completed && !disposed && !pull && !tearing) {
            button.classList.remove('pulling');
            onIdle();
          }
        });
      } else {
        amount = 0;
        button.classList.remove('pulling');
        // A click follows pointerup; let it begin before applying late record
        // data that would otherwise replace the element under that click.
        requestAnimationFrame(() => {
          if (!disposed && !pull && !tearing) onIdle();
        });
      }
    }

    function click(e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button > 0) return;
      e.preventDefault();
      if (e.detail && suppressClick) { suppressClick = false; return; }
      if (!disposed && !tearing && canStart()) onCommit();
    }

    async function tear() {
      if (disposed || tearing) return false;
      cancelMotion();
      prepare();
      tearing = true;
      button.classList.remove('pulling');
      button.classList.add('tearing');
      button.setAttribute('aria-disabled', 'true');
      if (!reducedMotion()) renderer.draw(amount);
      const completed = reducedMotion() || await animate(1, 720 * (1 - amount), true);
      if (disposed) return false;
      if (completed) button.hidden = true;
      amount = 0;
      tearing = false;
      button.classList.remove('tearing');
      button.removeAttribute('aria-disabled');
      return completed;
    }

    const on = (type, fn) => button.addEventListener(type, fn, { signal: listeners.signal });
    on('pointerdown', down);
    on('pointermove', move);
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) on(type, finish);
    on('click', click);
    on('dragstart', e => e.preventDefault());

    return {
      tear,
      isActive: () => !!(pull || motion || tearing),
      destroy() {
        disposed = true;
        listeners.abort();
        cancelMotion();
        if (pull && button.hasPointerCapture(pull.id)) button.releasePointerCapture(pull.id);
        pull = null;
      },
    };
  }

  return { attach };
})();
