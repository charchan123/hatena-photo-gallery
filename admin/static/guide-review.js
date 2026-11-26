"use strict";

(() => {
  const root = document.querySelector("#guide-review");
  const find = selector => root.querySelector(selector);
  const labelStatus = {
    pending: "未確認", confirmed: "名称確認済み", individual: "個別確認",
    held: "保留", recheck: "再確認", verify: "画像の再照合待ち",
    stale: "変更あり・再確認", reset: "訂正", note: "メモ保存", locked: "後工程",
  };
  const kindLabels = {name: "写真と名称", manuscript: "図鑑原稿", food: "食毒情報", features: "特徴検索", publication: "公開"};
  const feedback = find("#guide-feedback");
  const itemRegion = find("#guide-item");
  const selection = find("#guide-items");
  const zoom = find("#guide-zoom");
  let data, token, selected, view = 0, saving = false;
  let reviewer = "";
  const notes = new Map();
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
      if (first) return open(first.id);
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
      find("#guide-reviewer").focus();
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
    box.append(element("p", draft.status || "原稿なし"), element("p", draft.reference || ""));
    const fields = element("dl");
    for (const [key, value] of Object.entries(draft.fields)) {
      if (value) fields.append(element("dt", key), element("dd", value));
    }
    box.append(fields);
    if (draft.notes) box.append(element("p", draft.notes));
    const urls = new Map(draft.preview.sources.map(s => [s.url, s.title]));
    draft.sources.forEach(s => urls.set(s.URL, s["資料名"]));
    const sources = element("ul");
    urls.forEach((title, url) => {
      const line = element("li");
      line.append(link(url, title || "出典を開く"));
      sources.append(line);
    });
    box.append(sources);
    for (const kind of ["manuscript", "food", "features", "publication"]) {
      const status = kind === "publication" ? item.publication : item.editorial[kind];
      const section = element("section");
      section.append(element("h4", `${kindLabels[kind]} · ${status === "confirmed" ? "審査承認済み" : labelStatus[status] || status}`));
      if (kind === "publication") {
        section.append(element("p", "公開は別の審査工程で承認します。"));
      } else {
        const approve = action("この審査を承認して保存", () => save(item, kind, "confirmed", "editorial", []));
        approve.disabled = !item.reviewable[kind];
        section.append(approve,
          action("保留", () => save(item, kind, "held", "editorial", [])),
          action("審査状態を訂正", () => save(item, kind, "reset", "editorial", [])));
        if (kind === "features") section.append(element("p", "特徴の割当候補は「情報拡充」で確認できます。"));
      }
      box.append(section);
    }
    return details("図鑑原稿・出典・個別審査", box);
  }

  async function photoCard(row, item, number, stamp, readiness) {
    const p = row.identity;
    const evidence = row.evidence;
    const card = element("article", undefined, "guide-photo");
    card.append(element("h4", `写真 ${number} · ${labelStatus[item.photo_states[p.id]]}`));
    const image = element("img");
    image.alt = `${item.name}の写真 ${number}`;
    const picture = action("写真を拡大", () => {
      zoom.querySelector("img").src = image.src;
      zoom.querySelector("img").alt = image.alt;
      zoom.showModal();
    }, "guide-thumbnail");
    const failure = element("span", "画像の取得中");
    picture.append(image, failure);
    picture.disabled = true;
    image.hidden = true;
    card.append(picture, element("p", `撮影日 ${p.capture || "不明"} · ${p.classification}`),
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
    excerpt.append(element("small", p.id));
    card.append(details("記事の該当箇所と写真ID", excerpt));
    const one = action("この写真の掲載名を確認", () => save(item, "name", "confirmed", "photo", [p.id]));
    const individual = element("div", undefined, "guide-individual");
    one.disabled = true;
    individual.append(one, action("この写真を保留", () => save(item, "name", "held", "photo", [p.id])),
      action("この写真の確認を訂正", () => save(item, "name", "reset", "photo", [p.id])));
    card.append(individual);
    const photographs = find("#guide-photos");
    photographs.append(card);
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
      loaded.set(p.id, ticket);
      readiness();
    } catch {
      if (stamp === view) {
        failure.textContent = "画像を読み込めません。再取得してください。";
        readiness();
      }
    }
  }

  function render(item, stamp) {
    if (zoom.open) zoom.close();
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
    itemRegion.append(nav, title, line, element("p", item.question), element("p", item.reason, "meta"));
    itemRegion.append(control("確認者", "guide-reviewer", reviewer, v => { reviewer = v; }),
      control("確認メモ", "guide-note", notes.get(item.id) || "", v => notes.set(item.id, v), true));
    if (item.legacy_ids.length) {
      itemRegion.append(element("p", "過去の写真接続承認は #163 の指定3枚です。最新画像の目視確認を記録できます。原稿・食毒・特徴・公開は個別に審査します。"),
        link("https://github.com/charchan123/hatena-photo-gallery/pull/163", "旧承認 #163 を開く"));
    }
    const photos = element("div", undefined, "guide-photos");
    photos.id = "guide-photos";
    itemRegion.append(photos, manuscript(item));
    const history = element("ol");
    for (const event of [...item.history].reverse()) {
      const entry = element("li", `改訂 ${event.revision} · ${new Date(event.at).toLocaleString("ja-JP")} · ${event.reviewer} · ${kindLabels[event.kind]}／${labelStatus[event.decision]} · ${event.photos.length}枚${event.local ? "" : " · バックアップから復元"}`);
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
    itemRegion.append(details("確認履歴", history));
    const dock = element("div", undefined, "guide-dock");
    const check = element("p");
    check.setAttribute("role", "status");
    const all = action(`全${ids.length}枚の名称を確認して次へ`, () => save(item, "name", "confirmed", "all", ids, pending || next), "primary");
    const legacy = action("旧承認の指定3枚を再確認して保存", () => save(item, "name", "confirmed", "legacy", item.legacy_ids, pending || next));
    legacy.hidden = !item.legacy_ids.length;
    const individual = action("写真ごとに確認", () => {
      photos.classList.toggle("guide-show-individual");
      photos.scrollIntoView({block: "start"});
    });
    const hold = action("保留して次へ", () => save(item, "name", "held", "all", ids, pending || next));
    dock.append(check, all, individual, hold, legacy, action("メモを保存", () => save(item, "name", "note", "all", ids)),
      action("名称確認を訂正・再確認", () => {
        if (window.confirm(`${item.name}の名称確認を再開しますか？ 過去の記録は履歴に残ります。`))
          return save(item, "name", "reset", "all", ids);
      }));
    itemRegion.append(dock);
    function readiness() {
      check.textContent = `表示できた写真 ${loaded.size}／${ids.length}枚。写真を見てから、確認ボタンで記録してください。`;
      all.disabled = !ids.length || loaded.size !== ids.length || !["A", "B"].includes(item.group);
      legacy.disabled = item.legacy_ids.length !== 3 || !item.legacy_ids.every(key => loaded.has(key));
    }
    readiness();
    Promise.all(item.photos.map((row, i) => photoCard(row, item, i + 1, stamp, readiness))).then(async () => {
      if (stamp !== view || !ids.length) return;
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
        });
      } catch (error) { if (stamp === view) report(error.message, true); }
    });
  }

  selection.addEventListener("change", () => open(selection.value));
  for (const id of ["#guide-search", "#guide-priority", "#guide-size", "#guide-status"]) {
    find(id).addEventListener(id === "#guide-search" ? "input" : "change", () => {
      if (!data) return;
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
  window.guideReview = {open: () => open(selected)};
})();
