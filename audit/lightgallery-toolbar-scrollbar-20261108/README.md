# LightGallery toolbar / host scrollbar — Draft-only review (2026-11-08)

## Status / strict boundaries

- Base main: `cd51ca486c542ff6f33f2c9803397110b39893ec`.
- Separate from PR #137 (comments/Cloudflare): do not modify or test that work.
- **Do not merge, publish gh-pages, edit Hatena Design CSS, or paste the host patch until explicit user approval after real-device checks.**
- The user's live Hatena Design CSS contains later About/search changes and is **not** the frozen 2026-11-07 intermediate source. Never overwrite it.
- The accepted `hatena/release-2026-10-24/footer-managed.html` is hash-frozen by Gate2; never edit/rebaseline it for this UI patch.

## Minimal candidate (not yet user-accepted)

1. `assets/gallery.css`: only at desktop widths >=769px, reserve 18px at toolbar right edge and consistently size toolbar icons to 46px. Keep 768px-and-below close visibility rules intact.
2. `hatena/patches/lightgallery-overlay-scroll-lock-20261108.html`: **additive only** scoped CSS that makes the outer Hatena scrollbar invisible while our own `#kinoko-home-portal` / `#galleryWrapper` manual popover is actually open. It does not change the original parent JS or permanent page scroll styles.
3. `tests/browser/shared_lightgallery_fixture.py`: replay both candidate child CSS and parent additive CSS without production writes.
4. `tests/browser/shared_lightgallery.cjs`: Chromium checks for right gutter, uniform desktop toolbar hit areas, no host scrollbar during open, restoration of scroll styling and exact scroll position after close, plus existing mobile/desktop checks.

## Test requirements

- Isolated read-only shared LightGallery regression workflow; collect 1280 and 390 screenshots, test artifacts, and failed assertion details.
- Confirm real live Hatena embed vs standalone GitHub Pages at 1440/1280/960/390/320px, normal scroll and Hatena staging BODY scroller, Chrome desktop + Android.
- Verify close with × and Esc, forward/back history, prior scrollTop, no horizontal jump, image/EXIF caption/thumbnails, zoom/share/favorite interactions, and 768px mobile close visibility.
- Make no assumption about the scrollbar owner until rendered DOM evidence distinguishes parent viewport from child iframe scroll. The parent-scroll lock is a **candidate hypothesis**.
- Confirm native scroll restores even on failed opening, navigation, rotation, or replay; stop and revert the candidate on any regression.
- If Chrome or Android fails, **do not apply** the CSS to the live Hatena footer. Diagnose the measured owner and revise this Draft PR.

## Later release gate (requires separate explicit approval)

- Review the **current live Hatena footer**, preserve all other code, append the standalone `<style id="kinoko-lightbox-scroll-lock">...` block **once** to the footer, without replacing CSS or the 2026-10-24 accepted scripts.
- Merge this Draft PR only after CI, preview, real-device confirmation and explicit user approval. Merging main can regenerate/publish GitHub Pages.
- On failure: remove only the new additive style and restore prior CSS via an approved revert; verify original host scrolling and no stale CSS.
