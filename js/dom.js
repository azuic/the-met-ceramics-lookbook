/* dom.js — the three helpers the rest of the interface needs.
 *
 * Everything the museum wrote (titles, mediums, place names) goes in as text,
 * never as markup. */

const DOM = (() => {
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        const v = attrs[k];
        if (v == null || v === false) continue;
        if (k === 'style') node.style.cssText = v;
        else if (k === 'text') node.textContent = v;
        else if (k === 'class') node.className = v;
        else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2).toLowerCase(), v);
        else node.setAttribute(k, v === true ? '' : v);
      }
    }
    if (children) {
      for (const c of children) {
        if (c) node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      }
    }
    return node;
  }

  const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); };

  const fill = (node, children) => { clear(node); for (const c of children) if (c) node.appendChild(c); };

  return { el, clear, fill };
})();
