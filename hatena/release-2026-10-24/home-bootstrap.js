/* Install only after the exported current footer has been reconciled.
 * The separate header marker is the last, explicit activation step.
 */
(() => {
  'use strict';
  const marker = document.getElementById('kinoko-home-release');
  const query = new URLSearchParams(location.search);
  if (location.origin !== 'https://exsudoporus-ruber.hatenablog.jp' ||
      location.pathname !== '/' || query.has('page') || query.has('kinoko-native') ||
      !document.body.classList.contains('page-index') ||
      marker?.dataset.release !== '2026-10-24' ||
      document.getElementById('kinoko-home-portal') ||
      document.getElementById('photoGallery')) return;
  const content = document.getElementById('content');
  const container = document.getElementById('container-inner');
  if (!content || content.parentElement !== container ||
      !document.querySelector('#main-inner article.entry')) return;

  const portal = document.createElement('section');
  portal.id = 'kinoko-home-portal';
  portal.className = 'new-top-embed';
  portal.setAttribute('aria-label', 'キノコと田舎遊び・新トップ');
  const navigation = document.createElement('nav');
  navigation.className = 'kinoko-home-fallback';
  navigation.setAttribute('aria-label', '記事一覧と表示の切替');
  for (const [text, href] of [
    ['最新記事・過去の記事一覧', '/archive'],
    ['新トップを別画面で開く', 'https://charchan123.github.io/hatena-photo-gallery/new-top.html'],
    ['従来の記事表示', '/?kinoko-native=1'],
    ['RSS', '/rss'],
  ]) {
    const link = document.createElement('a');
    link.textContent = text;
    link.href = href;
    navigation.append(link);
  }
  const status = document.createElement('p');
  status.className = 'kinoko-home-status';
  status.setAttribute('role', 'status');
  status.textContent = '新トップを読み込んでいます。表示されない場合は記事一覧をご利用ください。';
  const frame = document.createElement('iframe');
  frame.id = 'photoGallery';
  frame.title = 'キノコ図鑑・Best Shot・不明キノコ研究室への入口';
  frame.src = 'https://charchan123.github.io/hatena-photo-gallery/new-top.html';
  frame.width = '100%';
  frame.height = '600';
  frame.setAttribute('allowfullscreen', '');
  frame.setAttribute('scrolling', 'no');
  // Exactly the permissions observed on the existing /new-top embed; no expansion.
  frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-pointer-lock allow-popups allow-downloads allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation allow-presentation allow-orientation-lock allow-modals');
  const menu = document.createElement('details');
  menu.className = 'kinoko-home-navigation';
  menu.hidden = true;
  const menuTitle = document.createElement('summary');
  menuTitle.textContent = 'MENU · 記事一覧と表示の切替';
  menu.append(menuTitle, navigation);
  let failed = false;
  frame.addEventListener('kinoko:height-ready', () => {
    if (failed || frame.getBoundingClientRect().height <= 0) return;
    status.hidden = true;
    document.body.classList.remove('kinoko-home-pending');
    document.body.classList.add('kinoko-home-active');
  });
  portal.append(status, frame, menu);
  container.insertBefore(portal, content);
  document.body.classList.add('kinoko-home-ready');
  setTimeout(() => {
    if (!status.hidden) {
      failed = true;
      menu.hidden = false;
      menu.open = true;
      frame.hidden = true;
      document.body.classList.remove('kinoko-home-pending', 'kinoko-home-ready', 'kinoko-home-active');
      status.textContent = '新トップを確認できません。記事一覧・従来表示のリンクをご利用ください。';
    }
  }, 8000);
})();
