import test from "node:test";
import assert from "node:assert/strict";
import { validateAccessSnapshot } from "../staging/access-snapshot.mjs";

test("offline Access snapshot guard rejects broadened scope, owner, service and preflight settings",()=>{
  const e={appId:'synthetic-app',workerTag:'synthetic-worker-tag',aud:'a'.repeat(64),
    ownerPolicyId:'owner',servicePolicyId:'service',tokenId:'synthetic-token',ownerEmail:'owner@example.invalid'};
  const app={id:e.appId,type:'self_hosted',aud:e.aud,destinations:[{type:'worker',worker_id:e.workerTag}],options_preflight_bypass:false};
  const policies=[{id:'owner',decision:'allow',session_duration:'30m',include:[{email:{email:e.ownerEmail}}],require:[],exclude:[]},
    {id:'service',decision:'non_identity',include:[{service_token:{token_id:e.tokenId}}],require:[],exclude:[]}];
  assert.equal(validateAccessSnapshot(app,policies,e),true);
  assert.equal(validateAccessSnapshot({...app,cors_headers:{allow_all_origins:false,
    allowed_origins:[],allowed_methods:[],allowed_headers:[],allow_credentials:false}},policies,e),true);
  const mutations=[
    (a,p)=>a.options_preflight_bypass=true,
    (a,p)=>a.cors_headers={allowed_origins:['*']},
    (a,p)=>a.read_service_tokens_from_header='Authorization',
    (a,p)=>a.domain='*.workers.dev',
    (a,p)=>a.destinations[0].worker_id='another-worker',
    (a,p)=>a.destinations[0].path='/v1/*',
    (a,p)=>a.destinations.push({type:'worker',worker_id:'another-worker'}),
    (a,p)=>a.aud='b'.repeat(64),
    (a,p)=>p[0].include=[{everyone:{}}],
    (a,p)=>p[0].include=[{email_domain:{domain:'example.invalid'}}],
    (a,p)=>p[0].include=[{email:{email:'another@example.invalid'}}],
    (a,p)=>p[0].decision='bypass',
    (a,p)=>p[1].decision='allow',
    (a,p)=>p[1].include=[{service_token:{token_id:'another-token'}}],
    (a,p)=>p.push({id:'bypass',decision:'bypass',include:[{everyone:{}}]}),
  ];
  for(const mutate of mutations){const a=structuredClone(app),p=structuredClone(policies);mutate(a,p);
    assert.throws(()=>validateAccessSnapshot(a,p,e),/ACCESS_SNAPSHOT_UNSAFE/);}
});
