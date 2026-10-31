"""Artwork replacement must change paint, not content, layout or legacy availability."""
import ast
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
import main

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT/'audit/ai-image-refresh-20261031/artwork-manifest.json').read_text())

def sha(b): return hashlib.sha256(b).hexdigest()

def test_seven_original_resolution_nontransparent_webp_assets():
    assert len(M['assets']) == 7
    for row in M['assets']:
        data = (ROOT/'assets'/row['asset']).read_bytes()
        assert sha(data) == row['sha256']
        with Image.open(ROOT/'assets'/row['asset']) as image:
            assert image.format == 'WEBP'
            assert image.size == (row['width'], row['height'])
            assert 'A' not in image.getbands()
        assert row['quality'] == 92 and row['method'] == 6
        assert len(row['source_sha256']) == 64

def test_all_active_css_uses_new_artwork_and_preserves_every_other_declaration():
    names = set(M['replacements']) | {r['asset'] for r in M['assets']}
    used = set()
    for file, expected in M['css_non_artwork_sha256'].items():
        css = (ROOT/file).read_text()
        assert all(old not in css for old in M['replacements'])
        used.update(r['asset'] for r in M['assets'] if r['asset'] in css)
        normalized = re.sub(r'url\(([^)]+)\)', lambda m:'url(AI_ARTWORK)' if m[1].strip('\"\'') in names else m[0], css)
        assert sha(normalized.encode()) == expected, file
    assert used == {r['asset'] for r in M['assets']}

def test_current_assets_and_unreferenced_legacy_assets_are_delivered_verbatim(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'OUTPUT_DIR', str(tmp_path))
    main.copy_shared_assets()
    for row in M['assets']:
        assert sha((tmp_path/'assets'/row['asset']).read_bytes()) == row['sha256']
    for name, expected in M['legacy_sha256'].items():
        assert sha((ROOT/'assets'/name).read_bytes()) == expected
        assert sha((tmp_path/'assets'/name).read_bytes()) == expected

def test_generator_logic_outside_asset_delivery_is_identical():
    source = ast.parse((ROOT/'main.py').read_text())
    source.body = [n for n in source.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) or n.name != 'copy_shared_assets']
    assert sha(ast.dump(source,include_attributes=False).encode()) == M['generator_ast_excluding_asset_copy_sha256']
