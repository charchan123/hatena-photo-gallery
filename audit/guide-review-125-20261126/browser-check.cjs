const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");

const baseURL = process.env.GUIDE_REVIEW_PREVIEW_URL || "http://127.0.0.1:8032/";
const output = process.env.GUIDE_REVIEW_EVIDENCE || "/tmp/guide-review-browser";
const storageKey = "kinoko-guide-title-review-v1";

async function select(page, name) {
  await page.getByLabel("掲載名で検索").fill(name);
  await page.locator("#queue button").filter({has: page.getByText(name, {exact: true})}).click();
  await page.getByRole("heading", {name, exact: true}).waitFor();
}

async function main() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({executablePath: process.env.GUIDE_REVIEW_CHROME || undefined});
  const errors = [];
  const screenshots = [];
  const protectedRequests = [];
  const localOrigin = new URL(baseURL).origin;

  try {
    for (const width of [1440, 390, 320]) {
      const page = await browser.newPage({viewport: {width, height: width === 1440 ? 1100 : 900}});
      page.on("pageerror", error => errors.push(error.message));
      page.on("request", request => {
        const host = new URL(request.url()).hostname;
        if (request.method() !== "GET" || (!request.url().startsWith(localOrigin) && host !== "cdn-ak.f.st-hatena.com")) {
          protectedRequests.push([request.method(), host]);
        }
      });
      await page.goto(baseURL, {waitUntil: "domcontentloaded"});
      await page.getByRole("heading", {name: "ニガイグチモドキ", exact: true}).waitFor();
      assert.equal(await page.locator(".photo").count(), 4);
      assert.match(await page.locator(".photo-attention").first().innerText(), /複合/);
      const representative = width === 1440 ? "ニガイグチモドキ" : "イボテングタケ";
      await select(page, representative);
      await page.getByLabel("掲載名で検索").clear();
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.locator(".photo img").evaluateAll(images => images.forEach(image => { image.loading = "eager"; }));
      const loaded = await page.waitForFunction(() => {
        const images = [...document.querySelectorAll(".photo img")];
        return images.length !== 0 && images.every(image => image.complete && image.naturalWidth > 0);
      }, null, {timeout: 10000}).then(() => true, () => false);
      const filename = "review-" + width + ".png";
      await page.screenshot({path: path.join(output, filename), fullPage: true, animations: "disabled"});
      screenshots.push({width, file: filename, subject: representative, actualPhotosLoaded: loaded});

      // Images are tested above against the original CDN. The layout loop uses
      // fixed aspect ratios and does not repeat external asset requests.
      await page.route("https://cdn-ak.f.st-hatena.com/**", route => route.abort());
      const all = await page.locator("#queue button").evaluateAll(nodes => nodes.map(node => node.dataset.name));
      assert.equal(all.length, 126);
      for (const name of all) {
        await select(page, name);
        const dimensions = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
        assert.ok(dimensions[0] <= dimensions[1], "horizontal overflow at " + width + "px: " + name);
        assert.equal(await page.locator(".photo").count(), await page.locator(".photo a[href*='hatenablog.jp/entry/']").count());
      }
      await page.close();
    }

    const page = await browser.newPage({acceptDownloads: true, viewport: {width: 390, height: 900}});
    page.on("pageerror", error => errors.push(error.message));
    await page.route("https://cdn-ak.f.st-hatena.com/**", route => route.abort());
    await page.goto(baseURL);
    await select(page, "イボテングタケ");
    const confirm = page.getByRole("button", {name: "全写真の名称確認を記録"});
    assert.equal(await confirm.isEnabled(), false);
    const boxes = page.getByRole("checkbox", {name: "この写真の名称を確認"});
    for (const box of await boxes.all()) {
      assert.equal(await box.isChecked(), false);
      await box.check();
    }
    await page.getByLabel("確認メモ").fill("プレビューの試験メモ");
    await confirm.click();
    assert.equal(await page.locator("#progress-label").textContent(), "1 / 125");
    await page.reload();
    assert.equal(await page.getByLabel("確認メモ").inputValue(), "プレビューの試験メモ");
    assert.ok((await boxes.all()).length > 0);
    assert.equal(await boxes.first().isChecked(), true);
    await page.getByLabel("確認状況").selectOption("confirmed");
    assert.equal(await page.locator("#queue button").count(), 1);
    await page.getByLabel("確認状況").selectOption("all");
    await select(page, "キヒダタケ");
    assert.equal(await confirm.count(), 0);
    await page.getByRole("button", {name: "保留にする"}).click();
    await page.getByLabel("確認状況").selectOption("held");
    assert.equal(await page.locator("#queue button").count(), 1);

    await page.evaluate(key => {
      const data = JSON.parse(localStorage.getItem(key));
      data.active = "イボテングタケ";
      data.records["イボテングタケ"].signature = "different-observation-version";
      localStorage.setItem(key, JSON.stringify(data));
    }, storageKey);
    await page.reload();
    assert.equal(await page.locator("#progress-label").textContent(), "0 / 125");
    assert.equal(await page.getByLabel("確認メモ").isEnabled(), false);
    assert.equal(await confirm.isEnabled(), false);
    const download = page.waitForEvent("download");
    await page.locator("#export").click();
    const downloadedPath = await (await download).path();
    const exported = JSON.parse(fs.readFileSync(downloadedPath, "utf8"));
    assert.equal(exported.purpose, "local_review_notes_only");
    assert.equal(exported.records.find(item => item.name === "イボテングタケ").reviewState, "stale");
    await page.close();

    assert.deepEqual(protectedRequests, []);
    assert.deepEqual(errors, []);
    const result = {layouts: 126 * 3, screenshots, localWorkflow: "pass", browser: await browser.version()};
    fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(result, null, 2) + "\n");
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
