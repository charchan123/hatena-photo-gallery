/* Comment UI is opt-in; no comment API or Turnstile request before opening. */
(() => {
  "use strict";
  const $ = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  };
  const KEY = "kinoko-research-comments-v1",
    fun = [
      "通りすがりの鑑定士",
      "森の観察者",
      "きのこマスター",
      "木陰の探検家",
    ];
  let saved;
  try {
    saved = JSON.parse(localStorage.getItem(KEY) || "null");
  } catch {}
  if (!saved || typeof saved !== "object" || Array.isArray(saved)) saved = {};
  if (typeof saved.nickname !== "string")
    saved.nickname =
      fun[crypto.getRandomValues(new Uint32Array(1))[0] % fun.length];
  saved.owners =
    saved.owners && typeof saved.owners === "object" ? saved.owners : {};
  saved.pending =
    saved.pending && typeof saved.pending === "object" ? saved.pending : {};
  const persist = () => {
    localStorage.setItem(KEY, JSON.stringify(saved));
  };
  try {
    persist();
  } catch {}
  const errorText = {
    COMMENTS_DISABLED: "コメントは準備中です。",
    POSTING_DISABLED: "現在、新規投稿を停止しています。",
    HUMAN_CHECK_REQUIRED: "人間確認を完了してください。",
    HUMAN_CHECK_FAILED:
      "人間確認の期限が切れた可能性があります。もう一度確認してください。",
    RESERVED_NICKNAME: "管理人・公式・運営と誤認される名前は使用できません。",
    RATE_LIMITED: "少し時間をおいてからお試しください。",
    CASE_REVIEW_REQUIRED:
      "ケースの紐付けを管理人が確認しています。過去のコメントは保管されています。",
    DELETE_NOT_AUTHORIZED:
      "削除キーを確認できません。削除済みの場合、本文は公開されません。",
    INVALID_TEXT: "名前は30文字以内、本文は1〜500文字で入力してください。",
  };
  let configPromise = fetch("research-comments-config.json", {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  })
    .then((r) => {
      if (!r.ok) throw Error("config");
      return r.json();
    })
    .catch(() => ({ enabled: false }));
  let turnstilePromise;
  function turnstile() {
    if (window.turnstile) return Promise.resolve(window.turnstile);
    if (!turnstilePromise)
      turnstilePromise = new Promise((resolve, reject) => {
        const script = $("script");
        script.src =
          "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
        script.async = true;
        script.onload = () =>
          window.turnstile
            ? resolve(window.turnstile)
            : reject(Error("人間確認を読み込めません"));
        script.onerror = () => reject(Error("人間確認を読み込めません"));
        document.head.append(script);
        setTimeout(
          () => reject(Error("人間確認の読み込みがタイムアウトしました")),
          8000,
        );
      });
    turnstilePromise.catch(() => {
      turnstilePromise = null;
    });
    return turnstilePromise;
  }
  function token() {
    const b = crypto.getRandomValues(new Uint8Array(32));
    return [...b].map((n) => n.toString(16).padStart(2, "0")).join("");
  }
  for (const details of document.querySelectorAll("[data-research-thread]")) {
    let loaded = false;
    details.addEventListener("toggle", async () => {
      if (!details.open || loaded) return;
      loaded = true;
      const area = details.querySelector(".research-comments-content"),
        status = $("p", "コメントを読み込んでいます…", "comments-status");
      status.setAttribute("role", "status");
      area.replaceChildren(status);
      const config = await configPromise;
      if (
        config.enabled !== true ||
        !config.release_approval ||
        !/^https:\/\/[^/]+\/?$/.test(config.api_url || "")
      ) {
        status.textContent =
          "コメント機能は準備中です。公開開始までお待ちください。";
        return;
      }
      const thread = details.dataset.researchThread,
        base = config.api_url.replace(/\/$/, ""),
        path = "/v1/cases/" + encodeURIComponent(thread) + "/comments";
      let busy = false,
        cursor = null,
        seen = new Set();
      async function api(route, body) {
        let r;
        try {
          r = await fetch(base + route, {
            method: body ? "POST" : "GET",
            headers: body ? { "Content-Type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
            signal: AbortSignal.timeout(10000),
            credentials: "omit",
            referrerPolicy: "no-referrer",
          });
        } catch {
          throw Error(
            "通信できませんでした。入力内容と削除キーを保持しています。時間をおいて再試行してください。",
          );
        }
        let v;
        try {
          v = await r.json();
        } catch {
          throw Error("応答を確認できませんでした。再試行してください。");
        }
        if (!r.ok) {
          const e = Error(
            errorText[v.error] ||
              "現在コメントを利用できません。時間をおいて再試行してください。",
          );
          e.code = v.error;
          throw e;
        }
        return v;
      }
      const list = $("div", undefined, "comments-list"),
        more = $("button", "続きのコメントを読む"),
        reload = $("button", "最初から読み直す");
      more.type = reload.type = "button";
      more.hidden = true;
      area.append(list, more, reload);
      function display(c) {
        if (seen.has(c.id)) return;
        seen.add(c.id);
        const box = $(
          "article",
          undefined,
          "comment" + (c.official ? " comment-official" : ""),
        );
        box.dataset.commentId = c.id;
        box.dataset.seq = String(c.seq);
        const head = $("p", undefined, "comment-meta");
        head.append(
          $("strong", c.state === "deleted" ? "削除済み" : c.nickname),
        );
        if (c.official)
          head.append($("span", "管理人・公式", "comment-official-badge"));
        const time = $(
          "time",
          new Date(c.created_at).toLocaleString("ja-JP", {
            timeZone: "Asia/Tokyo",
          }),
        );
        time.dateTime = new Date(c.created_at).toISOString();
        head.append(time);
        box.append(head);
        if (c.parent_id)
          box.append(
            $(
              "p",
              "コメント " + c.parent_id.slice(0, 8) + " への管理人返信",
              "comment-reply-to",
            ),
          );
        box.append(
          $(
            "p",
            c.state === "deleted" ? "投稿者によって削除されました。" : c.body,
            "comment-body",
          ),
        );
        if (c.state !== "deleted") {
          if (saved.owners[c.id]) {
            const del = $("button", "自分のコメントを削除");
            del.type = "button";
            del.onclick = async () => {
              if (
                !confirm(
                  "このコメントを削除しますか？本文と名前は公開されなくなります。",
                )
              )
                return;
              del.disabled = true;
              try {
                await api(path + "/" + c.id + "/delete", {
                  delete_token: saved.owners[c.id],
                });
                delete saved.owners[c.id];
                try {
                  persist();
                } catch {}
                await firstPage();
              } catch (e) {
                status.textContent = e.message;
                del.disabled = false;
              }
            };
            box.append(del);
          }
          const report = $("button", "通報");
          report.type = "button";
          report.onclick = () => openReport(c.id, box);
          box.append(report);
        }
        const next = [...list.children].find(
          (e) => Number(e.dataset.seq) > c.seq,
        );
        list.insertBefore(box, next || null);
      }
      async function loadPage(reset = false) {
        if (busy) return;
        busy = true;
        more.disabled = reload.disabled = true;
        try {
          const v = await api(path + (reset ? "" : "?after=" + (cursor || 0)));
          if (reset) {
            list.replaceChildren();
            seen.clear();
          }
          for (const c of v.comments) display(c);
          cursor = v.next_cursor;
          more.hidden = cursor === null;
          status.textContent = seen.size
            ? "同定の参考情報としてお読みください。"
            : "まだコメントはありません。最初の発見をどうぞ。";
        } catch (e) {
          status.textContent = e.message;
        } finally {
          busy = false;
          more.disabled = reload.disabled = false;
        }
      }
      const firstPage = () => loadPage(true);
      more.onclick = () => loadPage(false);
      reload.onclick = firstPage;
      async function challenge(container) {
        const t = await turnstile();
        return new Promise((resolve, reject) => {
          let id;
          id = t.render(container, {
            sitekey: config.turnstile_site_key,
            action: "research_comment",
            callback: (value) => resolve({ value, remove: () => t.remove(id) }),
            "error-callback": () =>
              reject(Error("人間確認に失敗しました。再度お試しください。")),
            "expired-callback": () =>
              reject(Error("人間確認の期限が切れました。")),
          });
        });
      }
      function openReport(id, box) {
        if (box.querySelector(".comment-report-form")) return;
        const form = $("form", undefined, "comment-report-form"),
          label = $("label", "通報理由（200文字以内）"),
          input = $("textarea"),
          submit = $("button", "通報を送信"),
          cancel = $("button", "閉じる"),
          notice = $("p");
        input.maxLength = 400;
        input.required = true;
        label.append(input);
        submit.type = "submit";
        cancel.type = "button";
        cancel.onclick = () => form.remove();
        form.append(label, notice, submit, cancel);
        box.append(form);
        form.onsubmit = async (ev) => {
          ev.preventDefault();
          if (!input.value.trim() || [...input.value.trim()].length > 200) {
            notice.textContent = "通報理由は1〜200文字です。";
            return;
          }
          submit.disabled = true;
          const mount = $("div");
          form.append(mount);
          let solved;
          try {
            solved = await challenge(mount);
            await api(path + "/" + id + "/reports", {
              request_id: crypto.randomUUID(),
              reason: input.value,
              turnstile_token: solved.value,
            });
            form.replaceChildren(
              $("p", "通報を受け付けました。管理人が確認します。"),
            );
          } catch (e) {
            notice.textContent = e.message;
            submit.disabled = false;
          } finally {
            solved?.remove();
            mount.remove();
          }
        };
      }
      await firstPage();
      if (details.dataset.archived === "true") {
        area.append(
          $("p", "履歴保管中のため、この欄からの新規投稿は停止しています。"),
        );
        return;
      }
      const form = $("form", undefined, "comment-form"),
        nameLabel = $("label", "ニックネーム（30文字以内）"),
        name = $("input"),
        bodyLabel = $("label", "同定のヒント・感想（500文字以内）"),
        body = $("textarea"),
        count = $("span", "0 / 500"),
        submit = $("button", "コメントを投稿"),
        note = $(
          "p",
          "個人情報は書き込まないでください。削除キーはこのブラウザに保存されます。別の端末や保存データを消した後には、自分の投稿を削除できません。",
        ),
        notice = $("p");
      notice.setAttribute("role", "status");
      name.value = saved.nickname;
      name.maxLength = 60;
      name.required = true;
      body.maxLength = 1000;
      body.required = true;
      body.rows = 4;
      nameLabel.append(name);
      bodyLabel.append(body, count);
      submit.type = "submit";
      form.append(nameLabel, bodyLabel, note, notice, submit);
      area.append(form);
      let pending = saved.pending[thread];
      if (pending) {
        name.value = pending.nickname;
        body.value = pending.body;
        name.readOnly = body.readOnly = true;
        submit.textContent = "前回の送信結果を再確認";
        notice.textContent =
          "送信結果が不明の投稿があります。同じ内容を再確認して重複登録を防ぎます。";
      }
      const counter = () =>
        (count.textContent = [...body.value].length + " / 500");
      body.oninput = counter;
      counter();
      name.onchange = () => {
        saved.nickname = name.value;
        try {
          persist();
        } catch {
          notice.textContent =
            "ブラウザへの保存ができません。設定をご確認ください。";
        }
      };
      form.onsubmit = async (ev) => {
        ev.preventDefault();
        if (submit.disabled) return;
        if (
          !body.value.trim() ||
          [...body.value.trim()].length > 500 ||
          !name.value.trim() ||
          [...name.value.trim()].length > 30
        ) {
          notice.textContent = errorText.INVALID_TEXT;
          return;
        }
        submit.disabled = true;
        const mount = $("div");
        form.append(mount);
        let solved;
        try {
          pending = pending || {
            request_id: crypto.randomUUID(),
            nickname: name.value,
            body: body.value,
            delete_token: token(),
          };
          saved.pending[thread] = pending;
          saved.nickname = name.value;
          try {
            persist();
          } catch {
            throw Error(
              "削除キーをブラウザに保存できないため投稿を停止しました。ブラウザの保存設定を確認してください。",
            );
          }
          solved = await challenge(mount);
          const v = await api(path, {
            ...pending,
            turnstile_token: solved.value,
          });
          if (v.comment.state !== "deleted")
            saved.owners[v.comment.id] = pending.delete_token;
          delete saved.pending[thread];
          pending = null;
          persist();
          body.value = "";
          name.readOnly = body.readOnly = false;
          submit.textContent = "コメントを投稿";
          counter();
          notice.textContent = "投稿しました。ありがとうございます！";
          await firstPage();
          display(v.comment);
        } catch (e) {
          notice.textContent = e.message;
          if (
            [
              "INVALID_TEXT",
              "RESERVED_NICKNAME",
              "INVALID_FIELDS",
              "INVALID_DELETE_TOKEN",
              "HUMAN_CHECK_FAILED",
              "HUMAN_CHECK_REQUIRED",
            ].includes(e.code)
          ) {
            delete saved.pending[thread];
            pending = null;
            try {
              persist();
            } catch {}
          }
          name.readOnly = body.readOnly = !!pending;
          if (pending) submit.textContent = "前回の送信結果を再確認";
        } finally {
          solved?.remove();
          mount.remove();
          submit.disabled = false;
        }
      };
    });
  }
})();
