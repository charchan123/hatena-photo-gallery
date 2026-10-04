from pathlib import Path
import re


def test_aiuo_page_overrides_legacy_900px_max_width():
    css = Path("assets/aiuo.css").read_text(encoding="utf-8")
    match = re.search(r"\.aiuo-index\s+\.aiuo-page\s*\{([^}]*)\}", css, re.S)
    assert match is not None
    block = re.sub(r"\s+", "", match.group(1))
    assert "width:min(100%,1180px);" in block
    assert "max-width:1180px;" in block
