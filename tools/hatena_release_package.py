"""Offline backup and reviewed release assembly. No network or editor access.

Private inputs/output must stay outside Git. A matching review is a preparation
gate, not permission to save Hatena settings or publish anything.
"""
from pathlib import Path
import argparse, difflib, hashlib, json, re, shutil

RELEASE=Path(__file__).resolve().parents[1]/'hatena/release-2026-10-24'
NAMES=('DesignCSS.txt','Header.html','Footer.html','NewTop.html','Settings.json')
def sha(value):return hashlib.sha256(value).hexdigest()
def inventory(folder):
    return {name:{'bytes':len((folder/name).read_bytes()),'sha256':sha((folder/name).read_bytes())} for name in NAMES}
def fresh(folder):
    if folder.exists():raise ValueError('Output already exists; choose a new folder. Nothing was overwritten.')
    folder.mkdir(parents=True)
def backup(source, target):
    before=inventory(source)
    fresh(target)
    for name in NAMES:shutil.copyfile(source/name,target/name)
    assert inventory(target)==before
    (target/'SHA256.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
    return before
def sections(text):
    return [v.replace('\r\n','\n').strip() for v in re.findall(r'/\* <system .*?/\* </system> \*/',text,re.S)]
def prepare(source, review_file, target):
    actual=inventory(source)
    if json.loads((source/'SHA256.json').read_text(encoding='utf-8'))!=actual:
        raise ValueError('Backup hash mismatch; stop without changing the backup.')
    review=json.loads(review_file.read_text(encoding='utf-8'))
    if review.get('approved_for_preparation') is not True or review.get('files')!=actual:
        raise ValueError('Current editor exports have not been reviewed at these exact hashes.')
    if review.get('production_publish_approved') is not False:
        raise ValueError('This tool only prepares an unpublished candidate.')
    css=(RELEASE/'design.css').read_bytes()
    oldcss=(source/'DesignCSS.txt').read_text(encoding='utf-8')
    if len(css)>65536 or len(sections(oldcss))!=2 or sections(oldcss)!=sections(css.decode('utf-8')):
        raise ValueError('Theme/system sections differ or CSS exceeds 64KiB; reconciliation required.')
    oldfooter=(source/'Footer.html').read_bytes().decode('utf-8')
    blocks=[m for m in re.finditer(r'<script\b[^>]*>[\s\S]*?</script\s*>',oldfooter,re.I)
            if 'photoGallery' in m.group()]
    if len(blocks)!=1 or 'navigationIntentAck' not in blocks[0].group() or sha(blocks[0].group().encode())!=review.get('managed_script_sha256'):
        raise ValueError('The old communication script was not uniquely identified and reviewed.')
    header=(source/'Header.html').read_bytes().decode('utf-8')
    if 'kinoko-home-release' in header or 'kinoko-home-portal' in oldfooter:
        raise ValueError('Release marker/managed payload already present; do not append twice.')
    b=blocks[0]
    newfooter=oldfooter[:b.start()]+(RELEASE/'footer-managed.html').read_text(encoding='utf-8')+oldfooter[b.end():]
    generated={'DesignCSS.txt':css,
      'Header.html':((RELEASE/'header-activation.html').read_text(encoding='utf-8')+'\n'+header).encode(),
      'Footer.html':newfooter.encode(),
      'NewTop.html':(source/'NewTop.html').read_bytes(),
      'Settings.json':(source/'Settings.json').read_bytes()}
    fresh(target)
    for name,value in generated.items():(target/name).write_bytes(value)
    changes=[]
    for name in NAMES:
        changes.extend(difflib.unified_diff((source/name).read_text(encoding='utf-8').splitlines(True),
            (target/name).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
    (target/'PRIVATE-DIFF.patch').write_text(''.join(changes),encoding='utf-8')
    (target/'SHA256.json').write_text(json.dumps(inventory(target),indent=2)+'\n',encoding='utf-8')
    (target/'NOT-PUBLISHED.txt').write_text('Prepared locally. Hatena save/staging/publication still requires separate explicit approval.\n',encoding='utf-8')
    return inventory(target)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','prepare']);parser.add_argument('source',type=Path)
    parser.add_argument('target',type=Path);parser.add_argument('--review',type=Path)
    a=parser.parse_args()
    if a.action=='prepare' and not a.review:parser.error('--review is required')
    try:
        result=backup(a.source,a.target) if a.action=='backup' else prepare(a.source,a.review,a.target)
    except (ValueError,OSError,UnicodeError,json.JSONDecodeError) as e:parser.exit(1,str(e)+'\n')
    print(json.dumps(result,indent=2))
