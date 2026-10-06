/* A single strip of paper winds around its original starting tip while
 * the remaining perforation stays attached on the left. No backing rectangle:
 * every pixel outside the deformed strip is transparent. */
const ReceiptPaper = (() => {
  const W = 240, H = 36, PAD_X = 288, PAD_Y = 40, DOWN_SLOPE = 0.085;
  let defaultRenderer;
  const clamp = v => Math.max(0, Math.min(1, v));
  const smooth = v => { const t = clamp(v); return t * t * (3 - 2 * t); };

  function init(node, label = node.parentElement.querySelector('.stubLabel')) {
    defaultRenderer = create(node, { label });
  }

  // Each slip owns its canvas and typography; opening a detail cannot take
  // over the filter receipt's renderer.
  function create(canvas, options = {}) {
    const width = options.width || W, height = options.height || H;
    const label = options.label || canvas.parentElement.querySelector('.stubLabel');
    const labelStyle = label ? getComputedStyle(label) : {
      fontStyle: 'normal', fontWeight: '400', fontSize: '8px',
      fontFamily: '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
      letterSpacing: '1.6px',
    };
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const canvasWidth = width + 320;
    canvas.width = canvasWidth * ratio;
    canvas.height = 180 * ratio;
    canvas.style.width = canvasWidth + 'px';
    const surface = {
      ctx: canvas.getContext('2d'), ratio, labelStyle, W: width, H: height, canvasWidth,
      text: options.text || 'PULL TO RESET',
    };
    return { draw: (progress, departure = 0) => render(surface, progress, departure) };
  }

  /* The roll consumes the strip from right to left, like rolling up a mat. */
  function geometry(progress, departure = 0, W = 240) {
    const p = clamp(progress), free = W * p, attached = W - free;
    // A caller cannot move/fade the sheet while any perforation is attached.
    const exit = p === 1 ? clamp(departure) : 0;
    // Once the last fibre parts, release the paper's tension close to the
    // seam. A small recoil replaces the long sideways slide and extra spin.
    const release = 1 - Math.pow(1 - exit, 3);
    const travel = 6 * release;
    const settle = 7 * release;
    const opacity = 1 - smooth((exit - 0.18) / 0.82);
    // A spiral keeps the starting tip in the core as new paper wraps around
    // it. The radius grows with wound length instead of leaving a loose flap.
    const core = 4, winding = 0.42;
    const radius = Math.sqrt(core * core + 2 * winding * free);
    const rotation = 0.16 * release;

    function point(x, y) {
      if (x <= attached && !exit) return { x, y, z: 0, normal: 1 };
      const distance = Math.max(0, x - attached);
      const r = Math.sqrt(Math.max(core * core, radius * radius - 2 * winding * distance));
      const angle = (radius - r) / winding + rotation;
      const z = radius - r * Math.cos(angle);
      // Let the roll drift down about 5° as it travels left. Ease the bend
      // away from the seam so the paper still attached above stays pinned.
      const bend = clamp(distance / 24);
      const heldBend = smooth(bend);
      // The lip held at the seam winds into the roll as it breaks free.
      const drop = free * DOWN_SLOPE * (heldBend + (1 - heldBend) * release);
      const fibre = y === 0 ? Math.sin(x * 2.1) * 0.45 * Math.min(1, distance / 4) : 0;
      return {
        x: attached + r * Math.sin(angle),
        y: y + z * 0.6 + drop + fibre,
        z, normal: Math.cos(angle),
      };
    }
    return { progress: p, attached, exit, travel, settle, opacity, radius, point };
  }

  function render({ ctx, ratio, labelStyle, W, H, canvasWidth, text }, progress, departure) {
    const { progress: p, attached, travel, settle, opacity, point } = geometry(progress, departure, W);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, canvasWidth, 180);
    ctx.translate(PAD_X - travel, PAD_Y + settle);
    ctx.globalAlpha = opacity;

    function path(points) {
      ctx.beginPath();
      points.forEach((v, i) => i ? ctx.lineTo(v.x, v.y) : ctx.moveTo(v.x, v.y));
      ctx.closePath();
    }

    const faces = [];
    for (let x = 0; x < W; x += 3) {
      for (let y = 0; y < H; y += 6) {
        const right = Math.min(W, x + 3), bottom = Math.min(H, y + 6);
        const corners = [point(x, y), point(right, y), point(right, bottom), point(x, bottom)];
        const middle = point((x + right) / 2, (y + bottom) / 2);
        faces.push({ corners, z: middle.z, normal: middle.normal });
      }
    }

    function face(f) {
      const back = f.normal < 0;
      const light = Math.abs(f.normal);
      const base = back ? [236, 229, 213] : [250, 248, 243];
      const shade = (1 - light) * (back ? 44 : 27);
      ctx.fillStyle = 'rgb(' + base.map(v => Math.round(v - shade)).join(',') + ')';
      path(f.corners);
      ctx.fill();
      // Overlap subpixel mesh edges to avoid hairline cracks in the stock.
      ctx.strokeStyle = ctx.fillStyle;
      ctx.lineWidth = 0.55;
      ctx.stroke();
    }
    // Paint the curved edge and its lettering in surface depth order.
    const layers = faces.map(f => ({ z: f.z, paint: () => face(f) }));

    // Each letter stays on its own patch of the front surface. Once that
    // patch turns over it is hidden, rather than floating over the torn gap.
    const font = `${labelStyle.fontStyle} ${labelStyle.fontWeight} ${labelStyle.fontSize} ${labelStyle.fontFamily}`;
    ctx.font = font;
    ctx.letterSpacing = '0px';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const spacing = parseFloat(labelStyle.letterSpacing) || 0;
    const widths = [...text].map(c => ctx.measureText(c).width + spacing);
    let tx = W / 2 - widths.reduce((a, b) => a + b, 0) / 2;
    [...text].forEach((c, i) => {
      const x = tx + (widths[i] - spacing) / 2;
      const label = point(x, H / 2), direction = point(x + 0.5, H / 2);
      if (label.normal > 0.1) {
        layers.push({ z: label.z + 0.02, paint: () => {
          ctx.save();
          ctx.fillStyle = '#C05A38';
          ctx.font = font;
          ctx.translate(label.x, label.y);
          ctx.rotate(Math.atan2(direction.y - label.y, direction.x - label.x));
          ctx.fillText(c, 0, 0);
          ctx.restore();
        } });
      }
      tx += widths[i];
    });
    const arrow = point(W - 20, H / 2);
    if (arrow.normal > 0) {
      layers.push({ z: arrow.z + 0.02, paint: () => {
        ctx.save();
        ctx.fillStyle = '#C05A38';
        ctx.font = `13px ${labelStyle.fontFamily}`;
        ctx.fillText('←', arrow.x, arrow.y);
        ctx.restore();
      } });
    }
    layers.sort((a, b) => a.z - b.z).forEach(layer => layer.paint());

    // The open ends expose the paper's spiral cross-section. Keep these fine:
    // the starting tip is inside the roll, hidden by the outer surface.
    ctx.beginPath(); ctx.moveTo(0, 0.5); ctx.lineTo(attached, 0.5);
    ctx.setLineDash([3, 3]); ctx.lineWidth = 0.75;
    ctx.strokeStyle = '#928F86'; ctx.stroke(); ctx.setLineDash([]);
    if (p > 0) {
      for (const edgeY of [0, H]) {
        ctx.beginPath();
        for (let x = attached; x <= W; x += 1) {
          const v = point(x, edgeY);
          if (x === attached) ctx.moveTo(v.x, v.y); else ctx.lineTo(v.x, v.y);
        }
        ctx.lineWidth = 0.7; ctx.strokeStyle = 'rgba(127,112,88,.24)'; ctx.stroke();
      }
    }
  }

  const draw = (progress, departure = 0) => defaultRenderer?.draw(progress, departure);
  return { init, draw, create, geometry };
})();
