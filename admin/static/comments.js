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
    searchTimer;
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
    try {
      const v = await call("cases", { q: $("#comments-search").value }),
        out = $("#comments-cases");
      out.replaceChildren();
      for (const c of v.cases) {
        const box = el("article");
        box.className = "panel";
        box.append(
          el("h4", c.label),
          el("p", `全${c.total}件・未確認${c.unread}件・通報${c.reports}件`),
          el("small", c.id),
          button("コメントを見る", () => {
            selected = c.id;
            $("#comments-case-title").textContent = c.label;
            loadComments(true);
          }),
        );
        out.append(box);
      }
      feedback(`${v.cases.length}ケース`);
    } catch (e) {
      feedback(e.message, true);
    }
  }
  async function start() {
    try {
      const r = await fetch("/api/comments/status"),
        v = await r.json();
      configured = v.configured;
      $("#comments-connection").textContent = v.message;
      $("#comments-backup").disabled = $("#comments-refresh").disabled =
        !configured;
      if (configured) await cases();
    } catch {
      feedback("コメント管理の設定状態を取得できません。", true);
    }
  }
  async function loadComments(reset = false) {
    if (!selected || busy) return;
    busy = true;
    try {
      const v = await call("comments", {
          case_id: selected,
          after: reset ? 0 : cursor || 0,
          unread: $("#comments-unread").checked ? 1 : 0,
        }),
        out = $("#comments-list");
      if (reset) out.replaceChildren();
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
        let pending;
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
          const controls = [...box.querySelectorAll("button,input,textarea")];
          controls.forEach((b) => (b.disabled = true));
          try {
            await call("action", payload);
            pending = null;
            await loadAfter();
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
        if (c.state !== "deleted") {
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
        out.append(box);
      }
      cursor = v.next_cursor;
      $("#comments-more").hidden = cursor === null;
    } catch (e) {
      feedback(e.message, true);
    } finally {
      busy = false;
    }
  }
  $("[data-page=comments]").addEventListener("click", start);
  $("#comments-refresh").onclick = cases;
  $("#comments-search").oninput = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(cases, 300);
  };
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
      b.disabled = !configured;
    }
  };
})();
