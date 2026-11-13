// Only bundled, immutable expectations are reused. Never cache a D1 result.
import { canonical, digest } from "../worker.mjs";

export function createRegistryChecker(registry, manifest) {
  // Private snapshots: callers cannot change the inputs after initialization.
  const registryText = canonical(registry);
  const frozenRegistry = JSON.parse(registryText);
  const frozenManifest = JSON.parse(canonical(manifest));
  let expected;
  async function initialize() {
    if (frozenManifest.version !== 1 ||
        await digest(registryText) !== frozenManifest.registry_sha256)
      throw Error("STAGING_REGISTRY_MISMATCH");
    const cases = await Promise.all(frozenRegistry.cases.map(async r => ({
      id: r.id,
      identity_hash: await digest(canonical([r.article_identity, [...r.observation_ids].sort()])),
    })));
    const aliases = frozenRegistry.cases.flatMap(r =>
      r.render_ids.map(alias => ({ alias, case_id: r.id })));
    if (canonical(frozenManifest.active_ids) !== canonical(cases.map(r => r.id).sort()))
      throw Error("STAGING_REGISTRY_MISMATCH");
    return Object.freeze({
      cases: canonical(cases.sort((a,b) => a.id.localeCompare(b.id))),
      aliases: canonical(aliases.sort((a,b) => a.alias.localeCompare(b.alias))),
    });
  }
  return async function checkRegistry(env) {
    // Lazy WebCrypto stays inside the request context, after JWT verification.
    // Concurrent first requests share initialization; a failure remains closed.
    expected ??= initialize();
    const fixed = await expected;
    const meta = (await env.DB.prepare("SELECT key,value FROM metadata").all()).results;
    const values = Object.fromEntries(meta.map(r => [r.key, r.value]));
    if (values.installation_id !== env.STAGING_INSTALLATION_ID ||
        values.schema_version !== "1" ||
        values.registry_sha256 !== frozenManifest.registry_sha256 ||
        env.REGISTRY_SHA256 !== frozenManifest.registry_sha256)
      throw Error("STAGING_REGISTRY_MISMATCH");
    // These three SELECTs and comparisons run on EVERY authenticated request.
    const cases = (await env.DB.prepare("SELECT id,identity_hash FROM cases ORDER BY id").all()).results;
    const aliases = (await env.DB.prepare("SELECT alias,case_id FROM aliases ORDER BY alias").all()).results;
    if (canonical(cases) !== fixed.cases || canonical(aliases) !== fixed.aliases)
      throw Error("STAGING_REGISTRY_MISMATCH");
  };
}
