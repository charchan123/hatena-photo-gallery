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
    u=urllib.parse.urlsplit(base)
    valid=(u.scheme=='https' and bool(u.hostname) and not u.username and not u.password
           and not u.query and not u.fragment and not u.path and len(secret)>=32)
    return base,secret,bool(valid)

def status():
    return {'configured':settings()[2], 'message':'コメント管理の接続設定が必要です。導入手順書を確認してください。' if not settings()[2] else 'コメント管理APIを設定済みです。'}

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
    if not configured:raise CommentsError('コメント管理は未設定です。環境変数を設定して管理室を再起動してください')
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
          headers={'Authorization':'Bearer '+secret,'Accept':'application/json',**({'Content-Type':'application/json'} if body is not None else {})})
    try:
        # Redirects never forward the credential. No remote URL comes from the UI.
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as response:
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:raise CommentsError('応答が大きすぎます。バックアップは未完了です')
            result=json.loads(raw)
    except urllib.error.HTTPError as error:
        codes={401:'管理者認証を確認してください',403:'アクセス権を確認してください',409:'対象コメントの状態または送信内容が変わりました。一覧を再取得して確認してください',429:'操作回数の上限です。時間をおいて再実行してください'}
        raise CommentsError(codes.get(error.code,'コメントAPIが利用できません。設定・APIの状態を確認してください')) from None
    except (OSError,ValueError) as error:
        if isinstance(error,CommentsError):raise
        raise CommentsError('コメントAPIに接続できませんでした。入力を保持しています。設定・通信状態を確認してください') from None
    if action=='backup':return verify_backup(result,secret)
    return result
