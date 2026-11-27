"""Exercise the integrated, review-only trial in a real browser."""
import argparse
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import sleep
from urllib.error import URLError

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from admin.comment_trial import fixtures
from admin.guide_review import GuideReview, fetch_photo, item_id
from tools.guide_review_trial import TrialServer


def test_image():
    file = BytesIO()
    Image.new("RGB", (150, 110), "#515940").save(file, format="PNG")
    return file.getvalue(), "image/png"


def read_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("portal", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--chromium")
    parser.add_argument("--real-screenshots", action="store_true")
    return parser.parse_args()


def enter(page, url):
    page.goto(url)
    expect(page.locator("#trial-banner")).to_be_visible()
    navigate(page, "guide-review")
    expect(page.locator("#guide-item h3")).to_have_text("センニンタケ")
    expect(page.locator("#guide-items option")).to_have_count(65)


def navigate(page, name):
    menu = page.locator("#admin-menu")
    if menu.is_visible() and menu.get_attribute("aria-expanded") == "false":
        menu.click()
    page.locator(f'button[data-page="{name}"]').click()
    if menu.is_visible():
        expect(menu).to_have_attribute("aria-expanded", "false")
        expect(page.locator("#page-title")).to_be_focused()


def check_menu(page, url, output=None):
    page.goto(url)
    expect(page.locator("#trial-banner")).to_be_visible()
    menu = page.locator("#admin-menu")
    if output and menu.is_visible():
        page.screenshot(path=output / "dashboard-phone.png")
        menu.click()
        page.screenshot(path=output / "menu-open-phone.png")
        page.keyboard.press("Escape")
        expect(menu).to_be_focused()
        expect(menu).to_have_attribute("aria-expanded", "false")
    buttons = page.locator('#admin-navigation [data-page]').evaluate_all("(items) => items.map(x => x.dataset.page)")
    assert len(buttons) == 11
    for name in buttons:
        navigate(page, name)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (page.viewport_size, name)
        if name not in {"dashboard", "guide-review", "comments"}:
            expect(page.locator("#trial-unavailable")).to_be_visible()


def supplementary(page):
    section = page.locator("#guide-reviewer").locator("xpath=ancestor::details[1]")
    if section.get_attribute("open") is None:
        section.locator("summary").click()


def verify_width(page, url, items):
    enter(page, url)
    page.locator(".guide-filters summary").click()
    page.locator("#guide-priority").select_option("")
    expect(page.locator("#guide-items option")).to_have_count(126)
    reading = 0
    for key, item in items.items():
        page.locator("#guide-items").select_option(key)
        expect(page.locator("#guide-item h3")).to_have_text(item["name"])
        expect(page.locator("#guide-photos article")).to_have_count(len(item["photos"]))
        reading += len(item["photos"])
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (page.viewport_size, item["name"])
        assert page.locator(".guide-dock .primary").evaluate("b => b.getBoundingClientRect().height >= 44")
    return reading


def verify_actions(page, tab, url, items, inaccessible):
    enter(page, url)
    enter(tab, url)
    all_button = page.get_by_role("button", name="全3枚の名称を確認して次へ")
    expect(page.get_by_text("表示できた写真 2／3枚", exact=False)).to_be_visible()
    expect(all_button).to_be_disabled()
    expect(page.get_by_text("画像を読み込めません", exact=False)).to_be_visible()
    supplementary(page)
    expect(page.get_by_role("button", name="旧承認の指定3枚を再確認して保存")).to_be_disabled()
    page.get_by_role("button", name="写真ごとに確認", exact=True).click()
    expect(page.get_by_role("button", name="この写真の掲載名を確認").nth(0)).to_be_disabled()
    page.get_by_role("button", name="写真を拡大").nth(1).click()
    expect(page.get_by_role("dialog", name="写真の拡大")).to_be_visible()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#admin-photo-viewer output")).to_have_text("2 / 2")
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="写真を拡大").nth(1)).to_be_focused()
    inaccessible.clear()
    page.locator(".guide-backup summary").click()
    page.locator("#guide-refresh").click()
    expect(all_button).to_be_enabled()
    supplementary(page)
    page.locator("#guide-reviewer").fill("ブラウザ試験")
    page.locator("#guide-note").fill("写真を目視する操作の回帰試験")
    pending = page.locator("#guide-items option").nth(1).get_attribute("value")
    all_button.click()
    expect(page.locator("#guide-feedback")).to_contain_text("保存しました")
    expect(page.locator("#guide-item h3")).to_have_text(items[pending]["name"])
    page.get_by_role("button", name="前の項目").click()
    expect(page.locator("#guide-item h3")).to_have_text("センニンタケ")
    expect(page.locator("#guide-item > p").first).to_contain_text("名称確認済み")
    page.get_by_text("確認履歴", exact=True).click()
    expect(page.get_by_text("写真を目視する操作の回帰試験")).to_be_visible()

    supplementary(tab)
    tab.locator("#guide-reviewer").fill("別タブ")
    tab.get_by_role("button", name="保留して次へ").click()
    expect(tab.locator("#guide-feedback")).to_contain_text("別の画面で保存されました")

    with page.expect_download() as download:
        page.locator("#guide-export").click()
    backup = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert backup["target"] == "kinoko-guide-review-trial"
    assert backup["revision"] == 1 and backup["events"][0]["scope"] == "all"
    page.locator("#guide-import").set_input_files({"name": "bad.json", "mimeType": "application/json", "buffer": b"{}"})
    page.locator("#guide-restore").click()
    expect(page.locator("#guide-feedback")).to_contain_text("バックアップの版・対象・改訂番号")
    page.locator("#guide-import").set_input_files({"name": "valid.json", "mimeType": "application/json",
                                                 "buffer": json.dumps(backup).encode("utf-8")})
    page.locator("#guide-restore").click()
    expect(page.locator("#guide-feedback")).to_contain_text("復元 0件")

    supplementary(page)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="名称確認を訂正・再確認").click()
    expect(page.locator("#guide-feedback")).to_contain_text("改訂 2")
    expect(page.locator("#guide-item > p").first).to_contain_text("未確認")


    mode = page.get_by_role("button", name="写真ごとに確認", exact=True)
    if mode.get_attribute("aria-expanded") == "false":
        mode.click()
    page.get_by_role("button", name="この写真の掲載名を確認").first.click()
    expect(page.locator("#guide-feedback")).to_contain_text("改訂 3")
    expect(page.get_by_role("button", name="写真ごとに確認", exact=True)).to_have_attribute("aria-expanded", "true")
    page.get_by_text("図鑑原稿・出典・個別審査", exact=True).click()
    page.get_by_text("原稿の修正案を保存", exact=True).click()
    page.locator("#guide-proposal-after").fill("試験用の修正案")
    page.locator("#guide-proposal-reason").fill("試験用の理由")
    page.get_by_label("元資料と現在の原稿を照合しました").check()
    page.get_by_role("button", name="修正案を保存", exact=True).click()
    expect(page.get_by_text("修正案を保存しました。", exact=False)).to_be_visible()
    page.reload()
    navigate(page, "guide-review")
    supplementary(page)
    expect(page.locator("#guide-reviewer")).to_have_value("ブラウザ試験")
    page.get_by_text("図鑑原稿・出典・個別審査", exact=True).click()
    page.get_by_text("原稿の修正案を保存", exact=True).click()
    expect(page.locator("#guide-proposal-after")).to_have_value("試験用の修正案")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="保存済みの修正案を取り消す").click()
    expect(page.get_by_text("修正案を取り消しました。")).to_be_visible()


def comments_screen(page, url, output=None):
    page.goto(url)
    expect(page.locator("#trial-banner")).to_be_visible()
    navigate(page, "comments")
    cases = page.locator("#comments-cases article")
    expect(cases).to_have_count(3)
    cases.first.get_by_role("button", name="コメントを見る").click()
    expect(page.locator("#comments-photos figure")).to_have_count(2)
    expect(page.locator("#comments-list article")).to_have_count(2)
    expect(page.get_by_role("button", name="公式返信を送信")).to_have_count(0)
    page.locator("#comments-unread").uncheck()
    expect(page.locator("#comments-list article")).to_have_count(3)
    page.get_by_role("button", name="履歴・通報を見る").first.click()
    expect(page.get_by_text("試験用の通報", exact=False)).to_be_visible()
    if output:
        page.locator("#comments-photos").scroll_into_view_if_needed()
        page.screenshot(path=output / f'comments-{page.viewport_size["width"]}.png')
    page.locator("#comments-photos button").first.click()
    expect(page.locator("#admin-photo-viewer output")).to_have_text("1 / 2")
    page.get_by_role("button", name="次の写真").click()
    expect(page.locator("#admin-photo-viewer output")).to_have_text("2 / 2")
    page.keyboard.press("Escape")
    cases.nth(1).get_by_role("button", name="コメントを見る").click()
    expect(page.locator("#comments-photos figure")).to_have_count(1)
    expect(page.locator("#comments-photos")).to_contain_text("判明済み")
    cases.nth(2).get_by_role("button", name="コメントを見る").click()
    expect(page.locator("#comments-photos")).to_contain_text("写真との紐付けを確認中")
    page.locator("#comments-case-filter").select_option("all")
    expect(cases).to_have_count(4)
    cases.nth(2).get_by_role("button", name="コメントを見る").click()
    expect(page.locator("#comments-list")).to_contain_text("コメントがまだありません")
    if output and page.viewport_size["width"] == 390:
        page.locator("#comments-list").scroll_into_view_if_needed()
        page.screenshot(path=output / "comments-empty.png")
    page.locator("#comments-search").fill("接続失敗")
    expect(page.locator("#comments-feedback")).to_contain_text("コメント管理APIに接続できません")
    if output and page.viewport_size["width"] == 390:
        page.locator("#comments-feedback").scroll_into_view_if_needed()
        page.screenshot(path=output / "comments-connection-error.png")
    status = page.evaluate("""async () => {
      const state = await (await fetch('/api/state')).json();
      const response = await fetch('/api/comments/request', {method:'POST', headers:{
        'Content-Type':'application/json', 'X-CSRF-Token':state.csrf},
        body:JSON.stringify({action:'action',values:{}})});
      return response.status;
    }""")
    assert status == 403


def screenshots(browser, url, output):
    for width in (1440, 390):
        page = browser.new_page(viewport={"width": width, "height": 940})
        enter(page, url)
        expect(page.get_by_text("表示できた写真 3／3枚", exact=False)).to_be_visible(timeout=35000)
        page.locator("#guide-photos").scroll_into_view_if_needed()
        page.screenshot(path=output / f"review-{width}.png")
        photo = page.get_by_role("button", name="写真を拡大").first
        photo.click()
        page.screenshot(path=output / f"viewer-{width}.png")
        page.keyboard.press("Escape")
        page.get_by_role("button", name="写真ごとに確認", exact=True).click()
        page.screenshot(path=output / f"individual-{width}.png")
        page.get_by_text("図鑑原稿・出典・個別審査", exact=True).click()
        page.locator(".guide-manuscript-preview").scroll_into_view_if_needed()
        page.screenshot(path=output / f"manuscript-{width}.png")
        page.get_by_text("原稿の修正案を保存", exact=True).click()
        page.locator("#guide-proposal-after").fill("試験用の入力例")
        page.screenshot(path=output / f"proposal-{width}.png")
        page.close()


def public_photos(portal, legacy):
    urls = [photo["identity"]["url"] for photo in legacy["photos"]]
    cases, _ = fixtures(portal)
    urls += [photo["src"] for case in cases for photo in case["media"]["photos"]]
    pictures = {}
    for url in dict.fromkeys(urls):
        for attempt in range(3):
            try:
                pictures[url] = fetch_photo(url)
                break
            except (OSError, URLError):
                if attempt == 2:
                    raise
                sleep(1)
    return pictures


def main():
    args = read_args()
    args.output.mkdir(parents=True, exist_ok=True)
    portal = json.loads(args.portal.read_bytes())
    results = {}
    with TemporaryDirectory() as directory, sync_playwright() as playwright:
        review = GuideReview(directory, lambda: portal, trial=True)
        review.refresh()
        items = review.items
        legacy = items[item_id("センニンタケ")]
        inaccessible = {legacy["photos"][0]["identity"]["url"]}
        fixture = test_image()
        published = public_photos(portal, legacy) if args.real_screenshots else {}

        def load(url):
            if url in inaccessible:
                raise OSError("simulated unavailable image")
            return fixture

        review.image_loader = load
        browser = playwright.chromium.launch(executable_path=args.chromium)
        with TrialServer(0, directory, review) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}"
            try:
                for width, height in [(1440, 900), (1280, 900), (390, 850), (360, 780), (320, 720), (780, 390)]:
                    page = browser.new_page(viewport={"width": width, "height": height})
                    check_menu(page, url, args.output if width == 390 else None)
                    results[f"{width}x{height}"] = {"items": len(items), "photos": verify_width(page, url, items)}
                    page.close()
                context = browser.new_context(viewport={"width": 390, "height": 850})
                verify_actions(context.new_page(), context.new_page(), url, items, inaccessible)
                context.close()
                if args.real_screenshots:
                    review.image_loader = lambda url: published[url]
                    screenshots(browser, url, args.output)
                for width in (1440, 390):
                    page = browser.new_page(viewport={"width": width, "height": 920})
                    def serve_photo(route):
                        picture = published.get(route.request.url, fixture)
                        route.fulfill(body=picture[0], content_type=picture[1])
                    page.route("https://cdn-ak.f.st-hatena.com/**", serve_photo)
                    comments_screen(page, url, args.output)
                    page.close()
            finally:
                server.shutdown()
                thread.join()
        browser.close()
    (args.output / "browser-results.json").write_text(
        json.dumps({"viewports": results, "groups": Counter(i["group"] for i in items.values()),
                    "browser_actions": "passed", "real_photos_in_screenshots": args.real_screenshots}, indent=2),
        encoding="utf-8",
    )
    print(results)


if __name__ == "__main__":
    main()
