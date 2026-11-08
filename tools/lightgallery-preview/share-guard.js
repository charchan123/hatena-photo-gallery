// Keep the vendor's share menu usable while preventing outside navigation.
function keepLinksLocal() {
  for (const link of document.querySelectorAll('.lg-dropdown a[href]')) {
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) {
      link.dataset.previewDestination = url.hostname || url.protocol;
      link.href = '#preview-share';
      link.removeAttribute('target');
    }
  }
}
new MutationObserver(keepLinksLocal).observe(document, {
  childList: true, subtree: true, attributes: true, attributeFilter: ['href'],
});
document.addEventListener('click', event => {
  const link = event.target.closest?.('a[href]');
  if (!link) return;
  if (link.dataset.previewDestination || new URL(link.href, location.href).origin !== location.origin) {
    event.preventDefault();
    event.stopImmediatePropagation();
    document.querySelector('[data-preview-share-note]')?.remove();
    const note = document.createElement('div');
    note.dataset.previewShareNote = '';
    note.setAttribute('role', 'status');
    note.textContent = '共有先の確認（外部送信なし） ' + (link.dataset.previewDestination || new URL(link.href).hostname);
    note.style.cssText = 'position:fixed;bottom:18%;left:50%;transform:translateX(-50%);z-index:2000;'
      + 'max-width:90vw;padding:10px 14px;background:#21442d;color:white;border-radius:8px;'
      + 'pointer-events:none;text-align:center;font:14px/1.5 system-ui,sans-serif';
    document.body.append(note);
    setTimeout(() => note.remove(), 3000);
  }
}, true);
