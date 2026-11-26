"use strict";

const items = AUDIT.items;
const byId = id => document.getElementById(id);
const labels = {
  A: "既存の写真接続候補承認",
  B: "撮影者に名称を確認",
  C: "写真ごとに確認",
  D: "名称の範囲を確認",
  E: "原記録・専門家に確認",
};
const statuses = {
  unreviewed: "未確認", confirmed: "名称確認済み", individual: "個別確認",
  held: "保留", stale: "再確認",
};
const key = "kinoko-guide-title-review-v1";
const japan = new Intl.Collator("ja");
const detail = byId("detail");
const saveStatus = byId("save-status");
const observationsSignature = item => [item.group, ...item.photos.map(photo => photo.fingerprint).sort()].join(".");
let storageRaw;
let records = {};
let savedName;
let storageReadable = true;

try {
  storageRaw = localStorage.getItem(key);
  if (storageRaw) {
    const stored = JSON.parse(storageRaw);
    if (stored.version !== 1 || !stored.records || Array.isArray(stored.records)) {
      throw new Error("Unable to read the review memo");
    }
    records = stored.records;
    savedName = stored.active;
    saveStatus.textContent = "確認メモを復元しました";
  }
} catch {
  storageReadable = false;
  saveStatus.textContent = "保存済みメモを読み取れません。入力はJSONで保存できます。";
}

let active = items.find(item => item.name === savedName)
  || items.find(item => item.group === "C")
  || items[0];

function status(item) {
  const record = records[item.name];
  if (!record) return "unreviewed";
  if (record.signature !== observationsSignature(item)) return "stale";
  return Object.hasOwn(statuses, record.status) ? record.status : "unreviewed";
}

function persist() {
  if (!storageReadable) return;
  try {
    if (localStorage.getItem(key) !== storageRaw) {
      saveStatus.textContent = "別のタブで保存されました。この画面の変更はJSONで保存してください。";
      return;
    }
    const next = JSON.stringify({version: 1, active: active.name, records});
    localStorage.setItem(key, next);
    storageRaw = next;
    saveStatus.textContent = "このブラウザに保存しました";
  } catch {
    saveStatus.textContent = "ブラウザに保存できません。変更をJSONで保存してください。";
  }
}

function saveRecord(item, checked, note, nextStatus) {
  if (status(item) === "stale") return;
  records[item.name] = {signature: observationsSignature(item), checked: [...checked], note, status: nextStatus};
  persist();
  drawProgress();
  drawQueue();
}

function element(kind, text, className) {
  const node = document.createElement(kind);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function safeLink(address, title) {
  const link = element("a", title);
  try {
    const url = new URL(address);
    if (url.protocol !== "https:") return element("span", title);
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  } catch {
    return element("span", title);
  }
  return link;
}

function drawProgress() {
  const inScope = items.filter(item => item.scope);
  const count = value => inScope.filter(item => status(item) === value).length;
  const confirmed = count("confirmed");
  byId("progress").value = confirmed;
  byId("progress-label").textContent = confirmed + " / " + inScope.length;
  byId("totals").textContent = "未確認 " + count("unreviewed") + "件　個別確認 " + count("individual")
    + "件　保留 " + count("held") + "件　再確認 " + count("stale") + "件";
}

function drawQueue() {
  const queue = byId("queue");
  const focused = queue.contains(document.activeElement) ? document.activeElement.dataset.name : null;
  queue.replaceChildren();
  const search = byId("search").value.trim().normalize("NFKC");
  const filter = byId("state").value;
  const filtered = items.filter(item => item.name.normalize("NFKC").includes(search)
    && (filter === "all" || status(item) === filter));
  const byPriority = (a, b) => (a.priority ?? 999) - (b.priority ?? 999) || japan.compare(a.name, b.name);
  filtered.sort(byId("order").value === "photos"
    ? (a, b) => b.photos.length - a.photos.length || byPriority(a, b)
    : byPriority);
  byId("results").textContent = filtered.length + "件（関連項目を含む）";
  for (const item of filtered) {
    const button = element("button");
    button.type = "button";
    button.dataset.name = item.name;
    button.setAttribute("aria-current", String(item === active));
    button.append(element("span", item.name),
      element("span", item.photos.length + "枚 · " + (status(item) === "unreviewed" ? item.group : statuses[status(item)]), "queue-meta"));
    button.addEventListener("click", () => {
      active = item;
      persist();
      drawQueue();
      drawDetail();
      detail.focus();
    });
    const row = element("li");
    row.append(button);
    queue.append(row);
    if (focused === item.name) button.focus({preventScroll: true});
  }
}

const photoStatus = {
  confirmed_named_mushroom: "現行ルールの確定名分類",
  legacy_undetected: "旧方式・本文から名称未検出",
  legacy_review: "旧方式・要確認",
};

function photoCard(item, photo, checked, onChange, readOnly) {
  const attention = photo.evidence !== "同じ節の見出しが一致" || photo.status === "legacy_undetected";
  const card = element("article", null, attention ? "photo photo-attention" : "photo");
  const image = element("img");
  image.alt = item.name + "の掲載写真（" + (photo.date || "撮影日不明") + "）";
  image.width = 320;
  image.height = 240;
  image.loading = "lazy";
  image.src = photo.src;
  const body = element("div", null, "photo-body");
  const label = element("label", null, "photo-check");
  const box = element("input");
  box.type = "checkbox";
  box.disabled = readOnly;
  box.checked = checked.has(photo.id);
  box.addEventListener("change", () => {
    if (box.checked) checked.add(photo.id);
    else checked.delete(photo.id);
    onChange();
  });
  label.append(box, element("span", "この写真の名称を確認"));
  const context = element("details", null, "context");
  context.append(element("summary", "記事の該当箇所と照合ID"),
    element("p", "節見出し　" + (photo.heading || "該当なし")),
    element("p", "画像ALT　" + (photo.alt || "未記載")));
  if (photo.context) context.append(element("p", photo.context));
  context.append(element("code", photo.id), safeLink(photo.src, "元画像を開く"));
  body.append(label, element("p", "撮影日　" + (photo.date || "不明")),
    element("p", photoStatus[photo.status] || photo.status, "metadata"),
    element("p", photo.evidence, "evidence"), safeLink(photo.article, photo.title || "元記事を開く"), context);
  card.append(image, body);
  return card;
}

function manuscriptPanel(draft) {
  const panel = element("section", null, "manuscript");
  panel.append(element("h3", "図鑑原稿と出典"));
  panel.append(element("p", (draft.status || "参照できる先行原稿なし") + (draft.title ? " · " + draft.title : ""), "metadata"));
  if (draft.scientific) panel.append(element("p", "資料掲載学名　" + draft.scientific));
  if (draft.summary) panel.append(element("p", "特徴　" + draft.summary));
  if (draft.habitat) panel.append(element("p", "生育環境　" + draft.habitat));
  if (draft.season) panel.append(element("p", "発生時期　" + draft.season));
  const sourceList = element("ul");
  for (const source of draft.sources) {
    const entry = element("li");
    entry.append(safeLink(source.url, source.title));
    sourceList.append(entry);
  }
  if (draft.sources.length) panel.append(sourceList);
  if (draft.status) {
    const pr = draft.title.match(/#([0-9]+)/);
    if (pr) panel.append(safeLink(
      "https://github.com/charchan123/hatena-photo-gallery/pull/" + pr[1] + "/files", "先行原稿の審査資料を開く"));
  }
  panel.append(element("p", "解説、特徴検索、食毒、公開はそれぞれ審査します。", "metadata"));
  return panel;
}

function drawDetail() {
  const item = active;
  const record = records[item.name];
  const current = status(item);
  const stale = current === "stale";
  const knownPhotos = new Set(item.photos.map(photo => photo.id));
  const checked = new Set(stale ? [] : (record?.checked ?? []).filter(id => knownPhotos.has(id)));
  const fullReview = item.group === "B" || item.group === "C";
  detail.replaceChildren(
    element("h2", item.name, "detail-title"),
    element("p", labels[item.group] + " · " + item.photos.length + "枚 · "
      + new Set(item.photos.map(photo => photo.article)).size + "記事 · " + statuses[current]
      + (item.scope ? "" : " · 関連項目"), "subhead"));
  const prompt = element("section", null, "question");
  prompt.append(element("h3", "確認してほしいこと"), element("p", item.question),
    element("p", item.reason, "metadata"));
  detail.append(prompt);
  if (stale) detail.append(element("p", "写真または記事証拠が更新されています。以前のメモはJSONに残ります。再確認を始めるまでこの項目は読み取り専用です。"));
  const grid = element("div", null, "photo-grid");
  const note = element("textarea");
  note.id = "review-note";
  note.maxLength = 2000;
  note.value = record?.note ?? "";
  note.disabled = stale;
  const confirm = element("button", "全写真の名称確認を記録");
  confirm.type = "button";
  const confirmState = element("p", null, "metadata");
  function refreshButtons() {
    confirm.disabled = !fullReview || stale || checked.size !== item.photos.length;
    confirmState.textContent = checked.size + " / " + item.photos.length + "枚を選択";
  }
  function change(nextStatus) {
    saveRecord(item, checked, note.value, nextStatus);
    refreshButtons();
  }
  function saveDecision(nextStatus) {
    const parent = document.activeElement;
    change(nextStatus);
    detail.querySelector(".subhead").textContent = labels[item.group] + " · " + item.photos.length + "枚 · "
      + new Set(item.photos.map(photo => photo.article)).size + "記事 · " + statuses[status(item)]
      + (item.scope ? "" : " · 関連項目");
    parent?.focus({preventScroll: true});
  }
  const photos = [...item.photos].sort((left, right) => Number(right.evidence !== "同じ節の見出しが一致")
    - Number(left.evidence !== "同じ節の見出しが一致"));
  for (const photo of photos) {
    grid.append(photoCard(item, photo, checked, () => {
      const previous = status(item);
      saveDecision(previous === "confirmed" ? "individual" : previous);
    }, stale));
  }
  detail.append(element("h3", "公開写真"), grid, manuscriptPanel(item.draft));
  const draft = element("section", null, "draft");
  const noteLabel = element("label", "確認メモ");
  noteLabel.htmlFor = note.id;
  const actions = element("div", null, "actions");
  for (const [value, text] of [["individual", "個別確認として記録"], ["held", "保留にする"]]) {
    const button = element("button", text, "secondary");
    button.type = "button";
    button.disabled = stale;
    button.addEventListener("click", () => saveDecision(value));
    actions.append(button);
  }
  confirm.addEventListener("click", () => {
    if (!confirm.disabled && checked.size === item.photos.length) saveDecision("confirmed");
  });
  note.addEventListener("input", () => change(status(item)));
  draft.append(element("h3", "このブラウザの確認記録"), noteLabel, note, confirmState);
  if (fullReview) actions.prepend(confirm);
  draft.append(actions);
  detail.append(draft);
  refreshButtons();
}

function saveExport() {
  const data = items.filter(item => Object.hasOwn(records, item.name)).map(item => ({
    name: item.name, recordedFor: records[item.name].signature, ...records[item.name], reviewState: status(item),
  }));
  const payload = {version: 1, purpose: "local_review_notes_only", main: AUDIT.main, pages: AUDIT.pages, records: data};
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
  const anchor = element("a");
  anchor.href = url;
  anchor.download = "kinoko-guide-review-notes.json";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

byId("search").addEventListener("input", drawQueue);
byId("order").addEventListener("change", drawQueue);
byId("state").addEventListener("change", drawQueue);
byId("export").addEventListener("click", saveExport);
drawProgress();
drawQueue();
drawDetail();
