// Read-only validation of supplied Access snapshots. No API client or mutation.
// Adapted from the Nov 1 recovery guard; no real identity/resource is embedded.
export function validateAccessSnapshot(app, policies, expected) {
  const stop = () => { throw Error("ACCESS_SNAPSHOT_UNSAFE"); };
  if (!expected.appId || !expected.workerTag || !expected.ownerPolicyId ||
      !expected.servicePolicyId || !expected.tokenId ||
      !/^[a-f0-9]{64}$/.test(expected.aud || "") ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(expected.ownerEmail || "")) stop();
  if (app.id !== expected.appId || app.type !== "self_hosted" || app.aud !== expected.aud ||
      app.domain || app.self_hosted_domains?.length ||
      app.options_preflight_bypass === true || app.read_service_tokens_from_header ||
      app.cors_headers && Object.values(app.cors_headers).some(v =>
        Array.isArray(v) ? v.length !== 0 : v !== false && v !== null && v !== "" && v !== 0)) stop();
  if (!Array.isArray(app.destinations) || app.destinations.length !== 1 ||
      app.destinations[0].type !== "worker" ||
      app.destinations[0].worker_id !== expected.workerTag ||
      Object.keys(app.destinations[0]).some(k => !["type","worker_id"].includes(k))) stop();
  if (!Array.isArray(policies) || policies.length !== 2) stop();
  const owner=policies.find(p=>p.id===expected.ownerPolicyId);
  const service=policies.find(p=>p.id===expected.servicePolicyId);
  const empty=p=>p && !p.require?.length && !p.exclude?.length;
  if (!empty(owner) || owner.decision!=="allow" || owner.session_duration!=="30m" ||
      owner.include?.length!==1 || Object.keys(owner.include[0]).join()!=="email" ||
      owner.include[0].email?.email!==expected.ownerEmail) stop();
  if (!empty(service) || service.decision!=="non_identity" || service.include?.length!==1 ||
      Object.keys(service.include[0]).join()!=="service_token" ||
      service.include[0].service_token?.token_id!==expected.tokenId) stop();
  return true;
}
