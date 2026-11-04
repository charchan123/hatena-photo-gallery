"""Build an inert approval-gated Windows packet; no network or credentials."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def build(target):
    target = Path(target).resolve()
    if target.exists() or target.with_suffix('.zip').exists():
        raise ValueError('OUTPUT_EXISTS_DO_NOT_OVERWRITE')
    target.mkdir(parents=True)
    runner = ROOT/'comments/tools/origin-windows/runner.mjs'
    block = runner.read_text().split('export const FILES=[',1)[1].split('];',1)[0]
    names = re.findall(r"'([^']+)'", block)
    if len(names)!=12 or any('..' in n or not n.startswith('comments/') for n in names):
        raise ValueError('PACKAGE_FILE_LIST_INVALID')
    hashes = {}
    for name in names:
        data = (ROOT/name).read_bytes()
        dest = target/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest = {'protocol':'origin-windows-v1','source_head':head,
                'deployed_worker_source':'4fdb9bc70359c22f448cec02a864535984d41333',
                'files':dict(sorted(hashes.items()))}
    data = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    (target/'package-manifest.json').write_bytes(data)
    archive = target.with_suffix('.zip')
    # Stored entries avoid zlib-version differences across Windows/Ubuntu.
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED) as z:
        # WindowsPath comparison folds case; PosixPath comparison does not.
        # Sort the serialized ZIP entry names, not host-native Path objects.
        for p in sorted(target.rglob('*'), key=lambda p: p.relative_to(target).as_posix()):
            if p.is_file():
                info = zipfile.ZipInfo(p.relative_to(target).as_posix(),(1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_STORED)
    receipt = {'source_head':head,'files':len(names),'manifest_sha256':hashlib.sha256(data).hexdigest(),
               'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,
               'approval_granted':False,'deadline_set':False,'remote_requests':0}
    archive.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('target',help='New output directory; existing outputs are never overwritten')
    print(json.dumps(build(parser.parse_args().target)))
