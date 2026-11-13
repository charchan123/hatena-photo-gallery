"""Offline-only synthetic staging UI. Never generate/publish production output."""
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research_comments import registry_digest, thread_mount

def build(target=None):
    target = Path(target) if target else Path(__file__).with_name('generated')
    registry = json.loads((ROOT/'comments/cases.json').read_text(encoding='utf-8'))
    manifest = json.loads(Path(__file__).with_name('manifest.json').read_text(encoding='utf-8'))
    if (manifest != {'version':1,'registry_sha256':registry_digest(registry),
                     'active_ids':sorted(r['id'] for r in registry['cases'])}):
        raise ValueError('staging frozen manifest requires explicit review')
    script = (ROOT/'assets/research-comments.js').read_text(encoding='utf-8')
    needle = 'credentials: "omit",'
    guard = 'const thread = details.dataset.researchThread,'
    if script.count(needle)!=1 or script.count(guard)!=1:
        raise ValueError('public transport changed; review staging transformation')
    script = script.replace(needle, 'credentials: "same-origin",\n            redirect: "error",')
    script = script.replace(guard, '''if (location.protocol !== "https:" || config.api_url !== location.origin ||
          config.transport !== "access-same-origin") {
        status.textContent = "隔離環境の接続設定が一致しません。接続を停止しました。";
        return;
      }
      const thread = details.dataset.researchThread,''')
    assets = target/'assets'; assets.mkdir(parents=True, exist_ok=True)
    (assets/'research-comments.js').write_text(script,encoding='utf-8')
    (assets/'research.css').write_bytes((ROOT/'assets/research.css').read_bytes())
    (assets/'staging.css').write_text('body{font-family:system-ui;background:#f7fcf4;color:#25412d;margin:0}main{max-width:1000px;margin:auto;padding:16px}.staging-cases{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.staging-case{min-width:0;background:white;border:1px solid #d5dfd0;border-radius:16px;padding:16px}.staging-case img{display:block;width:100%;height:auto}.staging-case small{overflow-wrap:anywhere}@media(max-width:680px){.staging-cases{grid-template-columns:1fr}}',encoding='utf-8')
    (assets/'synthetic.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300"><rect width="600" height="300" fill="#d4e3c4"/><text x="40" y="155" font-size="25">ISOLATED SYNTHETIC PHOTO</text></svg>',encoding='utf-8')
    cards = ''.join('<article class="staging-case"><h2>'+html.escape(r['label'])+'</h2><small>'+r['id']+'</small><img src="/assets/synthetic.svg" alt="検証用の合成画像">'+thread_mount(r['id'])+'</article>' for r in registry['cases'])
    (target/'research.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研究室コメント・隔離検証</title><link rel="stylesheet" href="/assets/research.css"><link rel="stylesheet" href="/assets/staging.css"><script src="/assets/research-comments.js" defer></script><main><h1>不明キノコ研究室・隔離検証</h1><p>検証専用です。写真とコメントは合成データ。本番ブログへの反映はありません。</p><div class="staging-cases">'+cards+'</div></main></html>',encoding='utf-8')
    files = {p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file() and p.name!='build-hashes.json'}
    (target/'build-hashes.json').write_text(json.dumps(files,indent=2)+'\n',encoding='utf-8')
    return target

if __name__=='__main__':
    build()
