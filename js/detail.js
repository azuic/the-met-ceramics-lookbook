/* detail.js — the catalogue card.
 *
 * The plate on the left is the object's own photograph, hotlinked live from
 * the museum and laid on the colour the grid drew for it, so the tile you
 * clicked is still underneath the picture while it loads. The card on the
 * right is the record verbatim: empty fields are dropped rather than filled
 * with dashes. */

const Detail = (() => {
  const { el, fill } = DOM;
  let root, body, current = -1;

  function titleCase(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  }

  function plate(i, rec) {
    const colour = Data.state.colors[i];
    const box = el('div', {
      style: 'position:relative;width:380px;height:430px;overflow:hidden;background:' +
        'radial-gradient(120% 100% at 35% 30%, rgba(255,255,255,0.22), transparent 55%), ' + colour,
    });
    if (rec && rec.image) {
      const img = el('img', {
        src: rec.image,
        alt: rec.title || 'Ceramic object',
        loading: 'lazy',
        style: 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;' +
          'opacity:0;transition:opacity .45s ease',
      });
      img.addEventListener('load', () => { img.style.opacity = '1'; });
      img.addEventListener('error', () => img.remove());
      box.appendChild(img);
    }
    return el('div', { class: 'plate' }, [
      box,
      el('div', { style: 'margin-top:16px;display:flex;justify-content:space-between;align-items:center;gap:20px' }, [
        el('span', {
          style: 'font-size:9px;letter-spacing:0.16em;color:#928F86',
          text: 'MET ' + Data.state.id[i],
        }),
        el('span', { style: 'display:flex;align-items:center;gap:8px' }, [
          // The chip is the exact colour the field used for this object.
          el('span', { style: 'width:34px;height:34px;background:' + colour + ';border:1px solid #D8D4CB;display:inline-block' }),
          el('span', { style: 'font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:#928F86', text: 'The crop' }),
        ]),
      ]),
    ]);
  }

  function card(i, rec) {
    const S = Data.state, meta = S.meta;
    const dep = meta.departments[S.dep[i]];
    const mat = meta.materials[S.mat[i]].name;
    const matName = mat === 'other/unspecified' ? 'ceramic' : mat;
    const place = (rec && (rec.country || rec.culture)) || '';

    const rows = [
      ['Medium', rec && rec.medium],
      ['Place', place],
      ['Date', rec && rec.date],
      ['Department', dep.name],
      ['Object', rec && rec.objectName],
      ['Culture', rec && rec.culture !== place ? rec.culture : ''],
    ].filter(r => r[1]);

    const title = (rec && rec.title) || titleCase(matName) + ' object';

    return el('div', { class: 'card' }, [
      el('div', {
        style: 'position:absolute;top:-12px;right:-14px;background:#F3F1EC;border:1.5px solid #C05A38;' +
          'color:#C05A38;padding:5px 8px;transform:rotate(3deg);font-size:8px;letter-spacing:0.14em',
        text: 'OPEN ACCESS · PUBLIC DOMAIN',
      }),
      el('div', {
        style: "font-family:'Libre Baskerville',Georgia,serif;font-size:21px;line-height:1.3;color:#262623;margin-bottom:14px",
        text: title,
      }),
      ...rows.map(([k, v]) => el('div', { class: 'field' }, [
        el('div', { class: 'k', text: k }),
        el('div', { class: 'v', text: v }),
      ])),
      el('div', {
        style: 'margin-top:14px;border:1.5px solid #96362C;color:#96362C;padding:7px 10px;transform:rotate(-2deg);' +
          'display:inline-block;letter-spacing:0.16em;font-size:9px;text-transform:uppercase',
        text: dep.short + ' · OBJ ' + S.id[i],
      }),
      el('a', {
        href: rec ? rec.url : 'https://www.metmuseum.org/art/collection/search',
        target: '_blank',
        rel: 'noopener',
        style: 'display:block;margin-top:18px;border-top:1px dashed #928F86;padding-top:12px;text-align:center;' +
          'font-size:8px;letter-spacing:0.22em;text-transform:uppercase;text-decoration:none',
        text: '✂ Tear here for the full record',
      }),
    ]);
  }

  function attrs(i) {
    const S = Data.state, meta = S.meta;
    const fam = meta.families[S.fam[i]];
    const mat = meta.materials[S.mat[i]].name;
    const list = [
      ['Palette', fam.name, fam.hex],
      ['Material', mat === 'other/unspecified' ? 'unspecified' : mat, '#BA8F3E'],
      ['Surface', S.mono[i] ? 'archival record shot' : fam.surface.split(' ')[0] + ' glazed', '#928F86'],
    ];
    return el('div', { class: 'attrs' }, list.map(([k, v, hex]) => el('div', {
      style: 'display:flex;align-items:center;gap:10px',
    }, [
      el('span', { style: 'width:11px;height:11px;border-radius:50%;background:' + hex }),
      el('div', {}, [
        el('div', { style: 'font-size:8px;letter-spacing:0.16em;text-transform:uppercase;color:#928F86', text: k }),
        el('div', { style: "font-family:'Libre Baskerville',Georgia,serif;font-size:13.5px;color:#262623", text: v }),
      ]),
    ])));
  }

  /* Rebuilding the contents on every open is what restarts the card
   * animations, and 44k records means only one is ever built. */
  function render(i, rec) {
    fill(body, [plate(i, rec), card(i, rec), attrs(i)]);
  }

  function open(i) {
    current = i;
    root.hidden = false;
    render(i, null);
    Data.detail(i).then(rec => { if (current === i && rec) render(i, rec); });
  }

  function close() {
    current = -1;
    root.hidden = true;
    DOM.clear(body);
  }

  function init(handlers) {
    root = document.getElementById('detail');
    body = document.getElementById('detailBody');
    document.getElementById('detailClose').addEventListener('click', close);
    document.getElementById('detailPrev').addEventListener('click', () => handlers.step(-1));
    document.getElementById('detailNext').addEventListener('click', () => handlers.step(1));
  }

  return { init, open, close, isOpen: () => current >= 0 };
})();
