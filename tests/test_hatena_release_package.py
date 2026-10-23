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
    assert (out/'Header.html').read_text().startswith((backup/'Header.html').read_text())
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
    assert (out/'Header.html').read_bytes().startswith(header)
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
