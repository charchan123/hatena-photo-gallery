"""Permit only the reviewed LightGallery additions to the base stylesheet."""

MOBILE_RULE = '/* ===== LightGallery：スマホでは×を常時表示 ===== */'.encode()
VIEWER_RULES = b"""/* LightGallery adds lg-on to this document while its full-page viewer is open. */
html.lg-on {
  overflow-y: hidden;
}

/* Space the desktop toolbar buttons without resizing the nested share menu. */
@media (min-width: 769px) {
  .lg-outer .lg-toolbar {
    box-sizing: border-box;
    padding-right: 18px;
  }

  .lg-outer .lg-toolbar > .lg-icon {
    width: 46px;
  }
}

"""


def verify_gallery_css(base, candidate):
    if candidate == base:
        return False
    assert base.count(MOBILE_RULE) == 1, 'gallery.css mobile rule anchor changed'
    assert VIEWER_RULES not in base, 'gallery.css already contains the reviewed viewer rules'
    assert candidate == base.replace(MOBILE_RULE, VIEWER_RULES + MOBILE_RULE, 1), (
        'gallery.css differs outside the reviewed LightGallery viewer rules'
    )
    return True
