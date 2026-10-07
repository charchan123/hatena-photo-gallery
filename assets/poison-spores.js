/* Decorative bursts. Eligibility is server-supplied; never infer from names/text. */
(function (root) {
  "use strict";
  const CARD = '.mushroom-card[data-food-safety="poisonous_confirmed"]';
  const PAGES = '.guide-index, .aiuo-index, .season-index, .feature-index';
  const PRESETS = [
    // x/y are image fractions. Signed dx/dy spread around the mushroom;
    // sway bends the slow tail without changing the initial radial direction.
    { x:.44, y:.40, dx:-36, dy:-52, sway:10, size:5, opacity:.64, duration:2200, delay:0, blur:0, color:"#C7ED55" },
    { x:.53, y:.46, dx:40, dy:-51, sway:-10, size:6, opacity:.78, duration:2100, delay:55, blur:.3, color:"#C084FC" },
    { x:.48, y:.56, dx:-48, dy:-40, sway:12, size:4, opacity:.68, duration:1800, delay:110, blur:0, color:"#C7ED55" },
    { x:.57, y:.40, dx:49, dy:-40, sway:-12, size:7, opacity:.74, duration:2400, delay:75, blur:.5, color:"#C084FC" },
    { x:.41, y:.62, dx:-63, dy:-8, sway:10, size:5, opacity:.60, duration:2000, delay:170, blur:.3, color:"#C7ED55" },
    { x:.60, y:.51, dx:64, dy:-12, sway:-10, size:6, opacity:.70, duration:2300, delay:225, blur:0, color:"#C7ED55" },
    { x:.46, y:.68, dx:-57, dy:-24, sway:12, size:7, opacity:.76, duration:1900, delay:260, blur:.4, color:"#C084FC" },
    { x:.55, y:.58, dx:57, dy:-19, sway:-12, size:4, opacity:.66, duration:2100, delay:145, blur:0, color:"#C7ED55" },
    { x:.50, y:.40, dx:5, dy:-78, sway:10, size:8, opacity:.72, duration:2700, delay:95, blur:.6, color:"#C084FC" },
    { x:.43, y:.53, dx:40, dy:14, sway:-10, size:5, opacity:.62, duration:2500, delay:295, blur:.5, color:"#C7ED55" }
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
          // A normalized 16px kick follows each particle's own direction.
          '--spore-kick-x':(16 * p.dx / Math.hypot(p.dx, p.dy)) + 'px',
          '--spore-kick-y':(16 * p.dy / Math.hypot(p.dx, p.dy)) + 'px',
          '--spore-mid-x':(p.dx * .63) + 'px', '--spore-mid-y':(p.dy * .63) + 'px',
          '--spore-sway-x':(p.dx * .85 + p.sway) + 'px',
          '--spore-late-y':(p.dy * .85) + 'px',
          '--spore-end-x':p.dx + 'px', '--spore-end-y':p.dy + 'px'
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
