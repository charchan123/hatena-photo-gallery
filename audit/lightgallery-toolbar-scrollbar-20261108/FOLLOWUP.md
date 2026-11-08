# LightGallery toolbar and scrollbar follow-up

The original README records the first Draft candidate. This follow-up uses PR base
`cd51ca486c542ff6f33f2c9803397110b39893ec` and published replay
`ae08f456729e7d89619af9569b7daecdd85080cd`. The live GitHub Pages
`assets/gallery.css` matched that published blob byte for byte. On the published
Best Shot page, gallery.css loads before best-shots.css and the vendor bundle.

## Failure analysis and repair

- The latest starting shared-gallery run (42447804441) reached the toolbar check.
  The query included three nested 20px share icons alongside the primary 46px
  buttons. The candidate now sizes direct toolbar controls only. The test checks
  both widths, as well as the actual close/zoom center distance.
- The artwork run (42447804366) rejected the added gallery.css rules. Both source
  guards compare against the PR base and permit only one byte-exact insertion
  immediately before the existing mobile rule. The other protected CSS bytes
  remain subject to the same checks. The shared guard retains its independent
  checks against the historical data/vendor baseline. The old shared source
  baseline predates the accepted artwork updates and also rejected those files.
- The current published replay already uses shared LightGallery and the accepted
  star layout. The historical dialog path still checks the native dialog when
  present. When the star sources match byte for byte, the browser now requires
  the same layout on both revisions and still exercises the simulated add control.

## Chromium evidence

Chromium replay used published HTML/data, vendored LightGallery, the frozen parent
handler and synthetic photo responses. The parent patch was applied only to the
candidate replay. At desktop widths 960, 1280 and 1440 CSS px, the close-button
right gutter was 18px and the close/zoom center distance was 46px on both entry
paths. The 1280px published embedded baseline measured 0px and 50px respectively.
The nested share icon widths remained 20px.

| 1280px scenario | Scrollbar owner measured | Published before/open/close | Candidate before/open/close | Opening → restored |
|---|---|---|---|---|
| Embedded normal host | Parent HTML viewport | 15 / 15 / 15px | 15 / 0 / 15px | 6381 → 6381px |
| Embedded Staging-style host | Independent parent BODY | 15 / 15 / 15px | 15 / 0 / 15px | 6382 → 6382px |
| Standalone Best Shot | Gallery HTML viewport | 15 / 15 / 15px | 15 / 0 / 15px | 6081 → 6081px |

The iframe document and fixed popover wrapper did not present the embedded bar.
The candidate gallery stylesheet hides its own viewport scrollbar while the
vendor's `lg-on` state is active. The unchanged additive parent patch locks only
the marked open popover. The replay checks that closing restores the host's
original scrollbar, iframe width, x-coordinate and opening scroll position.

The shared workflow publishes screenshots and measured results for each PR head.
Physical Android and the actual Hatena footer with the proposed patch still need
user review. The accepted Gate2 footer SHA-256 is
`60c08e60007b8f31a5dac61510a1a6d7bbeae51251c98aa519b5b71c93c2d3d3`.
Merge and GitHub Pages publication require explicit approval after review.
Applying the additive parent patch to Hatena requires a separate approval.
