"""Shared LightGallery dependencies for generated photo pages (one copy per page)."""

LIGHTGALLERY_TAGS = """
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/css/lightgallery-bundle.min.css">

<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/lightgallery.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/zoom/lg-zoom.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/thumbnail/lg-thumbnail.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/autoplay/lg-autoplay.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/plugins/share/lg-share.min.js"></script>
"""

# Pages already publishes these exact 2.8.3 vendor files. Keep the guide's CDN
# tags unchanged, and derive Best Shot's ordered non-parser-blocking local tags.
BEST_SHOT_LIGHTGALLERY_TAGS = (LIGHTGALLERY_TAGS
    .replace("https://cdn.jsdelivr.net/npm/lightgallery@2.8.3/", "lightgallery/")
    .replace("css/lightgallery-bundle.min.css", "lightgallery-bundle.min.css")
    .replace("plugins/zoom/", "").replace("plugins/thumbnail/", "")
    .replace("plugins/autoplay/", "").replace("plugins/share/", "")
    .replace('<script src=', '<script defer src=')
    .replace('<link rel="stylesheet"', '<link rel="stylesheet" data-lightgallery-style'))
