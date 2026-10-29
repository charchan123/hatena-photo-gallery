"""Read-only public snapshots for local replay. Never accesses Hatena admin.
Usage: python tools/hatena_release_capture.py OUTPUT_DIR [PUBLISHED_DIR]
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests, json, hashlib, re, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit

ROOT=Path(sys.argv[1]).resolve(); ROOT.mkdir(parents=True,exist_ok=True)
CACHE=ROOT/'cache'; CACHE.mkdir(exist_ok=True)
BASE='https://exsudoporus-ruber.hatenablog.jp'
URLS={'home':BASE+'/', 'new-top':BASE+'/new-top',
 'article':BASE+'/entry/2026/09/25/225327',
 'field':BASE+'/archive/category/キノコ探索日記',
 'daily':BASE+'/archive/category/日常の記録',
 'about':BASE+'/entry/2025/03/22/032440', 'archive':BASE+'/archive',
 'feed':BASE+'/feed','rss':BASE+'/rss'}
def fetch(url):
 p=CACHE/hashlib.sha256(url.encode()).hexdigest()
 if p.exists() and p.with_suffix('.json').exists(): return json.loads(p.with_suffix('.json').read_text())
 r=requests.get(url,timeout=30);r.raise_for_status();p.write_bytes(r.content)
 info={'url':url,'final_url':r.url,'status':r.status_code,'file':p.name,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'type':r.headers.get('content-type','')}
 p.with_suffix('.json').write_text(json.dumps(info));return info
def page(item):
 name,url=item;info=fetch(url);raw=(CACHE/info['file']).read_text();s=BeautifulSoup(raw,'xml' if name in ['feed','rss'] else 'html.parser')
 info.update({'body_class':s.body.get('class',[]) if s.body else [],'canonical':str(s.select_one('link[rel=canonical]')),
 'article_urls':[a.get('href') for a in s.select('.entry-title-link')],
 'iframe':[dict(f.attrs) for f in s.select('iframe')],
 'native':{sel:len(s.select(sel)) for sel in ['article.entry','.hatena-star-container','.comment-box','.hatena-bookmark-button','.hatena-module','form[role=search]']}})
 (ROOT/(name+'.html')).write_text(raw)
 return name,info
with ThreadPoolExecutor(max_workers=4) as p: pages=dict(p.map(page,URLS.items()))
resources=set()
for name,info in pages.items():
 if name in ['feed','rss']:continue
 s=BeautifulSoup((ROOT/(name+'.html')).read_text(),'html.parser')
 for e in s.select('[style]'):
  resources.update(re.findall(r'https://cdn[^\s\"\'\)]+',e.get('style','')))
 for e in s.select('link[rel=stylesheet],script[src],img[src]'):
  u=urljoin(info['url'],e.get('href') or e.get('src'));resources.add(u)
for css in [Path('hatena/hatena-design-css-daily-archive-2026-10-11.css'), Path('hatena/release-2026-10-24/design.css')]:
 resources.update(re.findall(r'https://[^\s\"\)]+',css.read_text()))
if len(sys.argv)>2:
 childroot=Path(sys.argv[2])
 childpages=list(childroot.glob('best-shots*.html'))+[childroot/(n+'.html') for n in ['new-top','index','research','features','あ行','アイタケ']]
 for pagefile in childpages:
  s=BeautifulSoup(pagefile.read_text(),'html.parser')
  resources.update(i.get('src') or i.get('href') for i in s.select('img[src],script[src],link[rel=stylesheet]') if (i.get('src') or i.get('href','')).startswith('https://'))
allow=('usercss.blog.st-hatena.com','cdn.blog.st-hatena.com','cdn-ak.f.st-hatena.com','code.jquery.com','ajax.googleapis.com','charchan123.github.io','fonts.googleapis.com','fonts.gstatic.com','cdn.jsdelivr.net','unpkg.com')
def resource(u):
 try:return fetch(u)
 except Exception as e:return {'url':u,'error':type(e).__name__}
with ThreadPoolExecutor(max_workers=6) as p: results=list(p.map(resource,sorted(u for u in resources if urlsplit(u).hostname in allow)))
for i in list(results):
 if 'css' in i.get('type',''):
  text=(CACHE/i['file']).read_text()
  for u in re.findall(r'(?:url\([\"\']?|@import [\"\'])([^\"\'\)\s]+)',text):
   if not u.startswith('data:'):results.append(resource(urljoin(i.get('final_url',i['url']),u)))
(ROOT/'capture.json').write_text(json.dumps({'pages':pages,'resources':results},ensure_ascii=False,indent=2))
print(json.dumps({'pages':{k:{'status':v['status'],'bytes':v['bytes'],'body':v['body_class']} for k,v in pages.items()},'resources':len(results),'failures':[v for v in results if 'error'in v]},ensure_ascii=False))
