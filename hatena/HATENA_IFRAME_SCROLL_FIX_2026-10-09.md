# Hatena parent iframe height handler — manual replacement candidate

PARENT_HATENA_PATCH_REQUIRED: YES

This repository cannot update the Hatena parent. No production save has been performed.

## Cause and scope

The public `/new-top` footer sets `photoGallery.style.height = "0px"`, reads `offsetHeight` (forced layout), then assigns the real height. This temporary collapse lets the browser clamp the parent's scroll position. In-place filters/details do not need `scrollToTitle`.

The adjacent HTML candidate replaces **only the complete photoGallery communication script**, not the PAGE TOP script or the whole footer. Do not append a second handler. Back up the current footer and use Hatena Preview before any separately authorized production save.

## Replacement behavior

- Assign the finite, nonnegative actual height directly; never collapse to zero as an intermediate step.
- Reserve minimum height on the outer wrapper when content shrinks near the page bottom. This may leave blank space below the iframe; it preserves the viewport without lying about iframe height. Upward scrolling, child navigation/load, and growth reclaim it.
- Preserve `requestHeight`, explicit navigation `scrollToTitle`, and `lgClosed` fullscreen cleanup/retries.
- Accept messages only from this iframe's `contentWindow` and its exact URL origin. A future hosting-origin change needs review.
- Do not call `scrollTo` for filters, tabs, search or details. Navigation remains separate.

## Manual verification and rollback

Compare feature on/off/clear, season tabs, kana/search, details open/close and bottom-edge collapse. Record parent scrollY, message types, and iframe actual height. Check navigation and lightGallery close separately. Test mobile MENU/PAGE TOP and native Hatena controls without submitting posts or stars.

To roll back, restore the backed-up communication script and CSS. The Slim CSS baseline remains unchanged. The mobile Design CSS candidate is a separate full replacement artifact, not an automatic deployment.

See `MOBILE_OPTIMIZATION_RECOVERY_REPORT_2026-10-09.md` and `mobile-review-2026-10-09/` for validation results and limitations.
