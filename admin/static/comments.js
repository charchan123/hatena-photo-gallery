/* Secrets stay in Python process environment. Existing draft state is untouched. */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s),
    el = (tag, text) => {
      const n = document.createElement(tag);
      if (text !== undefined) n.textContent = text;
      return n;
    };
  let configured = false,
    selected = null,
    cursor = null,
    busy = false,
    searchTimer, caseSequence = 0, threadSequence = 0, trial = false;
  let allCases = [];
  const replyDrafts = new Map(), unresolved = new Map();
  function safeUrl(value, hosts) {
    try {
      const url = new URL(value);
      if (url.protocol === "https:" && hosts.includes(url.hostname) &&
          !url.username && !url.password && !url.port) return url.href;
    } catch {}
    return null;
  }
  const photoHosts = ["cdn-ak.f.st-hatena.com", "cdn.image.st-hatena.com"];
  const articleHosts = ["exsudoporus-ruber.hatenablog.jp"];
  const phaseLabel = {identified: "判明済み", archived: "過去のコメントを保管中"};
  function photoEntries(row) {
    return (row.media?.photos || []).map((photo, index) => ({
      src: safeUrl(photo.src, photoHosts), alt: `${row.label}の写真 ${index + 1}`,
      caption: photo.date ? `撮影日 ${photo.date}` : "撮影日不明",
      article: safeUrl(photo.article_url, articleHosts), articleTitle: photo.article_title,
    })).filter(photo => photo.src);
  }
  function showPhotos(row) {
    const region = $("#comments-photos");
    region.replaceChildren();
    if (phaseLabel[row.media?.phase]) region.append(el("p", phaseLabel[row.media.phase]));
    const photos = photoEntries(row);
    if (!photos.length) {
      region.append(el("p", "写真との紐付けを確認中です。"));
      return;
    }
    const strip = el("div");
    strip.className = "comments-photo-strip";
    for (const [index, photo] of photos.entries()) {
      const figure = el("figure");
      const image = el("img");
      image.src = photo.src;
      image.alt = photo.alt;
      const zoom = button("", () => window.adminPhotoViewer.open(photos, photo, zoom));
      zoom.setAttribute("aria-label", `写真 ${index + 1} を拡大`);
      zoom.append(image);
      image.onerror = () => {
        zoom.disabled = true;
        zoom.replaceChildren(el("span", "画像を取得できません"));
      };
      figure.append(zoom, el("figcaption", photo.caption));
      if (photo.article) {
        const article = el("a", photo.articleTitle || "元記事");
        article.href = photo.article;
        article.target = "_blank";
        article.rel = "noopener noreferrer";
        figure.append(article);
      }
      strip.append(figure);
    }
    region.append(el("p", `写真 ${photos.length}枚`), strip);
  }
  function choose(row) {
    selected = row.id;
    $("#comments-case-title").textContent = row.label;
    showPhotos(row);
    renderCases();
    loadComments(true);
  }
  function renderCases() {
    const filter = $("#comments-case-filter").value;
    const q = $("#comments-search").value.trim().normalize("NFKC").toLocaleLowerCase("ja");
    const out = $("#comments-cases");
    out.replaceChildren();
    const matches = allCases.filter(row => row.label.normalize("NFKC").toLocaleLowerCase("ja").includes(q) || row.id.includes(q));
    const visible = matches.filter(row => filter === "all" || row[filter] > 0);
    for (const row of visible) {
      const box = el("article");
      box.className = "panel comments-case";
      const photo = photoEntries(row)[0];
      if (photo) {
        const image = el("img");
        image.loading = "lazy";
        image.src = photo.src;
        image.alt = photo.alt;
        image.onerror = () => image.remove();
        box.append(image);
      }
      const body = el("div");
      const open = button("コメントを見る", () => choose(row));
      if (row.id === selected) open.setAttribute("aria-current", "true");
      body.append(el("h4", row.label),
        el("p", `全${row.total}件・未確認${row.unread}件${row.reports ? `・通報${row.reports}件` : ""}`),
        el("p", photo ? `${photo.caption} · 写真${row.media.photo_count}枚` : "写真との紐付けを確認中"), el("small", row.id), open);
      box.append(body);
      out.append(box);
    }
    if (!visible.length) out.append(el("p", q ? "検索条件に一致するケースがありません。" :
      filter === "unread" ? "未確認のコメントはありません。" :
      filter === "reports" ? "通報が付いたケースはありません。" :
      "コメントが付いた研究ケースはまだありません。"));
  }
  const feedback = (text, error = false) => {
    const n = $("#comments-feedback");
    n.textContent = text;
    n.className = error ? "error" : "";
  };
  async function call(action, values = {}) {
    const s = await (await fetch("/api/state")).json();
    const r = await fetch("/api/comments/request", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": s.csrf },
      body: JSON.stringify({ action, values }),
      signal: AbortSignal.timeout(15000),
    });
    const v = await r.json();
    if (!r.ok) throw Error(v.message || "コメント操作に失敗しました");
    return v;
  }
  function button(text, fn) {
    const b = el("button", text);
    b.type = "button";
    b.onclick = fn;
    return b;
  }
  async function cases() {
    if (!configured) return;
    const sequence = ++caseSequence;
    try {
      const query = trial && $("#comments-search").value === "接続失敗" ? {q: "接続失敗"} : {q: ""};
      const result = await call("cases", query);
      if (sequence !== caseSequence) return;
      allCases = result.cases;
      const totals = allCases.reduce((sum, row) => [sum[0] + row.unread,
        sum[1] + Number(row.total > 0), sum[2] + row.reports], [0, 0, 0]);
      $("#comments-summary").textContent =
        `未確認${totals[0]}件 · コメントあり${totals[1]}／${allCases.length}ケース · 通報${totals[2]}件`;
      renderCases();
      feedback("");
    } catch (e) {
      if (sequence === caseSequence) feedback("コメント管理APIに接続できません。 " + e.message, true);
    }
  }
  async function start() {
    try {
      const r = await fetch("/api/comments/status"),
        v = await r.json();
      if (!r.ok) throw Error();
      configured = v.configured;
      trial = v.trial === true;
      $("#comments-connection").textContent = v.message;
      $("#comments-backup").disabled = $("#comments-refresh").disabled =
        !configured;
      $("#comments-backup").disabled ||= trial;
      if (configured) await cases();
      else feedback("コメント管理APIが未設定です。");
    } catch {
      feedback("コメント管理の設定状態を取得できません。", true);
    }
  }
  async function loadComments(reset = false) {
    if (!selected || (busy && !reset)) return;
    const current = selected, sequence = ++threadSequence;
    const out = $("#comments-list");
    if (reset) {
      const old = out.dataset.selected;
      if (old && old !== current) {
        out.replaceChildren(el("p", "コメントを読み込んでいます…"));
        $("#comments-more").hidden = true;
      }
      out.dataset.selected = current;
    }
    busy = true;
    try {
      const v = await call("comments", {
          case_id: current,
          after: reset ? 0 : cursor || 0,
          unread: $("#comments-unread").checked ? 1 : 0,
        });
      if (sequence !== threadSequence) return;
      if (reset) out.replaceChildren();
      if (reset && !v.comments.length) out.append(el("p", allCases.find(row => row.id === current)?.total !== 0 && $("#comments-unread").checked
        ? "未確認のコメントはありません。" : "コメントがまだありません。"));
      for (const c of v.comments) {
        const box = el("article");
        box.className = "panel";
        box.dataset.commentId = c.id;
        box.dataset.state = c.state;
        box.append(
          el(
            "h4",
            (c.official ? "管理人・公式：" : "") +
              (c.nickname || "投稿者による削除済み"),
          ),
          el(
            "p",
            new Date(c.created_at).toLocaleString("ja-JP") +
              " / " +
              {
                visible: "公開中",
                hidden: "非表示",
                deleted: "投稿者による削除",
              }[c.state] +
              (c.reviewed ? " / 確認済み" : " / 未確認"),
          ),
          el("p", c.body || "本文は削除済みです。"),
        );
        const notice = el("p");
        notice.setAttribute("role", "status");
        box.append(notice);
        let pending = unresolved.get(c.id);
        async function action(kind, body) {
          if (pending && (kind !== pending.action || body !== pending.body)) {
            notice.textContent = "前回の操作の結果を先に確認してください。";
            return;
          }
          const payload = pending || {
            request_id: crypto.randomUUID(),
            action: kind,
            comment_id: c.id,
            ...(body !== undefined ? { body } : {}),
          };
          pending = payload;
          unresolved.set(c.id, payload);
          const controls = [...box.querySelectorAll("button,input,textarea")];
          controls.forEach((b) => (b.disabled = true));
          try {
            await call("action", payload);
            pending = null;
            unresolved.delete(c.id);
            if (kind === "reply") replyDrafts.delete(c.id);
            if (selected === current) await loadAfter();
          } catch (e) {
            notice.textContent =
              e.message + " 同じ操作で再試行すると重複を防げます。";
            notice.className = "error";
            if (!box.querySelector(".comments-retry")) {
              const retry = button("前回の操作を再確認", () =>
                action(pending.action, pending.body),
              );
              retry.className = "comments-retry";
              box.append(retry);
            }
          } finally {
            controls.forEach((b) => (b.disabled = false));
          }
        }
        async function loadAfter() {
          busy = false;
          await loadComments(true);
          await cases();
        }
        box.append(
          button("履歴・通報を見る", async () => {
            try {
              const h = await call("history", { comment_id: c.id });
              let history = box.querySelector(".comments-history");
              if (!history) {
                history = el("section");
                history.className = "comments-history";
                box.append(history);
              }
              history.replaceChildren(el("h4", "操作履歴"));
              const names = {
                hide: "非表示",
                restore: "公開へ復元",
                review: "確認済み",
                reply: "公式返信",
                author_delete: "投稿者による削除",
              };
              for (const row of h.audit)
                history.append(
                  el(
                    "p",
                    new Date(row.created_at).toLocaleString("ja-JP", {
                      timeZone: "Asia/Tokyo",
                    }) +
                      " / " +
                      (names[row.action] || "管理操作"),
                  ),
                );
              if (!h.audit.length)
                history.append(el("p", "操作履歴はありません。"));
              history.append(el("h4", "通報内容"));
              for (const row of h.reports)
                history.append(
                  el(
                    "p",
                    new Date(row.created_at).toLocaleString("ja-JP", {
                      timeZone: "Asia/Tokyo",
                    }) +
                      " / " +
                      (row.reason || "投稿者削除のため理由を消去済み"),
                  ),
                );
              if (!h.reports.length)
                history.append(el("p", "通報はありません。"));
            } catch (e) {
              notice.textContent = e.message;
            }
          }),
        );
        if (c.state !== "deleted" && !trial) {
          box.append(
            button("確認済みにする", () => action("review")),
            button(c.state === "hidden" ? "公開へ復元" : "非表示にする", () => {
              if (
                confirm(
                  c.state === "hidden"
                    ? "このコメントを公開へ復元しますか？"
                    : "このコメントを非表示にしますか？",
                )
              )
                action(c.state === "hidden" ? "restore" : "hide");
            }),
          );
          if (!c.parent_id && c.state === "visible") {
            const label = el("label", "管理人として返信（500文字以内）"),
              reply = el("textarea");
            reply.maxLength = 1000;
            reply.value = replyDrafts.get(c.id) || "";
            reply.oninput = () => replyDrafts.set(c.id, reply.value);
            label.append(reply);
            box.append(
              label,
              button("公式返信を送信", () => {
                if (!reply.value.trim() || [...reply.value].length > 500) {
                  notice.textContent = "返信は1〜500文字です。";
                  return;
                }
                if (confirm("管理人・公式として返信を送信しますか？"))
                  action("reply", reply.value);
              }),
            );
          }
        }
        if (pending) {
          notice.textContent = "前回の操作結果を確認できます。";
          box.append(button("前回の操作を再確認", () => pending && action(pending.action, pending.body)));
        }
        out.append(box);
      }
      cursor = v.next_cursor;
      $("#comments-more").hidden = cursor === null;
    } catch (e) {
      if (sequence === threadSequence) feedback(e.message, true);
    } finally {
      if (sequence === threadSequence) busy = false;
    }
  }
  $("[data-page=comments]").addEventListener("click", start);
  $("#comments-refresh").onclick = cases;
  $("#comments-search").oninput = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => trial ? cases() : renderCases(), 250);
  };
  $("#comments-case-filter").onchange = renderCases;
  $("#comments-more").onclick = () => loadComments(false);
  $("#comments-unread").onchange = () => loadComments(true);
  $("#comments-backup").onclick = async () => {
    const b = $("#comments-backup");
    b.disabled = true;
    try {
      const v = await call("backup"),
        blob = new Blob([JSON.stringify(v, null, 2)], {
          type: "application/json",
        }),
        url = URL.createObjectURL(blob),
        a = el("a", "検証済みバックアップJSONを保存");
      a.href = url;
      a.download =
        "kinoko-comments-" +
        new Date(v.created_at).toISOString().replace(/[:.]/g, "-") +
        ".json";
      feedback("整合性・署名検証が成功しました。SHA-256: " + v.sha256);
      $("#comments-feedback").append(a);
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      feedback("バックアップは未完了です。" + e.message, true);
    } finally {
      b.disabled = !configured || trial;
    }
  };
})();
