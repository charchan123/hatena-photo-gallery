"""Real Chromium over public snapshots + the unchanged published child pages.

Only intercepted GETs are served. No Hatena editor, Cloudflare, comments or stars
are written. This is LOCAL REPLAY, never an authenticated Hatena Staging result.
Usage: python tools/hatena_release_browser.py CAPTURE_DIR PUBLISHED_DIR EVIDENCE_DIR
"""
from pathlib import Path
from urllib.parse import urlsplit, unquote, urljoin
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, os, re, sys, requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

capture, published, evidence = map(lambda p:Path(p).resolve(),sys.argv[1:4])
evidence.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
release=root/'hatena/release-2026-10-24'
data=json.loads((capture/'capture.json').read_text())
cache=capture/'cache'
resources={x['url']:x for x in data['resources'] if 'file'in x}
pages={urlsplit(v['final_url']).path:k for k,v in data['pages'].items() if k not in ['feed','rss']}
allowed={'cdn-ak.f.st-hatena.com','cdn.image.st-hatena.com','usercss.blog.st-hatena.com',
 'cdn.blog.st-hatena.com','fonts.googleapis.com','fonts.gstatic.com','code.jquery.com','ajax.googleapis.com','cdn.jsdelivr.net','unpkg.com'}
results=[]; blocked=[]; counts={'checks':0}
def check(value, label):
    counts['checks']+=1
    if not value:raise AssertionError(label)

def prepared(name, variant, marker=True, body_scroll=False):
    s=BeautifulSoup((capture/(name+'.html')).read_text(),'html.parser')
    # Preserve native content and controls. Suppress third-party tracking/native
    # account actions in both replay variants, not in the release payload.
    for t in s.select('script'):
        if t.get('src'):
            if 'jquery' not in t['src'].lower():t.decompose()
        elif not any(x in t.text for x in ['menu-btn','page_top','photoGallery']):t.decompose()
    if variant=='after':
        for link in s.select('link[rel=stylesheet]'):
            if '/blog_style/' in link.get('href',''):
                style=s.new_tag('style');style.string=(release/'design.css').read_text();link.replace_with(style)
        scripts=[t for t in s.select('script:not([src])') if 'photoGallery'in t.text and 'navigationIntentAck'in t.text]
        check(len(scripts)==1,'exactly one observed communication block')
        scripts[0].replace_with(BeautifulSoup((release/'footer-managed.html').read_text(),'html.parser'))
        if marker:
            s.select_one('#top-editarea').append(BeautifulSoup((release/'header-activation.html').read_text(),'html.parser'))
    if body_scroll:
        style=s.new_tag('style');style.string='html{height:100vh!important;overflow:hidden!important}body{position:relative!important;margin-top:56px!important;height:calc(100vh - 56px)!important;overflow-y:auto!important}'
        s.head.append(style)
    return str(s)

def resource(url):
    if url in resources:return resources[url]
    key=hashlib.sha256(url.encode()).hexdigest();f=cache/key
    if f.exists() and f.with_suffix('.json').exists():return json.loads(f.with_suffix('.json').read_text())
    r=requests.get(url,timeout=20);r.raise_for_status();f.write_bytes(r.content)
    info={'url':url,'file':key,'type':r.headers.get('content-type','application/octet-stream')}
    f.with_suffix('.json').write_text(json.dumps(info));resources[url]=info;return info

def route_for(variant, marker=True, body_scroll=False):
    def route(route):
        req=route.request;u=urlsplit(req.url)
        if req.method!='GET':blocked.append({'method':req.method,'host':u.hostname});route.abort();return
        if u.hostname=='exsudoporus-ruber.hatenablog.jp':
            key=pages.get(unquote(u.path)) or pages.get(u.path)
            if key:route.fulfill(status=200,content_type='text/html',body=prepared(key,variant,marker,body_scroll));return
        if u.hostname=='charchan123.github.io' and u.path.startswith('/hatena-photo-gallery/'):
            rel=unquote(u.path.removeprefix('/hatena-photo-gallery/'));p=published/(rel or 'index.html')
            if p.is_file() and p.resolve().is_relative_to(published):
                import mimetypes
                route.fulfill(status=200,content_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream',body=p.read_bytes());return
        if u.hostname in allowed:
            try:
                info=resource(req.url);route.fulfill(status=200,content_type=info['type'],body=(cache/info['file']).read_bytes());return
            except Exception:pass
        # External social/ads/analytics are not part of an offline acceptance test.
        route.fulfill(status=404,body='isolated replay: external service unavailable')
    return route

def measure(page):
    return page.evaluate('''() => ({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth+1,
      canonical:document.querySelector('link[rel=canonical]')?.href,
      native:Object.fromEntries(['article.entry','.hatena-star-container','.comment-box','.hatena-bookmark-button','.hatena-module'].map(s=>[s,document.querySelectorAll(s).length])),
      links:[...document.querySelectorAll('#content a')].map(a=>a.getAttribute('href')),
      forms:[...document.querySelectorAll('#content form')].map(f=>[f.getAttribute('action'),f.getAttribute('method')]),
      feeds:[...document.querySelectorAll('link[type*="xml"]')].map(l=>l.href),
      title:document.title,og:[...document.querySelectorAll('meta[property^="og:"]')].map(m=>[m.getAttribute('property'),m.content]),
      root:!!document.querySelector('#kinoko-home-portal'),iframeCount:document.querySelectorAll('#photoGallery').length})''')

def compact(measurement):
    # Full native href arrays are compared above before storing this digest.
    value=dict(measurement);links=value.pop('links')
    value['native_link_count']=len(links)
    value['native_links_sha256']=hashlib.sha256(json.dumps(links,ensure_ascii=False).encode()).hexdigest()
    return value

with sync_playwright() as pw:
    launch={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
    if os.getenv('HATENA_CHROMIUM'):launch['executable_path']=os.environ['HATENA_CHROMIUM']
    browser=pw.chromium.launch(**launch)
    for width in [320,360,390,430,768,900,1280,1440]:
        for name in ['home','new-top','article','field','daily','about','archive']:
            variants={}
            for variant in ['before','after']:
                context=browser.new_context(viewport={'width':width,'height':960},device_scale_factor=1)
                context.route('**/*',route_for(variant));page=context.new_page()
                page.goto(data['pages'][name]['url'],wait_until='load',timeout=90000)
                if name in ['home','new-top'] and variant=='after':
                    page.wait_for_function("document.querySelector('#photoGallery')?.style.height.endsWith('px')",timeout=15000)
                page.wait_for_timeout(250)
                m=measure(page);variants[variant]=m
                frames=[f for f in page.frames if f.url.startswith('https://charchan123.github.io/hatena-photo-gallery/new-top.html')]
                if frames:
                    portal=frames[0].evaluate('''() => ({width:innerWidth,
                      panels:[...document.querySelectorAll('.portal-records-hero,.portal-explore')].map(e=>e.getBoundingClientRect().height),
                      left:[...document.querySelectorAll('.record-preview-thumb')].map(e=>e.getBoundingClientRect().height),
                      right:[...document.querySelectorAll('.portal-guide-row .portal-card')].map(e=>e.getBoundingClientRect().height)})''')
                    m['portal']=portal
                    check(len(portal['left'])==3 and len(portal['right'])==3,'six portal image mounts')
                    for heights in [portal['left'],portal['right']]:check(max(heights)-min(heights)<1,'equal heights within each thumbnail column')
                    if portal['width']>=900:check(abs(portal['panels'][0]-portal['panels'][1])<1,'desktop equal portal panels')
                    if name=='home' and variant=='after':check(portal['width']==width,'root iframe retains viewport breakpoints')
                check(not m['overflow'],f'{name} {variant} {width}: horizontal overflow')
                if variant=='after':
                    check(m['native']==variants['before']['native'],f'{name}: native controls')
                    for key in ['canonical','title','og','feeds','links','forms']:
                        check(m[key]==variants['before'][key],f'{name}: unchanged {key}')
                    check(m['root']==(name=='home'),f'{name}: exact root activation')
                    check(m['iframeCount']==(1 if name in ['home','new-top'] else 0),f'{name}: no duplicate frame')
                    if width<=900 and name in ['article','field','daily','home']:
                        btn=page.locator('#menu-btn');btn.click();page.wait_for_timeout(450)
                        check(page.locator('#menu-content a').first.is_visible(),f'{name}: menu open')
                        btn.click();page.wait_for_timeout(450)
                        check(not page.locator('#menu-content a').first.is_visible(),f'{name}: menu closes after animation')
                page.screenshot(path=str(evidence/f'{name}-{width}-{variant}.jpg'),type='jpeg',quality=65)
                context.close()
            results.append({'page':name,'width':width,'before':compact(variants['before']),'after':compact(variants['after'])})
            (evidence/'progress.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    # Query bypass, missing activation, and all non-root pages keep native markup.
    for path,marker in [('/',False),('/?kinoko-native=1',True),('/?page=2',True)]:
        c=browser.new_context();c.route('**/*',route_for('after',marker));p=c.new_page();p.goto('https://exsudoporus-ruber.hatenablog.jp'+path)
        check(p.locator('#kinoko-home-portal').count()==0,'activation is opt-in and root/query guarded');c.close()
    # Parent protocol: real distinct origins, both scroll hosts. Real published
    # child links, filter and details actions exercise the existing ACK protocol.
    protocol=[]
    for parent,mode in [('home','window'),('home','body'),('new-top','window'),('new-top','body')]:
        print('Protocol:',parent,mode,flush=True)
        steps=[]
        c=browser.new_context(viewport={'width':390,'height':900});c.route('**/*',route_for('after',body_scroll=mode=='body'))
        p=c.new_page();p.goto(data['pages'][parent]['url']);p.wait_for_function("parseFloat(document.querySelector('#photoGallery').style.height)>600")
        f=next(f for f in p.frames if f.url.startswith('https://charchan123.github.io/'))
        # Invalid source and origins cannot change iframe height or parent scroll.
        old=p.locator('#photoGallery').get_attribute('style')
        p.evaluate("window.postMessage({type:'setHeight',height:999999},location.origin)")
        p.wait_for_timeout(100);check(p.locator('#photoGallery').get_attribute('style')==old,'invalid source/origin ignored')
        for target in ['features.html','index.html','season.html','index.html','best-shots.html','index.html','research.html','index.html','あ行.html','アイタケ.html']:
            print('Navigate:',target,flush=True)
            # A user activation in the real child, not a fabricated parent ACK.
            hrefs=f.locator('a[href]').evaluate_all('(links)=>links.map(a=>a.getAttribute("href"))')
            matches=[h for h in hrefs if unquote(urlsplit(h).path).split('/')[-1]==target]
            check(bool(matches),'published navigation link '+target)
            link=f.locator('a[href='+json.dumps(matches[-1],ensure_ascii=False)+']').last
            p.evaluate('(mode)=>{const e=mode==="body"?document.body:document.scrollingElement;e.scrollTop=e.scrollHeight}',mode)
            link.click();p.wait_for_timeout(350);f=next(f for f in p.frames if f.url.startswith('https://charchan123.github.io/'))
            check(unquote(f.url.split('?')[0]).endswith('/'+target),'actual child navigation '+target)
            p.wait_for_function("parseFloat(document.querySelector('#photoGallery').style.height)>0")
            check(p.evaluate("document.getElementById('photoGallery').getBoundingClientRect().top")>=-3,'navigation reaches frame top '+mode)
            check(not p.evaluate("document.documentElement.scrollWidth>innerWidth+1"),'parent overflow '+mode)
            steps.append({'target':target,**p.locator('#photoGallery').evaluate('(e)=>({frame_height:e.offsetHeight,frame_top:e.getBoundingClientRect().top,reserved_min_height:e.closest(".new-top-embed, #galleryWrapper")?.style.minHeight})')})
            if target=='features.html':
                initial=float(p.locator('#photoGallery').evaluate('(e)=>e.offsetHeight'))
                f.locator('.feature-filter').first.click();p.wait_for_timeout(700)
                check(float(p.locator('#photoGallery').evaluate('(e)=>e.offsetHeight'))<initial,'filter shrinks parent height')
                f.locator('.feature-clear').click();p.wait_for_timeout(700)
                check(abs(float(p.locator('#photoGallery').evaluate('(e)=>e.offsetHeight'))-initial)<20,'clear grows parent height')
            if target=='index.html':
                search=f.locator('.index-search-input');search.fill('アイタケ');p.wait_for_timeout(300)
                check(f.locator('.index-search-input').input_value()=='アイタケ','live index search');search.fill('');p.wait_for_timeout(300)
            if target=='research.html':
                f.locator('details').first.locator('summary').click();p.wait_for_timeout(300)
                check(f.locator('details').first.get_attribute('open') is not None,'research details open')
                f.locator('details').first.locator('summary').click()
            if target=='アイタケ.html':
                f.locator('details').first.locator('summary').click();p.wait_for_timeout(300)
                check(f.locator('details').first.get_attribute('open') is not None,'subject references open')
                f.locator('details').first.locator('summary').click()
                f.locator('a.gallery-item').first.click()
                f.locator('.lg-outer.lg-visible').wait_for()
                check(f.locator('.lg-current img.lg-object').count()>0,'photograph enlarged')
                f.locator('.lg-close').click();p.wait_for_timeout(600)
                check(f.locator('.lg-outer.lg-visible').count()==0,'photograph closed')
        p.set_viewport_size({'width':900,'height':390});p.wait_for_timeout(700)
        check(not p.evaluate('document.documentElement.scrollWidth>innerWidth+1'),'rotation overflow')
        # Browser history traverses the actual iframe session history.
        p.evaluate('history.back()')
        f.wait_for_url(lambda u:unquote(urlsplit(str(u)).path).endswith('/あ行.html'))
        p.evaluate('history.forward()')
        f.wait_for_url(lambda u:unquote(urlsplit(str(u)).path).endswith('/アイタケ.html'))
        check(any('アイタケ' in unquote(x.url) for x in p.frames),'child back/forward history')
        protocol.append({'parent':parent,'scroll_host':mode,'navigation_filter_search_details_rotation_history':'PASS','steps':steps})
        c.close()
    # Published responsive pages, unchanged generated bytes; collect screenshots.
    for name in ['index.html','best-shots.html','best-shots-2025.html','best-shots-2026.html','research.html','features.html']:
        for width in [320,360,390,430,768,900,1280,1440]:
            c=browser.new_context(viewport={'width':width,'height':960});c.route('**/*',route_for('after'));p=c.new_page();p.goto('https://charchan123.github.io/hatena-photo-gallery/'+name,wait_until='load')
            p.wait_for_function('''[...document.querySelectorAll('main img')].filter(e=>{
              const r=e.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;
            }).every(e=>e.complete&&e.naturalWidth>0)''')
            check(not p.evaluate("document.documentElement.scrollWidth>innerWidth+1"),name+str(width))
            if name.startswith('best-shots'):
                mounts=p.locator('.best-shot-grid .best-shot-photo').evaluate_all('els=>els.map(e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,ratio:getComputedStyle(e).aspectRatio,fit:getComputedStyle(e.querySelector("img")).objectFit}})')
                for mount in mounts:
                    check(mount['fit']=='contain','Best Shot whole photograph retained')
                    if width>680:check(abs(mount['width']/mount['height']-4/3)<.01,'Best Shot desktop shared 4:3 mount')
                    else:check(mount['ratio']=='auto','Best Shot mobile intrinsic ratio')
                if width>680:
                    for grid in p.locator('.best-shot-grid').all():
                        titles=grid.locator('.best-shot-card__body h3')
                        if titles.count()>1:
                            check(abs(titles.nth(0).bounding_box()['y']-titles.nth(1).bounding_box()['y'])<1,'Best Shot first-row captions aligned')
            p.screenshot(path=str(evidence/f'child-{name[:-5]}-{width}.jpg'),type='jpeg',quality=65);c.close()
    check(not blocked,'no external mutation attempted')
    browser.close()
(evidence/'results.json').write_text(json.dumps({'kind':'LOCAL_REPLAY_NOT_HATENA_STAGING','browser':browser.version,'checks':counts['checks'],'widths':[320,360,390,430,768,900,1280,1440],'rows':results,'protocol':protocol,'blocked_mutations':blocked},ensure_ascii=False,indent=2))
print('PASS:',counts['checks'],'real Chromium release checks; no external writes')
