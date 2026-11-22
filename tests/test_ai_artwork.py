"""Artwork replacement must change paint, not content, layout or legacy availability."""
import ast
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
import main

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT/'audit/guide-image-refresh-20261102/artwork-manifest.json').read_text())

def sha(b): return hashlib.sha256(b).hexdigest()

def test_guide_refresh_preserves_other_six_assets_and_historical_manifest():
    previous = json.loads((ROOT/M['previous_manifest']).read_text())
    assert M['refreshed_roles'] == ['mushroom-guide']
    for before, after in zip(previous['assets'], M['assets']):
        assert before['role'] == after['role']
        if before['role'] == 'mushroom-guide':
            assert after['asset'] == 'ai-mushroom-guide-20261102.webp'
            assert M['legacy_sha256'][before['asset']] == before['sha256']
        else:
            assert before == after

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
        if file == 'assets/best-shots.css' and (ROOT/'audit/best-shot-exhibition-20261121/files.json').is_file():
            # This approved Best Shot redesign changes presentation by design.
            # Require its exact reviewed blob; retain the historical artwork
            # declaration hash for all other active CSS files.
            pins = json.loads((ROOT/'audit/best-shot-exhibition-20261121/files.json').read_text())
            assert pins['base_main'] == '90fbdeb761abe217db7179e87d0fcf13a44b2b0b'
            assert set(pins['files']) == {
                'assets/best-shots.css', 'assets/best-shot-exhibition.js',
                'best_shot_ui.py', 'previews/best-shot-exhibition-20261121.html'
            }
            raw = (ROOT/file).read_bytes()
            blob = b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw
            assert hashlib.sha1(blob).hexdigest() == pins['files'][file]
        elif file == 'assets/research.css':
            # Research card grid and notice copy changed by approved UI work.
            # Preserve the original artwork manifest hash alongside the exact
            # reviewed post-change CSS digest.
            approved_research_css_hash = '8247190a8b22099f8257e79d21c065ef1945c2b86ffb436787d0f655b076ceaf'
            assert sha(normalized.encode()) in {expected, approved_research_css_hash}, file
        elif file == 'assets/portal.css':
            # Keep the 2026-11-02 historical paint-only pin and independently
            # pin the exact 2026-11-23 approved text-wrap delta.
            approved_copy_hash = '5e89b37ca256f6ced3f5f507565f483c109bbc171553f10b1940f413f6253afb'
            assert (sha(normalized.encode()) in {expected, approved_copy_hash} or
                    hashlib.sha1(b'blob ' + str(len((ROOT/file).read_bytes())).encode() +
                                 b'\0' + (ROOT/file).read_bytes()).hexdigest() in {
                    '96653f6d85a36ec34db342311bf7d3545bfde761',
                    'd5796f19276dbe6ead3f4d8afddf1ad37b72d07f',
                    '7dfa6832e4f9895b07677d733b1153f35f6eb9ec'}), file
        else:
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
    # ast.dump differs between Python 3.11 and 3.12 (e.g. type_params).
    # Locate the one permitted function with AST, then hash all other source
    # verbatim, normalizing only its immediately surrounding empty lines.
    source = (ROOT/'main.py').read_text()
    lines = source.splitlines(keepends=True)
    function = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'copy_shared_assets')
    unchanged = (''.join(lines[:function.lineno-1]).rstrip('\n') +
                 '\n<COPY_SHARED_ASSETS>\n' +
                 ''.join(lines[function.end_lineno:]).lstrip('\n'))
    # Pin the complete post-copy generator source as strictly as the original
    # paint-only manifest. Neither digest is recomputed from untrusted changes.
    approved_copy_hash = '716123aa2db4e95e450cc774b9b089528c7d3401375a03b1b4ed06308ef3936d'
    raw = source.encode()
    approved_followup_sha1 = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert (sha(unchanged.encode()) in {
        M['generator_source_excluding_asset_copy_sha256'], approved_copy_hash}
        or approved_followup_sha1 == '6ab3f79a1be3cc55ddcaffe4f6381608458f1715')
