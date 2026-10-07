/* Decorative bursts. Eligibility is server-supplied; never infer from names/text. */
(function (root) {
  "use strict";
  const CARD = '.mushroom-card[data-food-safety="poisonous_confirmed"]';
  const PAGES = '.guide-index, .aiuo-index, .season-index, .feature-index';
  const PRESETS = [
    // Six outward paths cross the photo edge; the others drift around the cap.
    { x:.44, y:.40, dx:-83, dy:-104, bend:14, exit:"top", size:7, opacity:.90, duration:3200, delay:0, core:"#EEFF88", edge:"#D7F957" },
    { x:.53, y:.46, dx:90, dy:-73, bend:-15, size:8, opacity:.95, duration:3000, delay:45, core:"#F0D2FF", edge:"#E2A5FF" },
    { x:.48, y:.56, dx:-78, dy:-58, bend:12, size:6, opacity:.90, duration:2800, delay:80, core:"#EEFF88", edge:"#D7F957" },
    { x:.57, y:.40, dx:97, dy:-62, bend:-16, size:9, opacity:.95, duration:3000, delay:60, core:"#F0D2FF", edge:"#E2A5FF" },
    { x:.41, y:.62, dx:-132, dy:-12, bend:14, exit:"left", size:7, opacity:.90, duration:3200, delay:120, core:"#EEFF88", edge:"#D7F957" },
    { x:.60, y:.51, dx:134, dy:-18, bend:-14, exit:"right", size:8, opacity:.90, duration:3300, delay:160, core:"#EEFF88", edge:"#D7F957" },
    { x:.46, y:.68, dx:-140, dy:-26, bend:15, exit:"left", size:9, opacity:.95, duration:3400, delay:180, core:"#F0D2FF", edge:"#E2A5FF" },
    { x:.55, y:.58, dx:130, dy:-20, bend:-13, exit:"right", size:6, opacity:.90, duration:3200, delay:105, core:"#EEFF88", edge:"#D7F957" },
    { x:.50, y:.40, dx:6, dy:-122, bend:16, exit:"top", size:10, opacity:.95, duration:3100, delay:70, core:"#F0D2FF", edge:"#E2A5FF" },
    { x:.43, y:.53, dx:76, dy:18, bend:-12, size:7, opacity:.90, duration:2600, delay:195, core:"#EEFF88", edge:"#D7F957" }
  ];
  const OVERHANG = 80;
  const CLEANUP_MS = Math.max(...PRESETS.map(p => p.duration + p.delay)) + 200;

  function trajectory(p, width, height) {
    let x = width * p.x, y = height * p.y;
    // Keep outward emitters near the subject, but within reach of wide cards'
    // edges. Only presentation coordinates change, never card geometry.
    if (p.exit === 'left') x = Math.min(x, 88);
    if (p.exit === 'right') x = Math.max(x, width - 88);
    if (p.exit === 'top') y = Math.min(y, 65);
    // Small cards must not send their longer presets into the layer's clip edge.
    const dx = Math.max(-x - 60, Math.min(p.dx, width - x + 60));
    const dy = Math.max(-y - 60, p.dy);
    const length = Math.hypot(dx, dy);
    const nx = -dy / length * p.bend, ny = dx / length * p.bend;
    return [[x, y], [x + dx * .30 + nx, y + dy * .30 + ny],
      [x + dx * .70 + nx, y + dy * .70 + ny], [x + dx, y + dy]];
  }

  function motionPath(p, rect, bounds) {
    const points = trajectory(p, rect.width, rect.height).map(([x, y]) =>
      `${(x + rect.left - bounds.left).toFixed(3)} ${(y + rect.top - bounds.top).toFixed(3)}`);
    return `path("M ${points[0]} C ${points.slice(1).join(', ')}")`;
  }

  function burstBounds(rect, width, height) {
    // Body-level fixed paint avoids card/ancestor clipping and never extends
    // the scrollable document. Bottom clipping keeps names/chips unobscured.
    const left = Math.max(0, rect.left - OVERHANG);
    const top = Math.max(0, rect.top - OVERHANG);
    return { left, top, width:Math.max(0, Math.min(width, rect.right + OVERHANG) - left),
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
          '--spore-path':motionPath(p, rect, bounds),
          '--spore-size':p.size + 'px', '--spore-core':p.core, '--spore-edge':p.edge,
          '--spore-alpha':p.opacity, '--spore-duration':p.duration + 'ms',
          '--spore-delay':p.delay + 'ms'
        };
        for (const [key, value] of Object.entries(vars)) particle.style.setProperty(key, String(value));
        particle.addEventListener('animationend', event => {
          // Appearance also emits animationend; count each particle only once.
          if (event.animationName !== 'poison-spore-motion') return;
          particle.remove();
          if (--remaining === 0) clear(card);
        });
        layer.appendChild(particle);
      }
      doc.body.appendChild(layer);
      // Fallback for interrupted animations; never retain decorative DOM.
      active.set(card, { layer, timer:win.setTimeout(() => clear(card), CLEANUP_MS) });
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
  if (typeof module !== 'undefined') module.exports = { PRESETS, OVERHANG, CLEANUP_MS, trajectory, motionPath, burstBounds, setup };
  if (root.document) root.document.addEventListener('DOMContentLoaded', () => setup(root.document, root));
}(typeof window !== 'undefined' ? window : globalThis));
