"use strict";

(() => {
  const root = document.querySelector("#guide-review");
  const find = selector => root.querySelector(selector);
  const labelStatus = {
    pending: "未確認", confirmed: "名称確認済み", individual: "個別確認",
    held: "保留", recheck: "再確認", verify: "画像の再照合待ち",
    stale: "再確認が必要", reset: "訂正", note: "メモ保存", locked: "後工程",
  };
  const kindLabels = {name: "写真と名称", manuscript: "図鑑原稿", food: "食毒情報", features: "特徴検索", publication: "公開"};
  const feedback = find("#guide-feedback");
  const itemRegion = find("#guide-item");
  const selection = find("#guide-items");
  const viewer = window.adminPhotoViewer;
  const visiblePhotos = new Map();
  let data, token, selected, view = 0, saving = false;
  const labels = {
    restored: "バックアップから復元したため再確認", image: "画像の内容が変わったため再確認",
    membership: "写真の構成が変わったため再確認", article: "記事の記録が変わったため再確認",
    manuscript: "原稿・出典が更新されたため再確認", corrected: "確認内容を訂正したため未確認",
    updated: "確認対象の情報が更新されています",
  };
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem("kinoko-guide-review-inputs")) || {}; } catch {}
  let reviewer = typeof preferences.reviewer === "string" ? preferences.reviewer.slice(0, 80) : "";
  const notes = new Map(Object.entries(preferences.notes || {}).filter(([key, value]) =>
    /^[a-f0-9]{64}$/.test(key) && typeof value === "string" && value.length <= 2000));
  const filterIds = ["#guide-search", "#guide-priority", "#guide-size", "#guide-status"];
  const individualMode = new Set();
  let scrollTarget = null;
  for (const id of filterIds) {
    const field = find(id), saved = preferences.filters?.[id];
    if (typeof saved === "string" && (field.tagName !== "SELECT" || [...field.options].some(x => x.value === saved))) field.value = saved;
  }
  function remember() {
    try {
      localStorage.setItem("kinoko-guide-review-inputs", JSON.stringify({
        reviewer, item: selected, notes: Object.fromEntries(notes),
        filters: Object.fromEntries(filterIds.map(id => [id, find(id).value])),
      }));
    } catch { /* The SQLite confirmation API is independent of browser preferences. */ }
  }
  let objectUrls = [];
  const loaded = new Map();

  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function action(title, invoke, className) {
    const button = element("button", title, className);
    button.type = "button";
    button.onclick = invoke;
    return button;
  }

  function link(url, title) {
    try {
      const parsed = new URL(url);
      if (!["https:", "http:"].includes(parsed.protocol)) return element("span", title);
      const anchor = element("a", title);
      anchor.href = parsed.href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      return anchor;
    } catch {
      return element("span", title);
    }
  }

  function report(message, error = false) {
    feedback.textContent = message;
    feedback.classList.toggle("error", error);
  }

  async function request(path, body) {
    const options = body === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": token},
      body: JSON.stringify(body),
    };
    const response = await fetch("/api/guide-review/" + path, options);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "操作に失敗しました");
    return result;
  }

  function normal(value) {
    return value.normalize("NFKC").toLowerCase().replace(/[ぁ-ゖ]/g, c => String.fromCharCode(c.charCodeAt(0) + 96));
  }

  function filtered() {
    const q = normal(find("#guide-search").value.trim());
    const priority = find("#guide-priority").value;
    const size = Number(find("#guide-size").value);
    const status = find("#guide-status").value;
    return (data?.rows || []).filter(row =>
      normal(row.name).includes(q) &&
      (!priority || (priority === "priority" ? row.priority_candidate : row.group === priority)) &&
      (!size || (size === 3 ? row.count >= 3 : row.count === size)) &&
      (!status || row.status === status))
      .sort((a, b) => Number(b.priority_candidate) - Number(a.priority_candidate) ||
        (a.name === "センニンタケ" ? -1 : b.name === "センニンタケ" ? 1 : a.priority - b.priority) ||
        a.name.localeCompare(b.name, "ja"));
  }

  function updateList() {
    const rows = data.rows;
    find('#guide-priority option[value="priority"]').textContent = `優先候補（${rows.filter(row => row.priority_candidate).length}件）`;
    const counts = {"対象": rows.length};
    for (const key of ["confirmed", "pending", "individual", "held", "recheck"]) {
      counts[labelStatus[key]] = rows.filter(row => row.status === key).length;
    }
    counts["原稿承認済み"] = rows.filter(row => row.manuscript === "confirmed").length;
    find("#guide-counts").replaceChildren(...Object.entries(counts).map(([key, value]) => {
      const box = element("div");
      box.append(element("span", key), element("strong", String(value)));
      return box;
    }));
    const rowsFiltered = filtered();
    selection.replaceChildren(...rowsFiltered.map(row => {
      const option = element("option", `${row.name} · ${row.count}枚 · ${labelStatus[row.status]}${row.scope ? "" : "（関連）"}`);
      option.value = row.id;
      return option;
    }));
    selection.value = selected || "";
    if (selection.selectedIndex >= 0) {
      const option = selection.options[selection.selectedIndex];
      selection.scrollTop = Math.max(0, option.offsetTop - selection.options[0].offsetTop - selection.clientHeight / 2);
    }
    const allPriority = rows.filter(row => row.priority_candidate);
    const rank = allPriority.slice().sort((a, b) => (a.name === "センニンタケ" ? -1 : b.name === "センニンタケ" ? 1 : a.priority - b.priority) || a.name.localeCompare(b.name, "ja"))
      .findIndex(row => row.id === selected);
    const remaining = allPriority.filter(row => row.status !== "confirmed").length;
    find("#guide-progress").textContent = `確認対象 ${rows.filter(row => row.scope).length}項目＋関連${rows.filter(row => !row.scope).length}件 · 優先候補 ${rank >= 0 ? `${rank + 1} / ` : ""}${allPriority.length}件（残り${remaining}件）`;
    find("#guide-select-label").firstChild.textContent = `対象項目（${rowsFiltered.length}件）`;
  }

  function navigation(id, direction, pendingOnly = false) {
    const rows = filtered();
    const index = rows.findIndex(row => row.id === id);
    const options = index < 0 ? rows : direction < 0 ? rows.slice(0, index).reverse()
      : [...rows.slice(index + 1), ...(pendingOnly ? rows.slice(0, index) : [])];
    return options.find(row => !pendingOnly || ["pending", "individual", "recheck"].includes(row.status))?.id;
  }

  async function open(id, useFirst = true) {
    const stamp = ++view;
    itemRegion.inert = true;
    try {
      const result = await request(id ? "state?" + new URLSearchParams({item: id}) : "state");
      if (stamp !== view) return;
      data = result;
      token = result.csrf;
      selected = id;
      const first = useFirst && !id && filtered()[0];
      if (id && !filtered().some(row => row.id === id) && useFirst) return open(filtered()[0]?.id, false);
      if (first) return open(first.id);
      remember();
      updateList();
      render(result.item, stamp);
      if (!feedback.textContent) report(result.revision ? `保存済みの履歴を復元しました（改訂 ${result.revision}）` : "保存済みの確認記録はありません");
    } catch (error) {
      if (stamp !== view) return;
      render(null, stamp);
      report(error.message, true);
    } finally {
      if (stamp === view) itemRegion.inert = false;
    }
  }

  async function save(item, kind, decision, scope, ids, next = null) {
    if (saving) return;
    if (!reviewer.trim()) {
      report("確認者の名前を入力してください", true);
      const field = find("#guide-reviewer");
      field.closest("details").open = true;
      field.focus();
      return;
    }
    if (kind !== "name" && decision === "confirmed" &&
        !window.confirm(`${item.name}の${kindLabels[kind]}の審査結果を記録しますか？`)) return;
    const tickets = kind === "name" && decision === "confirmed" ?
      Object.fromEntries(ids.map(id => [id, loaded.get(id)])) : {};
    saving = true;
    itemRegion.inert = true;
    report("保存しています…");
    try {
      const result = await request("save", {
        revision: data.revision, item: item.id, kind, decision, scope, photos: ids, tickets,
        reviewer, note: notes.get(item.id) || "", ack: decision === "confirmed",
        view_basis: item.view_basis[kind],
      });
      report(`保存しました（改訂 ${result.revision}）`);
      notes.delete(item.id);
      if (scope === "photo") scrollTarget = ids[0];
      await open(next || item.id, false);
      if (next) itemRegion.scrollIntoView({block: "start"});
    } catch (error) {
      report(error.message, true);
    } finally {
      itemRegion.inert = false;
      saving = false;
    }
  }

  function control(label, id, value, onInput, multiline = false) {
    const field = element("label", label);
    const input = element(multiline ? "textarea" : "input");
    input.id = id;
    input.maxLength = multiline ? 2000 : 80;
    input.value = value;
    input.oninput = () => onInput(input.value);
    field.append(input);
    return field;
  }

  function details(title, content) {
    const container = element("details");
    container.append(element("summary", title), content);
    return container;
  }

  function manuscript(item) {
    const draft = item.draft;
    const box = element("div", undefined, "guide-editorial");
    const preview = element("article", undefined, "guide-manuscript-preview");
    preview.append(element("p", "原稿候補のプレビュー"), element("h4", item.name),
      element("p", draft.status || "原稿なし"));
    const fields = element("dl");
    const names = {"資料掲載学名": "学名", "科": "科名", "属": "属名"};
    for (const key of ["資料掲載学名", "科", "属", "生態", "特徴", "生育環境", "発生時期", "食毒"]) {
      const value = draft.fields[key];
      const text = key === "食毒" && item.editorial.food !== "confirmed" ? "別途審査中" : value || "確認中";
      fields.append(element("dt", names[key] || key), element("dd", text));
    }
    fields.append(element("dt", "注意事項"), element("dd", "資料に基づく原稿候補です。掲載写真への適用は個別に確認します。"));
    preview.append(fields);
    const research = element("div");
    research.append(element("p", draft.reference || ""), element("p", draft.notes || ""));
    if (draft.fields["食毒"]) research.append(element("p", "審査用の食毒記録 " + draft.fields["食毒"]));
    const proposal = details("原稿の修正案を保存", element("div"));
    proposal.addEventListener("toggle", () => {
      if (proposal.open && !proposal.dataset.loaded) {
        proposal.dataset.loaded = "true";
        proposalForm(item, proposal.lastElementChild);
      }
    });
    const urls = new Map(draft.preview.sources.map(s => [s.url, s.title]));
    draft.sources.forEach(s => urls.set(s.URL, s["資料名"]));
    const sources = element("ul");
    urls.forEach((title, url) => {
      const line = element("li");
      line.append(link(url, title || "出典を開く"));
      sources.append(line);
    });
    if (sources.childElementCount) preview.append(element("h5", "出典"), sources);
    box.append(preview, details("調査資料・原典の適用範囲", research), proposal);
    for (const kind of ["manuscript", "food", "features", "publication"]) {
      const status = kind === "publication" ? item.publication : item.editorial[kind];
      const section = element("section");
      section.append(element("h4", `${kindLabels[kind]} · ${status === "confirmed" ? "審査承認済み" : labelStatus[status] || status}`));
      if (item.editorial_reasons[kind]) section.append(element("p", labels[item.editorial_reasons[kind]]));
      if (kind === "publication") {
        section.append(element("p", "公開は別の審査工程で承認します。"));
      } else {
        const approve = action(kindLabels[kind] + "を承認", () => save(item, kind, "confirmed", "editorial", []));
        approve.disabled = !item.reviewable[kind];
        section.append(approve,
          action(kindLabels[kind] + "を保留", () => save(item, kind, "held", "editorial", [])),
          action(kindLabels[kind] + "の承認を訂正", () => save(item, kind, "reset", "editorial", [])));
        if (!item.reviewable[kind]) section.append(element("p", kind === "features" ?
          "特徴検索の審査候補は「情報拡充」で確認できます。" : "承認に必要な原稿または根拠資料を確認中です。"));
      }
      box.append(section);
    }
    return details("図鑑原稿・出典・個別審査", box);
  }

  async function proposalForm(item, region) {
    const status = element("p");
    status.setAttribute("role", "status");
    region.replaceChildren(status);
    try {
      const saved = await request("proposal?" + new URLSearchParams({item: item.id}));
      const current = saved.proposal;
      const field = element("select"), label = element("label", "修正対象");
      for (const key of Object.keys(item.draft.fields)) field.append(new Option(key, key));
      if (current) field.value = current.field;
      label.append(field);
      const before = element("p", item.draft.fields[field.value] || "記載なし");
      const after = control("修正案", "guide-proposal-after", current?.after || "", () => {}, true);
      const reason = control("修正理由・根拠", "guide-proposal-reason", current?.reason || "", () => {}, true);
      after.querySelector("textarea").maxLength = 4000;
      const check = element("input");
      check.type = "checkbox";
      const ack = element("label");
      ack.append(check, "元資料と現在の原稿を照合しました");
      field.onchange = () => {
        before.textContent = item.draft.fields[field.value] || "記載なし";
        check.checked = false;
      };
      async function submit(value) {
        submitButton.disabled = cancel.disabled = true;
        try {
          const result = await request("proposal", {item: item.id, revision: saved.revision,
            basis: item.view_basis.manuscript, proposal: value});
          saved.revision = result.revision;
          status.textContent = value ? "修正案を保存しました。原稿と承認の状態は独立しています。" : "修正案を取り消しました。";
          cancel.hidden = !value;
          if (!value) for (const area of region.querySelectorAll("textarea")) area.value = "";
          check.checked = false;
        } catch (error) { status.textContent = error.message; }
        finally { submitButton.disabled = cancel.disabled = false; }
      }
      const submitButton = action("修正案を保存", () => submit({
        field: field.value, before: item.draft.fields[field.value],
        after: after.querySelector("textarea").value, reason: reason.querySelector("textarea").value,
        checked: check.checked,
      }));
      const cancel = action("保存済みの修正案を取り消す", () => {
        if (window.confirm("この修正案を取り消しますか？")) submit(null);
      });
      cancel.hidden = !current;
      if (saved.stale) status.textContent = "元原稿が改訂されました。現在の文章と根拠を確認してから保存してください。";
      if (saved.stale && current) region.append(element("p", "修正案を作ったときの原文 " + current.before));
      region.append(label, element("strong", "現在の文章"), before, after, reason, ack, submitButton, cancel);
    } catch (error) { status.textContent = error.message; }
  }

  async function photoCard(row, item, number, stamp, readiness) {
    const p = row.identity;
    const evidence = row.evidence;
    const card = element("article", undefined, "guide-photo");
    card.dataset.photoId = p.id;
    card.append(element("h4", `写真 ${number} · ${labelStatus[item.photo_states[p.id]]}`));
    const reason = element("p", labels[item.photo_reasons[p.id]] || "", "guide-reason");
    card.append(reason);
    const image = element("img");
    image.alt = `${item.name}の写真 ${number}`;
    const entry = {alt: image.alt, caption: `写真 ${number} · ${item.name}`};
    const picture = action("", () => {
      const entries = item.photos.map(row => visiblePhotos.get(row.identity.id)).filter(Boolean);
      viewer.open(entries, entry, picture);
    }, "guide-thumbnail");
    picture.setAttribute("aria-label", "写真を拡大");
    const failure = element("span", "画像の取得中");
    picture.append(image, failure);
    const retry = action("写真を再取得", () => loadImage(), "guide-photo-retry");
    retry.hidden = true;
    picture.disabled = true;
    image.hidden = true;
    const captureSource = row.date_source === "exif" ? "（EXIF）" : "";
    card.append(picture, retry, element("p", `撮影日${captureSource} ${p.capture || "不明"}`),
      link(p.article, evidence?.title || "元記事を開く"));
    const excerpt = element("div");
    if (evidence) {
      excerpt.append(element("p", [evidence.block ? `本文ブロック ${evidence.block}` : "", evidence.heading, evidence.evidence].filter(Boolean).join(" · ")));
      if (evidence.alt || evidence.caption) excerpt.append(element("p", [evidence.alt, evidence.caption].filter(Boolean).join(" ／ ")));
      if (evidence.context) excerpt.append(element("p", evidence.context));
      if (evidence.history) excerpt.append(element("p", evidence.history));
    } else {
      excerpt.append(element("p", "監査時の記述と照合できません。元記事でこの写真の前後を確認してください。"));
    }
    const title = evidence?.title || "";
    const recordedDate = title.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
    if (row.published) card.append(element("p", `記事の投稿日 ${row.published.slice(0, 10)}`));
    if (recordedDate) {
      const titled = recordedDate[1] + "-" + recordedDate[2].padStart(2, "0") + "-" + recordedDate[3].padStart(2, "0");
      card.append(element("p", "記事タイトルに記載の日付 " + titled));
      if (p.capture && Math.abs(Date.parse(titled) - Date.parse(p.capture)) > 86400000 * 366) {
        card.append(element("p", "撮影日と記事の記載に1年以上の差があります。元記事と元画像を確認してください。", "guide-reason"));
      }
    }
    excerpt.append(element("small", `写真ID ${p.id} · 分類コード ${p.classification}`));
    card.append(details("記事の該当箇所と写真ID", excerpt));
    const one = action("この写真の掲載名を確認", () => save(item, "name", "confirmed", "photo", [p.id]));
    const individual = element("div", undefined, "guide-individual");
    one.disabled = true;
    individual.append(one, action("この写真を保留", () => save(item, "name", "held", "photo", [p.id])),
      action("この写真の確認を訂正", () => save(item, "name", "reset", "photo", [p.id])));
    card.append(individual);
    const photographs = find("#guide-photos");
    photographs.append(card);
    await loadImage();

    async function loadImage() {
      retry.hidden = true;
      failure.textContent = "画像の取得中";
      try {
        const params = new URLSearchParams({item: item.id, id: p.id});
        const response = await fetch("/api/guide-review/photo?" + params);
        const ticket = response.headers.get("X-Guide-Photo-Ticket");
        if (!response.ok || !ticket) throw new Error();
        const blob = await response.blob();
        if (stamp !== view) return;
        image.src = URL.createObjectURL(blob);
        objectUrls.push(image.src);
        await image.decode();
        if (stamp !== view) return;
        if (!image.naturalWidth) throw new Error();
        image.hidden = false;
        failure.hidden = true;
        picture.disabled = false;
        one.disabled = false;
        entry.src = image.src;
        visiblePhotos.set(p.id, entry);
        loaded.set(p.id, ticket);
      } catch {
        if (stamp !== view) return;
        failure.textContent = "画像を読み込めません。";
        retry.hidden = false;
      }
      readiness();
    }
  }

  function render(item, stamp) {
    viewer.close();
    visiblePhotos.clear();
    objectUrls.forEach(url => URL.revokeObjectURL(url));
    objectUrls = [];
    loaded.clear();
    itemRegion.replaceChildren();
    if (!item) {
      itemRegion.append(element("p", "表示する項目がありません。"));
      return;
    }
    const ids = item.photos.map(p => p.identity.id);
    const prev = navigation(item.id, -1);
    const next = navigation(item.id, 1);
    const pending = navigation(item.id, 1, true);
    const nav = element("div", undefined, "guide-nav");
    const previous = action("前の項目", () => open(prev));
    previous.disabled = !prev;
    const advance = action("次の未確認項目", () => open(pending));
    advance.disabled = !pending;
    nav.append(previous, advance);
    const title = element("h3", item.name);
    const line = element("p", `区分 ${item.group} · 公開写真 ${ids.length}枚 · ${labelStatus[item.status]}`);
    itemRegion.append(nav, title, line, element("p", item.question));
    if (item.reason) itemRegion.append(details("確認対象の背景", element("p", item.reason, "meta")));
    const identity = element("div");
    identity.append(control("確認者", "guide-reviewer", reviewer, v => { reviewer = v; remember(); }),
      control("確認メモ", "guide-note", notes.get(item.id) || "", v => { notes.set(item.id, v); remember(); }, true));
    if (item.legacy_ids.length) identity.append(link("https://github.com/charchan123/hatena-photo-gallery/pull/163", "過去の指定3枚の記録"));
    const photos = element("div", undefined, "guide-photos");
    photos.id = "guide-photos";
    photos.classList.toggle("guide-show-individual", individualMode.has(item.id));
    itemRegion.append(photos);
    const history = element("ol");
    for (const event of [...item.history].reverse()) {
      const entry = element("li", `改訂 ${event.revision} · ${new Date(event.at).toLocaleString("ja-JP")} · ${event.reviewer} · ${kindLabels[event.kind]}／${event.decision === "confirmed" && event.kind !== "name" ? "承認済み" : labelStatus[event.decision]}${event.kind === "name" ? ` · ${event.photos.length}枚` : ""}${event.local ? "" : " · バックアップから復元"}`);
      if (event.note) entry.append(element("p", event.note));
      if (event.photos.length) {
        const recorded = element("ul");
        for (const photo of event.photos) {
          recorded.append(element("li", `${photo.id} · ${photo.capture || "日付不明"}`));
        }
        entry.append(details("当時の対象写真", recorded));
      }
      history.append(entry);
    }
    if (!item.history.length) history.append(element("li", "新しい確認記録はありません"));

    const dock = element("div", undefined, "guide-dock");
    const check = element("p");
    check.setAttribute("role", "status");
    const all = action(`全${ids.length}枚の名称を確認して次へ`, () => save(item, "name", "confirmed", "all", ids, pending || next), "primary");
    const legacy = action("旧承認の指定3枚を再確認して保存", () => save(item, "name", "confirmed", "legacy", item.legacy_ids, pending || next));
    legacy.hidden = !item.legacy_ids.length;
    const individual = action("写真ごとに確認", () => {
      if (photos.classList.toggle("guide-show-individual")) individualMode.add(item.id);
      else individualMode.delete(item.id);
      individual.setAttribute("aria-expanded", String(individualMode.has(item.id)));
      photos.scrollIntoView({block: "start"});
    });
    individual.setAttribute("aria-expanded", String(individualMode.has(item.id)));
    const hold = action("保留して次へ", () => save(item, "name", "held", "all", ids, pending || next));
    dock.append(check, all, individual, hold);
    identity.append(legacy, action("メモを保存", () => save(item, "name", "note", "all", ids)),
      action("名称確認を訂正・再確認", () => {
        if (window.confirm(`${item.name}の名称確認を再開しますか？ 過去の記録は履歴に残ります。`))
          return save(item, "name", "reset", "all", ids);
      }));
    const supplemental = details(`確認者・メモ・訂正（${reviewer || "確認者未入力"}）`, identity);
    itemRegion.append(dock, supplemental, manuscript(item), details("確認履歴", history));
    function readiness() {
      check.textContent = `表示できた写真 ${loaded.size}／${ids.length}枚。写真を見てから、確認ボタンで記録してください。`;
      all.disabled = !ids.length || loaded.size !== ids.length || !["A", "B"].includes(item.group);
      legacy.disabled = item.legacy_ids.length !== 3 || !item.legacy_ids.every(key => loaded.has(key));
    }
    readiness();
    Promise.all(item.photos.map((row, i) => photoCard(row, item, i + 1, stamp, readiness))).then(async () => {
      if (stamp !== view || !ids.length) return;
      if (scrollTarget) {
        const card = Array.from(photos.children).find(node => node.dataset.photoId === scrollTarget);
        card?.scrollIntoView({block: "center"});
        card?.querySelector(".guide-individual button")?.focus({preventScroll: true});
        scrollTarget = null;
      }
      try {
        const latest = await request("state?" + new URLSearchParams({item: item.id}));
        if (stamp !== view) return;
        // Keep the revision of the displayed history. A concurrent save must
        // still fail rather than silently using a newer revision.
        if (latest.revision !== data.revision) return;
        data.rows = latest.rows;
        updateList();
        line.textContent = `区分 ${item.group} · 公開写真 ${ids.length}枚 · ${labelStatus[latest.item.status]}`;
        photos.querySelectorAll("h4").forEach((heading, i) => {
          heading.textContent = `写真 ${i + 1} · ${labelStatus[latest.item.photo_states[ids[i]]]}`;
          heading.parentElement.querySelector(".guide-reason").textContent = labels[latest.item.photo_reasons[ids[i]]] || "";
        });
      } catch (error) { if (stamp === view) report(error.message, true); }
    });
  }

  selection.addEventListener("change", () => open(selection.value));
  for (const id of filterIds) {
    find(id).addEventListener(id === "#guide-search" ? "input" : "change", () => {
      if (!data) return;
      remember();
      updateList();
      if (!filtered().some(row => row.id === selected)) open(filtered()[0]?.id, false);
    });
  }
  find("#guide-refresh").onclick = async () => {
    try {
      await request("refresh", {});
      report("公開データと保存記録を再取得しました");
      await open(selected);
    } catch (error) { report(error.message, true); }
  };
  find("#guide-export").onclick = async () => {
    try {
      const result = await request("export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type: "application/json"}));
      const download = element("a");
      download.href = url;
      download.download = "kinoko-guide-review.json";
      download.click();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
    } catch (error) { report(error.message, true); }
  };
  find("#guide-restore").onclick = async () => {
    if (!data || saving) return;
    const file = find("#guide-import").files[0];
    if (!file || file.size > 18_000_000) {
      report("18MB以下の確認記録JSONを選択してください", true);
      return;
    }
    try {
      const backup = JSON.parse(await file.text());
      const result = await request("restore", {revision: data.revision, backup});
      report(`照合が完了しました。復元 ${result.saved}件（改訂 ${result.revision}）`);
      await open(selected);
    } catch (error) { report(error.message, true); }
  };
  window.guideReview = {open: () => open(selected || (/^[a-f0-9]{64}$/.test(preferences.item || "") ? preferences.item : undefined))};
})();
