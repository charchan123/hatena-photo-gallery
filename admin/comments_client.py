"""Local-only authenticated proxy. Never expose the service credential to JS."""
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 20 * 1024 * 1024
class CommentsError(ValueError):
    pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def settings():
    base=os.environ.get('KINOKO_COMMENTS_API_URL','').rstrip('/')
    secret=os.environ.get('KINOKO_COMMENTS_ADMIN_TOKEN','')
    try:
        u=urllib.parse.urlsplit(base)
        valid=(u.scheme=='https' and bool(u.hostname) and not u.username and not u.password
               and not u.query and not u.fragment and not u.path and u.port in {None,443}
               and bool(re.fullmatch(r'[!-~]{32,4096}',secret)))
    except ValueError:
        valid=False
    return base,secret,bool(valid)


def transport_settings(base):
    # Fixed, opt-in staging transport. Request/UI data can never select a target
    # or supply credentials. Direct production calls never receive Access keys.
    mode=os.environ.get('KINOKO_COMMENTS_TRANSPORT','direct')
    pinned=os.environ.get('KINOKO_COMMENTS_STAGING_ORIGIN','')
    client_id=os.environ.get('KINOKO_COMMENTS_ACCESS_CLIENT_ID','')
    client_secret=os.environ.get('KINOKO_COMMENTS_ACCESS_CLIENT_SECRET','')
    if mode=='direct':
        return {},not any((pinned,client_id,client_secret)),mode
    valid=(mode=='staging-access' and base==pinned
           and bool(re.fullmatch(r'https://kinoko-comments-staging-[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev',pinned))
           and bool(re.fullmatch(r'[A-Za-z0-9._-]{10,256}',client_id))
           and bool(re.fullmatch(r'[!-~]{32,4096}',client_secret)))
    return ({'CF-Access-Client-Id':client_id,'CF-Access-Client-Secret':client_secret} if valid else {}),bool(valid),mode

def status():
    base,_,valid=settings()
    _,transport_valid,mode=transport_settings(base)
    configured=valid and transport_valid
    return {'configured':configured, 'transport':mode if mode in {'direct','staging-access'} else 'invalid',
            'message':'コメント管理の接続設定が必要です。導入手順書を確認してください。' if not configured
            else ('隔離検証用Access接続を設定済みです。' if mode=='staging-access' else 'コメント管理APIを設定済みです。')}

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def verify_backup(value,secret):
    if not isinstance(value,dict) or set(value)!={'version','created_at','data','sha256','signature'} or value['version']!=1:
        raise CommentsError('バックアップの形式を確認できません。保存しませんでした')
    payload={k:value[k] for k in ('version','created_at','data')};raw=canonical(payload)
    if not hmac.compare_digest(str(value['sha256']),hashlib.sha256(raw).hexdigest()) or not hmac.compare_digest(str(value['signature']),hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()):
        raise CommentsError('バックアップの整合性・署名検証に失敗しました。保存しませんでした')
    return value

def request(action,values=None):
    values=values or {};base,secret,configured=settings()
    access_headers,transport_valid,mode=transport_settings(base)
    if not configured or not transport_valid:raise CommentsError('コメント管理は未設定です。環境変数を設定して管理室を再起動してください')
    if not isinstance(values,dict):raise CommentsError('コメント操作の入力が不正です')
    if action=='cases' and set(values)<= {'q'}:
        route='/admin/cases?'+urllib.parse.urlencode({'q':str(values.get('q',''))[:80]});body=None
    elif action=='comments' and set(values)<= {'case_id','after','unread'}:
        if not re.fullmatch(r'research-[0-9a-f]{16}',str(values.get('case_id',''))):raise CommentsError('研究ケースIDが不正です')
        route='/admin/comments?'+urllib.parse.urlencode(values);body=None
    elif action=='history' and set(values)=={'comment_id'}:
        route='/admin/history?'+urllib.parse.urlencode(values);body=None
    elif action=='action' and set(values)<= {'request_id','action','comment_id','body'}:
        if values.get('action') not in {'reply','hide','restore','review'}:raise CommentsError('許可されていないコメント操作です')
        route='/admin/action';body=canonical(values)
    elif action=='backup' and not values:
        route='/admin/backup';body=None
    else:raise CommentsError('許可されていないコメント操作です')
    req=urllib.request.Request(base+route,data=body,method='POST' if body is not None else 'GET',
          headers={**access_headers,'Authorization':'Bearer '+secret,'Accept':'application/json',**({'Content-Type':'application/json'} if body is not None else {})})
    try:
        # Redirects never forward the credential. No remote URL comes from the UI.
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as response:
            if mode=='staging-access' and (response.status!=200 or response.headers.get_content_type()!='application/json'):
                raise CommentsError('Access認証またはAPI応答を確認できません。Service Authポリシー・接続先を確認してください')
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:raise CommentsError('応答が大きすぎます。バックアップは未完了です')
            result=json.loads(raw)
    except urllib.error.HTTPError as error:
        codes={401:'管理者認証を確認してください',403:'アクセス権を確認してください',
               409:'対象コメントの状態または送信内容が変わりました。一覧を再取得して確認してください',
               429:'操作回数の上限です。時間をおいて再実行してください'}
        if mode=='staging-access':
            if error.code in {301,302,303,307,308}:
                raise CommentsError('Accessログイン画面への転送を拒否しました。Service Authポリシーと接続先を確認してください') from None
            codes.update({401:'管理者認証・AccessのService Auth設定を確認してください',
                          403:'アクセス権・AccessのService Auth設定を確認してください'})
        raise CommentsError(codes.get(error.code,'コメントAPIが利用できません。設定・APIの状態を確認してください')) from None
    except (OSError,ValueError) as error:
        if isinstance(error,CommentsError):raise
        raise CommentsError('コメントAPIに接続できませんでした。入力を保持しています。設定・通信状態を確認してください') from None
    if action=='backup':return verify_backup(result,secret)
    return result
