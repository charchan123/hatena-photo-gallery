'use strict';
// Compare the styles that match /new-top without authenticated parent state.
// Parent-only rules cannot match; negative host guards always match there.
// Preserve every declaration and all other selectors/media conditions.
function standalonePortalCSS(css) {
  return css
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/[^{}]+\{[^{}]*\}/g, rule => {
      const selector = rule.slice(0, rule.indexOf('{')).trim();
      if (selector.split(',').every(s => s.trim().startsWith(':root[data-portal-columns="2"] '))) return '';
      return rule.replace(/:root:not\(\[data-portal-columns="[12]"\]\) /g, '');
    })
    .replace(/\s+/g, '');
}
module.exports = {standalonePortalCSS};
