// Read-only receipt for an ALREADY deployed, closed Worker. Never deploys or enables URLs.
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
const hash=b=>createHash('sha256').update(b).digest('hex');
const need=(ok,why)=>{if(!ok)throw Error(why);};
const pin='0f363c931bd791aaa92b1b89d513fa4709b0ce5504ab5c1c206043c6d847d68a';
export function deployedVersion(d){
  const v=d?.deployments?.[0]?.versions;
  need(v?.length===1&&v[0].percentage===100&&/^6ff1d822-[a-f0-9-]{27}$/.test(v[0].version_id),'ACTIVE_VERSION_MISMATCH');
  return v[0].version_id;
}
export async function codeReceipt(r){
  need(r.ok,'CONTENT_HTTP_'+r.status);
  const type=r.headers.get('content-type')||'';
  let b,modules=1;
  if(type.startsWith('multipart/')){
    const entries=[...(await r.formData()).entries()];
    const js=entries.filter(([name])=>/\.(?:js|mjs)$/.test(name));
    need(js.length===1,'CONTENT_MODULE_COUNT_MISMATCH');
    const entry=r.headers.get('cf-entrypoint');
    need(!entry||entry===js[0][0],'CONTENT_ENTRYPOINT_MISMATCH');
    modules=js.length;
    b=typeof js[0][1]==='string'?Buffer.from(js[0][1]):Buffer.from(await js[0][1].arrayBuffer());
  }else b=Buffer.from(await r.arrayBuffer());
  const digest=hash(b);need(digest===pin,'DEPLOYED_CODE_SHA_MISMATCH');
  return {compiled_sha256:digest,javascript_modules:modules};
}
