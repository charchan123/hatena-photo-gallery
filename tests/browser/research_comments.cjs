"use strict";
const { chromium } = require(
    process.env.PLAYWRIGHT_MODULE_PATH || "playwright",
  ),
  assert = require("node:assert/strict"),
  { spawn, execFileSync } = require("node:child_process"),
  fs = require("node:fs"),
  path = require("node:path");
const root = path.resolve(__dirname, "../.."),
  out = path.resolve(
    process.argv[2] ||
      process.env.COMMENTS_EVIDENCE ||
      "/tmp/research-comments-evidence",
  ),
  python = process.env.PYTHON_BIN || "python";
fs.mkdirSync(out, { recursive: true });
let children = [],
  browser;
let assertions = 0;
const check = (v, label) => {
  assert.ok(v, label);
  assertions++;
};
async function start(command, args) {
  const child = spawn(command, args, {
    cwd: root,
    stdio: ["ignore", "pipe", "inherit"],
  });
  children.push(child);
  return new Promise((resolve, reject) => {
    let text = "";
    const timer = setTimeout(() => reject(Error("server timeout")), 15000);
    child.on("exit", (c) => reject(Error("server exit " + c)));
    child.stdout.on("data", (data) => {
      text += data;
      try {
        const v = JSON.parse(text.split("\n")[0]);
        clearTimeout(timer);
        resolve(v.port);
      } catch {}
    });
  });
}
async function stop() {
  for (const c of children) {
    c.kill();
  }
  children = [];
}
(async () => {
  execFileSync(python, ["tests/browser/comments_fixture.py", out], {
    cwd: root,
  });
  const port = await start(process.execPath, [
      "tests/browser/comments_api_server.mjs",
    ]),
    admin = await start(python, [
      "tests/browser/comments_admin_server.py",
      out,
      String(port),
    ]),
    api = "http://127.0.0.1:" + port;
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const context = await browser.newContext({
      viewport: { width: 1280, height: 1000 },
    }),
    page = await context.newPage();
  let enabled = false;
  await context.route("**/*", async (route) => {
    const r = route.request(),
      u = new URL(r.url());
    if (u.hostname === "comments.fixture.test") {
      const response = await route.fetch({ url: api + u.pathname + u.search });
      return route.fulfill({ response });
    }
    if (u.hostname === "127.0.0.1") return route.continue();
    if (u.pathname.endsWith("/research-comments-config.json"))
      return route.fulfill({
        json: {
          version: 1,
          enabled,
          api_url: "https://comments.fixture.test",
          turnstile_site_key: "isolated-site-key",
          release_approval: enabled ? "ISOLATED TEST ONLY" : null,
        },
      });
    if (u.pathname.endsWith("/research.html"))
      return route.fulfill({
        body: fs.readFileSync(path.join(out, "research.html")),
        contentType: "text/html",
      });
    const marker = "/hatena-photo-gallery/",
      relative = u.pathname.includes(marker) ? u.pathname.split(marker)[1] : "";
    if (
      relative &&
      fs.existsSync(path.join(root, relative)) &&
      fs.statSync(path.join(root, relative)).isFile()
    )
      return route.fulfill({
        body: fs.readFileSync(path.join(root, relative)),
        contentType: relative.endsWith(".css")
          ? "text/css"
          : relative.endsWith(".js")
            ? "text/javascript"
            : "application/json",
      });
    if (r.resourceType() === "image")
      return route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="300" height="200" fill="#c4d3b1"/><text x="20" y="100">ISOLATED PHOTO</text></svg>',
      });
    return route.abort();
  });
  const stats = async () =>
    await (await context.request.get(api + "/__test/stats")).json();
  const info = await stats();
  await page.addInitScript(() => {
    if (!localStorage.getItem("kinoko-research-comments-v1"))
      localStorage.setItem(
        "kinoko-research-comments-v1",
        JSON.stringify({
          nickname: "既存の森の観察者",
          owners: {},
          pending: {},
        }),
      );
    window.turnstile = {
      render: (box, opts) => {
        queueMicrotask(() => opts.callback("synthetic-token"));
        return 1;
      },
      remove: () => {},
    };
  });
  const url =
    "https://charchan123.github.io/hatena-photo-gallery/research.html";
  await page.goto(url);
  check(
    (await page.locator("[data-research-thread]").count()) === 66,
    "66 stable case mounts",
  );
  check((await stats()).publicCalls === 0, "no eager API for 66 cases");
  const thread = page.locator('[data-research-thread="' + info.caseId + '"]');
  await thread.locator("summary").click();
  await page.waitForFunction(() =>
    document
      .querySelector(".research-comments[open]")
      .textContent.includes("公開開始まで"),
  );
  check(
    (await stats()).publicCalls === 0,
    "disabled UI never contacts comment API",
  );
  enabled = true;
  await page.reload();
  await thread.locator("summary").click();
  await thread.locator(".comment").first().waitFor();
  check((await thread.locator(".comment").count()) === 20, "page size 20");
  check((await stats()).publicCalls === 1, "only opened case fetched");
  check(
    (await thread.locator(".comment-body img").count()) === 0,
    "XSS text remains text",
  );
  check(
    (await thread.locator(".comment-form input").inputValue()) ===
      "既存の森の観察者",
    "nickname not overwritten",
  );
  await thread
    .locator(".comment-form textarea")
    .fill("写真の特徴についての合成コメントです");
  await thread
    .getByRole("button", { name: "コメントを投稿", exact: true })
    .click();
  await thread
    .getByText("投稿しました。ありがとうございます！", { exact: true })
    .waitFor();
  check(
    (await thread
      .locator(".comment-body")
      .filter({ hasText: "写真の特徴についての合成コメントです" })
      .count()) === 1,
    "new post immediately shown",
  );
  check(
    (await thread
      .getByRole("button", { name: "自分のコメントを削除" })
      .count()) === 1,
    "owner key retained",
  );
  await thread
    .getByRole("button", { name: "続きのコメントを読む", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      document.querySelectorAll(".research-comments[open] .comment").length ===
      24,
  );
  const seqs = await thread
    .locator(".comment")
    .evaluateAll((xs) => xs.map((x) => Number(x.dataset.seq)));
  check(
    seqs.every((x, i) => !i || x > seqs[i - 1]),
    "pagination and new post preserve oldest order",
  );
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await thread.scrollIntoViewIfNeeded();
    check(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      "no horizontal overflow " + width,
    );
    await page.screenshot({
      path: path.join(out, "visitor-" + width + ".png"),
    });
    await thread.locator(".comment-form").scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(out, "compose-" + width + ".png"),
    });
    await thread.evaluate((e) =>
      scrollTo(
        0,
        e.closest(".research-case").getBoundingClientRect().top + scrollY - 20,
      ),
    );
    await page.screenshot({ path: path.join(out, "case-" + width + ".png") });
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  const a = await context.newPage();
  a.on("dialog", (d) => d.accept());
  await a.goto("http://127.0.0.1:" + admin);
  await a.click("[data-page=comments]");
  await a.waitForSelector("#comments-cases article");
  const caseBox = a
    .locator("#comments-cases article")
    .filter({ hasText: info.caseId });
  await caseBox
    .getByRole("button", { name: "コメントを見る", exact: true })
    .click();
  await a.waitForSelector("#comments-list article");
  let first = a.locator(
    '#comments-list article[data-comment-id="' + info.firstId + '"]',
  );
  await first.locator("textarea").fill("管理人からの公式返信です");
  await first
    .getByRole("button", { name: "公式返信を送信", exact: true })
    .click();
  await a.waitForFunction(
    () => !document.querySelector("#comments-list textarea")?.disabled,
  );
  await page.reload();
  await thread.locator("summary").click();
  await thread.locator(".comment").first().waitFor();
  await thread
    .getByRole("button", { name: "続きのコメントを読む", exact: true })
    .click();
  await thread.getByText("管理人からの公式返信です", { exact: true }).waitFor();
  check(
    (await thread.locator(".comment-official-badge").count()) === 1,
    "official reply server authenticated",
  );
  first = a.locator(
    '#comments-list article[data-comment-id="' + info.firstId + '"]',
  );
  await first
    .getByRole("button", { name: "非表示にする", exact: true })
    .click();
  await a.waitForFunction(
    () =>
      document.querySelector("#comments-list article").dataset.state ===
      "hidden",
  );
  await thread
    .getByRole("button", { name: "最初から読み直す", exact: true })
    .click();
  await page.waitForFunction(
    (id) => !document.querySelector('[data-comment-id="' + id + '"]'),
    info.firstId,
  );
  check(
    (await thread
      .locator('[data-comment-id="' + info.firstId + '"]')
      .count()) === 0,
    "hidden comment absent publicly",
  );
  await first.getByRole("button", { name: "公開へ復元", exact: true }).click();
  await a.waitForFunction(
    () =>
      document.querySelector("#comments-list article").dataset.state ===
      "visible",
  );
  await thread
    .getByRole("button", { name: "最初から読み直す", exact: true })
    .click();
  await thread.locator('[data-comment-id="' + info.firstId + '"]').waitFor();
  check(true, "restored comment visible");
  const row = thread.locator('[data-comment-id="' + info.firstId + '"]');
  await row.getByRole("button", { name: "通報", exact: true }).click();
  await row
    .locator(".comment-report-form textarea")
    .fill("管理人による確認が必要な合成通報です");
  await row.getByRole("button", { name: "通報を送信", exact: true }).click();
  await row
    .getByText("通報を受け付けました。管理人が確認します。", { exact: true })
    .waitFor();
  check(true, "visitor report accepted");
  await first
    .getByRole("button", { name: "履歴・通報を見る", exact: true })
    .click();
  await first
    .locator(".comments-history")
    .filter({ hasText: "合成通報" })
    .waitFor();
  check(true, "admin report and moderation history visible");
  const download = a.waitForEvent("download");
  await a.click("#comments-backup");
  await download;
  await a.waitForFunction(() =>
    document
      .querySelector("#comments-feedback")
      .textContent.includes("署名検証が成功"),
  );
  check(true, "backup signed and downloaded");
  await first.scrollIntoViewIfNeeded();
  await a.screenshot({ path: path.join(out, "admin-comments.png") });
  page.on("dialog", (d) => d.accept());
  await thread
    .getByRole("button", { name: "続きのコメントを読む", exact: true })
    .click();
  await thread
    .getByRole("button", { name: "自分のコメントを削除", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      !document
        .querySelector(".research-comments[open]")
        .textContent.includes("写真の特徴についての合成コメントです"),
  );
  check(true, "author content removed");
  await context.request.post(api + "/__test/fail", { data: { fail: true } });
  await thread
    .getByRole("button", { name: "最初から読み直す", exact: true })
    .click();
  await page.waitForFunction(() =>
    document
      .querySelector(".research-comments[open] .comments-status")
      .textContent.includes("利用できません"),
  );
  check(
    (await page.locator(".research-photo img").count()) > 0,
    "API failure leaves photographs intact",
  );
  await page.screenshot({ path: path.join(out, "api-error.png") });
  fs.writeFileSync(
    path.join(out, "result.json"),
    JSON.stringify(
      {
        assertions,
        local_only: true,
        production_writes: false,
        seed_cases: 66,
      },
      null,
      2,
    ),
  );
  console.log(
    "PASS:",
    assertions,
    "comments real Worker-SQLite-admin-browser assertions",
  );
  await browser.close();
  await stop();
})().catch(async (e) => {
  console.error(e);
  if (browser) await browser.close();
  await stop();
  process.exitCode = 1;
});
