import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_package',ROOT/'tools/hatena_release_package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

@pytest.fixture
def inputs(tmp_path):
    source=tmp_path/'export';source.mkdir()
    css=(package.RELEASE/'design.css').read_text(encoding='utf-8')
    (source/'DesignCSS.txt').write_text('\n'.join(package.sections(css))+'\n/* current customization */',encoding='utf-8')
    (source/'Header.html').write_text('<div class="header1">existing header</div>',encoding='utf-8')
    block='<script>const iframe="photoGallery";const ack="navigationIntentAck";</script>'
    (source/'Footer.html').write_text('<p>keep</p>'+block+'<script>/* PAGE TOP and other integration */</script>',encoding='utf-8')
    (source/'NewTop.html').write_text('<iframe id="photoGallery">unchanged</iframe>',encoding='utf-8')
    (source/'Settings.json').write_text('{"responsive":true}',encoding='utf-8')
    target=tmp_path/'backup';package.backup(source,target)
    review=tmp_path/'review.json';review.write_text(json.dumps({'approved_for_preparation':True,
        'production_publish_approved':False,'files':package.inventory(target),
        'managed_script_sha256':package.sha(block.encode())}),encoding='utf-8')
    return source,target,review,tmp_path/'prepared'

def test_backup_never_overwrites_and_preserves_original_bytes(inputs):
    source,target,_,_=inputs
    assert package.inventory(source)==package.inventory(target)
    with pytest.raises(ValueError):package.backup(source,target)

def test_preparation_retains_other_footer_header_and_newtop(inputs):
    _,backup,review,out=inputs;package.prepare(backup,review,out)
    assert (out/'NewTop.html').read_bytes()==(backup/'NewTop.html').read_bytes()
    assert (out/'Header.html').read_text().endswith((backup/'Header.html').read_text())
    footer=(out/'Footer.html').read_text()
    assert footer.startswith('<p>keep</p>')
    assert footer.endswith('<script>/* PAGE TOP and other integration */</script>')
    assert footer.count('kinokoHeightBound')==2
    assert package.inventory(backup)==json.loads((backup/'SHA256.json').read_text())

def test_windows_crlf_outside_reviewed_script_is_byte_preserved(inputs):
    _,backup,review,out=inputs
    header=b'<div>Windows header</div>\r\n'
    block=b'<script>\r\nconst iframe="photoGallery";\r\nconst ack="navigationIntentAck";\r\n</script>'
    prefix=b'<p>keep</p>\r\n';suffix=b'\r\n<script>/* PAGE TOP */</script>\r\n'
    (backup/'Header.html').write_bytes(header)
    (backup/'Footer.html').write_bytes(prefix+block+suffix)
    hashes=package.inventory(backup)
    (backup/'SHA256.json').write_text(json.dumps(hashes))
    r=json.loads(review.read_text());r.update(files=hashes,managed_script_sha256=package.sha(block))
    review.write_text(json.dumps(r));package.prepare(backup,review,out)
    assert (out/'Header.html').read_bytes().endswith(header)
    assert (out/'Footer.html').read_bytes().startswith(prefix)
    assert (out/'Footer.html').read_bytes().endswith(suffix)

@pytest.mark.parametrize('change',['backup','review','handler','theme','duplicate','legacy_handler'])
def test_unsafe_or_stale_inputs_stop_before_output(inputs,change):
    _,backup,review,out=inputs;r=json.loads(review.read_text())
    if change=='backup':(backup/'Header.html').write_text('stale')
    elif change=='review':r['approved_for_preparation']=False
    elif change=='handler':r['managed_script_sha256']='0'*64
    elif change=='theme':
        p=backup/'DesignCSS.txt';p.write_text(p.read_text().replace('8599973812333959601','999'))
        (backup/'SHA256.json').write_text(json.dumps(package.inventory(backup)));r['files']=package.inventory(backup)
    else:
        p=backup/'Footer.html'
        p.write_text(p.read_text()*2 if change=='duplicate' else p.read_text()+'<script>/* old photoGallery handler */</script>')
        (backup/'SHA256.json').write_text(json.dumps(package.inventory(backup)));r['files']=package.inventory(backup)
    review.write_text(json.dumps(r))
    with pytest.raises(ValueError):package.prepare(backup,review,out)
    assert not out.exists()


# Gate2 accepted-source parity and public binding safety.
"""Offline parity between Gate2 accepted sources and public release components."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "hatena/release-2026-10-24"


def test_gate2_frozen_component_hashes():
    manifest = json.loads((RELEASE / "gate2-accepted.json").read_text())
    for name, expected in manifest["candidate_files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name


def test_public_binding_has_no_private_host_or_staging_query():
    manifest = json.loads((RELEASE / "gate2-accepted.json").read_text())
    for name in manifest["candidate_files"]:
        text = (ROOT / name).read_text()
        assert ".workers.dev" not in text, name
        assert "cloudflareaccess.com" not in text, name
        assert "?_staging=" not in text, name
    for name in ("design.css", "footer-managed.html"):
        assert "https://charchan123.github.io/hatena-photo-gallery/" in (RELEASE / name).read_text()


def test_components_are_exactly_their_distribution_blocks():
    managed = (RELEASE / "footer-managed.html").read_text()
    scripts = re.findall(r"<script>\s*([\s\S]*?)</script>", managed)
    assert len(scripts) == 2
    assert scripts[0].strip() == (RELEASE / "home-bootstrap.js").read_text().strip()
    assert (RELEASE / "design.css").read_text().endswith((RELEASE / "home.css").read_text())


def test_parent_security_and_viewport_contract():
    managed = (RELEASE / "footer-managed.html").read_text()
    assert "event.source !== iframe.contentWindow || event.origin !== galleryOrigin" in managed
    assert "portalWide:document.getElementById('kinoko-home-portal') ? window.innerWidth >= 900 : undefined" in managed
    assert "type:'photoOpeningAck', id:data.id, ok" in managed
    assert "menu.hidden = true;" in managed
    assert "menu.hidden = false;" in managed
    assert "allow-scripts allow-same-origin allow-forms allow-pointer-lock allow-popups allow-downloads allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation allow-presentation allow-orientation-lock allow-modals" in managed


def test_css_limit_and_shared_category_scope():
    css = (RELEASE / "design.css").read_bytes()
    assert len(css) <= 65536
    assert len(css.replace(b"\n", b"\r\n")) <= 65536
    text = css.decode()
    assert "body.page-archive-category:is(.category-日常の記録, .category-キノコ探索日記)" in text
    assert 'content: "FIELD NOTES"' in text
    assert "body.kinoko-home-ready > nav.blog-controlls" in text


def test_child_hashes_and_mixed_version_compatibility():
    assert hashlib.sha256((ROOT / "assets/gallery.js").read_bytes()).hexdigest() == "23e8bb1abd04b5f0c034fd6dc84aee5bd72611474d34b312f08e1536e603d734"
    assert hashlib.sha256((ROOT / "assets/portal.css").read_bytes()).hexdigest() == "2eff9ed126bc16447b42b63ff9ccb51065619784d28eb31d285df3aaccf0e13a"
    code = (ROOT / "assets/gallery.js").read_text()
    assert "event.data.photoOpeningProtocol === 1" in code
    assert 'type:"lgOpening"' in code or "type:'lgOpening'" in code
