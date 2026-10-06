/* The ring is a compact colour map of the same ordered objects as the field.
 * Rebuild only when its index changes, never while scrolling or loading crops. */
const PaletteRing = (() => {
  function gradient(index, rgb) {
    if (!index?.length) return 'none';
    const bins = Math.min(180, index.length);
    const stops = [];
    let first, last;
    for (let bin = 0; bin < bins; bin++) {
      const from = Math.floor(bin * index.length / bins);
      const to = Math.floor((bin + 1) * index.length / bins);
      let r = 0, g = 0, b = 0;
      for (let k = from; k < to; k++) {
        const offset = index[k] * 3;
        r += rgb[offset]; g += rgb[offset + 1]; b += rgb[offset + 2];
      }
      const count = to - from;
      const colour = 'rgb(' + Math.round(r / count) + ',' +
        Math.round(g / count) + ',' + Math.round(b / count) + ')';
      if (!first) first = colour;
      last = colour;
      stops.push(colour + ' ' + ((from + to) / 2 / index.length * 100).toFixed(4) + '%');
    }
    // Do not interpolate across the seam: the last objects are not adjacent
    // to the first ones in the scrollable field.
    return 'conic-gradient(from 0deg,' + first + ' 0%,' + stops.join(',') + ',' + last + ' 100%)';
  }

  return { gradient };
})();
