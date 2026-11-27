"""Exercise the integrated, review-only trial in a real browser."""
import argparse
from collections import Counter
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
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
    page.locator('button[data-page="guide-review"]').click()
    expect(page.locator("#guide-item h3")).to_have_text("センニンタケ")
    expect(page.locator("#guide-items option")).to_have_count(65)


def verify_width(page, url, items):
    enter(page, url)
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
    expect(page.get_by_role("button", name="旧承認の指定3枚を再確認して保存")).to_be_disabled()
    page.get_by_role("button", name="写真ごとに確認", exact=True).click()
    expect(page.get_by_role("button", name="この写真の掲載名を確認").nth(0)).to_be_disabled()
    page.get_by_role("button", name="写真を拡大").nth(1).click()
    expect(page.get_by_role("dialog", name="写真の拡大")).to_be_visible()
    page.get_by_role("button", name="写真を閉じる").click()
    inaccessible.clear()
    page.locator(".guide-backup summary").click()
    page.locator("#guide-refresh").click()
    expect(all_button).to_be_enabled()
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

    tab.locator("#guide-reviewer").fill("別タブ")
    tab.get_by_role("button", name="保留して次へ").click()
    expect(tab.locator("#guide-feedback")).to_contain_text("別の画面で保存されました")

    with page.expect_download() as download:
        page.locator("#guide-export").click()
    backup = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert backup["revision"] == 1 and backup["events"][0]["scope"] == "all"
    page.locator("#guide-import").set_input_files({"name": "bad.json", "mimeType": "application/json", "buffer": b"{}"})
    page.locator("#guide-restore").click()
    expect(page.locator("#guide-feedback")).to_contain_text("バックアップの版・対象・改訂番号")
    page.locator("#guide-import").set_input_files({"name": "valid.json", "mimeType": "application/json",
                                                 "buffer": json.dumps(backup).encode("utf-8")})
    page.locator("#guide-restore").click()
    expect(page.locator("#guide-feedback")).to_contain_text("復元 0件")

    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="名称確認を訂正・再確認").click()
    expect(page.locator("#guide-feedback")).to_contain_text("改訂 2")
    expect(page.locator("#guide-item > p").first).to_contain_text("未確認")


def screenshots(browser, url, output):
    for width in (1440, 390):
        page = browser.new_page(viewport={"width": width, "height": 940})
        enter(page, url)
        expect(page.get_by_text("表示できた写真 3／3枚", exact=False)).to_be_visible(timeout=35000)
        page.locator("#guide-photos").scroll_into_view_if_needed()
        page.screenshot(path=output / f"review-{width}.png")
        page.close()


def main():
    args = read_args()
    args.output.mkdir(parents=True, exist_ok=True)
    portal = json.loads(args.portal.read_bytes())
    results = {}
    with TemporaryDirectory() as directory, sync_playwright() as playwright:
        review = GuideReview(directory, lambda: portal)
        review.refresh()
        items = review.items
        legacy = items[item_id("センニンタケ")]
        inaccessible = {legacy["photos"][0]["identity"]["url"]}
        fixture = test_image()

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
                for width in (1440, 390, 320):
                    page = browser.new_page(viewport={"width": width, "height": 900})
                    results[str(width)] = {"items": len(items), "photos": verify_width(page, url, items)}
                    page.close()
                context = browser.new_context(viewport={"width": 390, "height": 850})
                verify_actions(context.new_page(), context.new_page(), url, items, inaccessible)
                context.close()
                if args.real_screenshots:
                    review.image_loader = fetch_photo
                    screenshots(browser, url, args.output)
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
