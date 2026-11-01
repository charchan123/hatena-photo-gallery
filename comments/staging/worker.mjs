// Separate entry: production never imports this module or its manifest policy.
import { createWorker } from "../worker.mjs";
import registry from "../cases.json" with { type: "json" };
import manifest from "./manifest.json" with { type: "json" };
import { createAccessVerifier } from "./access.mjs";
import { createRegistryChecker } from "./registry.mjs";
const headers = {
  "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
};
const error = (code, status) => Response.json({ error: code }, { status, headers });
const allowedAssets = new Map([
  ["/", "text/html; charset=utf-8"], ["/research.html", "text/html; charset=utf-8"],
  ["/assets/research-comments.js", "text/javascript; charset=utf-8"],
  ["/assets/research.css", "text/css; charset=utf-8"],
  ["/assets/staging.css", "text/css; charset=utf-8"],
  ["/assets/synthetic.svg", "image/svg+xml"],
]);
function settings(request, env) {
  const origin = env.STAGING_ORIGIN || "";
  // Deliberately no arbitrary custom/production origin or preview host support.
  if (env.ENVIRONMENT !== "staging" ||
      !/^https:\/\/kinoko-comments-staging-[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev$/.test(origin) ||
      new URL(request.url).origin !== origin ||
      env.ALLOWED_ORIGINS !== origin ||
      env.TURNSTILE_HOSTNAME !== new URL(origin).hostname ||
      env.MANIFEST_URL !== "staging:bundled" ||
      !/^[a-f0-9]{32}$/.test(env.STAGING_INSTALLATION_ID || "") ||
      !env.DB || env.REGISTRY_SHA256 !== manifest.registry_sha256)
    throw Error("STAGING_CONFIGURATION");
}
async function bounded(operation) {
  let timer;
  try {
    return await Promise.race([operation, new Promise((_,reject) => {
      timer=setTimeout(()=>reject(Error("STAGING_TIMEOUT")),3000);
    })]);
  } finally { clearTimeout(timer); }
}
export function createStagingWorker({ fetcher = globalThis.fetch, clock = () => Date.now() } = {}) {
  const verifyAccess = createAccessVerifier();
  const checkRegistry = createRegistryChecker(registry, manifest);
  const api = createWorker({ fetcher, clock, loadManifest: async () => manifest });
  return {
    async fetch(request, env) {
      try {
        settings(request, env);
        // JWT signature, team, audience and expiry are required for EVERY path,
        // including assets, OPTIONS, disabled flags and the local manifest.
        await verifyAccess(request, env);
      } catch {
        return error("STAGING_ACCESS_DENIED", 403);
      }
      try {
        await bounded(checkRegistry(env));
        const url = new URL(request.url);
        if (url.pathname.startsWith("/admin/") || url.pathname.startsWith("/v1/")) {
          const origin = request.headers.get("Origin");
          if (!url.pathname.startsWith("/admin/") && origin && origin !== env.STAGING_ORIGIN)
            return error("ORIGIN_FORBIDDEN", 403);
          return api.fetch(request, env);
        }
        if (request.method !== "GET" && request.method !== "HEAD") return error("NOT_FOUND",404);
        if (url.pathname === "/research-comment-cases.json") return Response.json(manifest,{headers});
        if (url.pathname === "/research-comments-config.json") {
          const enabled = env.RELEASE_APPROVAL === "approved" && env.PUBLIC_READ_ENABLED === "true" &&
            typeof env.TURNSTILE_SITE_KEY === "string" && !!env.TURNSTILE_SITE_KEY;
          return Response.json({version:1, enabled, api_url:env.STAGING_ORIGIN,
            transport:"access-same-origin", turnstile_site_key:env.TURNSTILE_SITE_KEY || "",
            release_approval:enabled ? "ISOLATED STAGING ONLY" : null},{headers});
        }
        if (!allowedAssets.has(url.pathname) || !env.ASSETS) return error("NOT_FOUND",404);
        // Worker-first routing plus an allowlist prevent serving unguarded uploads.
        const assetURL = new URL(url.pathname === "/" ? "/research.html" : url.pathname,url.origin);
        const asset = await bounded(env.ASSETS.fetch(new Request(assetURL,{method:request.method})));
        if (asset.status !== 200) return error("ASSET_UNAVAILABLE",503);
        const h = new Headers(headers);
        h.set("Content-Type",allowedAssets.get(url.pathname));
        h.set("Content-Security-Policy", "default-src 'none'; script-src 'self' https://challenges.cloudflare.com; style-src 'self'; img-src 'self'; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
        return new Response(asset.body,{headers:h});
      } catch {
        return error("STAGING_UNAVAILABLE",503);
      }
    },
  };
}
export default createStagingWorker();
