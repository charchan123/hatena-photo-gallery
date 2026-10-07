/* Decorative bursts. Eligibility is server-supplied; never infer from names/text. */
(function (root) {
  "use strict";
  const CARD = '.mushroom-card[data-food-safety="poisonous_confirmed"]';
  const PAGES = '.guide-index, .aiuo-index, .season-index, .feature-index';
  const PRESETS = [
    // x/y are fractions of the image; dx/sway/rise are pixels.
    { x:.44, y:.40, dx:-18, sway:12, rise:86, size:4, opacity:.58, duration:2200, delay:0, blur:0, color:"#B8E34A" },
    { x:.53, y:.46, dx:21, sway:-11, rise:74, size:5, opacity:.46, duration:2100, delay:55, blur:.5, color:"#9A6BC9" },
    { x:.48, y:.56, dx:-14, sway:10, rise:63, size:3, opacity:.60, duration:1800, delay:110, blur:0, color:"#B8E34A" },
    { x:.57, y:.40, dx:17, sway:-13, rise:89, size:6, opacity:.40, duration:2400, delay:75, blur:1, color:"#9A6BC9" },
    { x:.41, y:.62, dx:-23, sway:14, rise:54, size:4, opacity:.50, duration:2000, delay:170, blur:.3, color:"#B8E34A" },
    { x:.60, y:.51, dx:24, sway:-10, rise:70, size:5, opacity:.55, duration:2300, delay:225, blur:0, color:"#B8E34A" },
    { x:.46, y:.68, dx:-20, sway:12, rise:46, size:7, opacity:.27, duration:1900, delay:260, blur:1.5, color:"#9A6BC9" },
    { x:.55, y:.58, dx:12, sway:-14, rise:60, size:3, opacity:.62, duration:2100, delay:145, blur:0, color:"#B8E34A" },
    { x:.50, y:.43, dx:-16, sway:11, rise:83, size:8, opacity:.28, duration:2500, delay:95, blur:2, color:"#9A6BC9" },
    { x:.43, y:.53, dx:19, sway:-12, rise:68, size:4, opacity:.48, duration:2200, delay:295, blur:.5, color:"#B8E34A" }
  ];

  function burstBounds(rect, width, height) {
    // Body-level fixed paint avoids card/ancestor clipping and never extends
    // the scrollable document. Bottom clipping keeps names/chips unobscured.
    const left = Math.max(0, rect.left - 24);
    const top = Math.max(0, rect.top - 24);
    return { left, top, width:Math.max(0, Math.min(width, rect.right + 24) - left),
      height:Math.max(0, Math.min(height, rect.bottom) - top) };
  }

  function setup(doc, win) {
    if (!doc.body.matches(PAGES)) return null;
    const reduced = win.matchMedia('(prefers-reduced-motion: reduce)');
    const hover = win.matchMedia('(hover: hover) and (pointer: fine)');
    const states = new WeakMap();
    const active = new Map();
    const observer = new win.MutationObserver(() => {
      for (const card of active.keys()) {
        if (!card.isConnected || !card.getClientRects().length || !card.matches(CARD)) clear(card);
      }
    });
    function clear(card) {
      const burst = active.get(card);
      if (!burst) return;
      win.clearTimeout(burst.timer);
      burst.layer.remove();
      active.delete(card);
      if (!active.size) observer.disconnect();
    }
    function clearAll() { for (const card of active.keys()) clear(card); }
    function burst(card) {
      if (reduced.matches || doc.hidden || !card.matches(CARD) || !card.getClientRects().length) return;
      const image = card.querySelector('.mushroom-card-thumb');
      if (!image) return;
      const rect = image.getBoundingClientRect();
      const bounds = burstBounds(rect, doc.documentElement.clientWidth, win.innerHeight);
      if (!rect.width || !rect.height || !bounds.width || !bounds.height) return;
      clear(card);
      // A quick sweep across a grid must not leave hundreds of particles alive.
      if (active.size >= 3) clear(active.keys().next().value);
      const layer = doc.createElement('div');
      layer.className = 'poison-spore-burst';
      layer.setAttribute('aria-hidden', 'true');
      for (const [key, value] of Object.entries(bounds)) layer.style[key] = value + 'px';
      let remaining = PRESETS.length;
      for (const p of PRESETS) {
        const particle = doc.createElement('span');
        particle.className = 'poison-spore';
        const vars = {
          '--spore-x':(rect.left - bounds.left + rect.width * p.x) + 'px',
          '--spore-y':(rect.top - bounds.top + rect.height * p.y) + 'px',
          '--spore-size':p.size + 'px', '--spore-color':p.color,
          '--spore-alpha':p.opacity, '--spore-duration':p.duration + 'ms',
          '--spore-delay':p.delay + 'ms', '--spore-blur':p.blur + 'px',
          '--spore-kick-x':(p.dx * .55) + 'px',
          '--spore-drift-x':p.dx + 'px', '--spore-sway-x':(p.dx + p.sway) + 'px',
          '--spore-mid-y':(-p.rise * .63) + 'px',
          '--spore-late-y':(-p.rise * .85) + 'px', '--spore-end-y':-p.rise + 'px'
        };
        for (const [key, value] of Object.entries(vars)) particle.style.setProperty(key, String(value));
        particle.addEventListener('animationend', () => {
          particle.remove();
          if (--remaining === 0) clear(card);
        }, { once:true });
        layer.appendChild(particle);
      }
      doc.body.appendChild(layer);
      // Fallback for interrupted animations; never retain decorative DOM.
      active.set(card, { layer, timer:win.setTimeout(() => clear(card), 2900) });
      observer.observe(doc.body, { subtree:true, childList:true, attributes:true,
        attributeFilter:['style', 'class', 'hidden', 'data-food-safety'] });
    }
    function state(card) {
      if (!states.has(card)) states.set(card, { hover:false, focus:false });
      return states.get(card);
    }
    // pointerenter does not bubble; capture also handles dynamic search results.
    doc.addEventListener('pointerenter', event => {
      const card = event.target;
      if (!card.matches?.(CARD) || event.pointerType !== 'mouse' || !hover.matches) return;
      const s = state(card);
      if (!s.hover && !s.focus) burst(card);
      s.hover = true;
    }, true);
    doc.addEventListener('pointerleave', event => {
      if (event.target.matches?.(CARD)) state(event.target).hover = false;
    }, true);
    doc.addEventListener('focusin', event => {
      const card = event.target;
      if (!card.matches?.(CARD) || !card.matches(':focus-visible')) return;
      const s = state(card);
      if (!s.focus && !s.hover) burst(card);
      s.focus = true;
    });
    doc.addEventListener('focusout', event => {
      if (event.target.matches?.(CARD)) state(event.target).focus = false;
    });
    win.addEventListener('scroll', clearAll, true);
    win.addEventListener('resize', clearAll);
    win.addEventListener('pagehide', clearAll);
    doc.addEventListener('visibilitychange', clearAll);
    reduced.addEventListener('change', clearAll);
    hover.addEventListener('change', clearAll);
    return { clearAll };
  }
  if (typeof module !== 'undefined') module.exports = { PRESETS, burstBounds, setup };
  if (root.document) root.document.addEventListener('DOMContentLoaded', () => setup(root.document, root));
}(typeof window !== 'undefined' ? window : globalThis));
