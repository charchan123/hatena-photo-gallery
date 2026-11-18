// No identity/secret is logged or returned. Keys are fetched only from the pinned team.
import { createRemoteJWKSet, jwtVerify } from "jose";
export function createAccessVerifier() {
  const keys = new Map();
  return async function verify(request, env) {
    const issuer = env.ACCESS_TEAM_DOMAIN || "";
    const audience = env.ACCESS_AUD || "";
    if (!/^https:\/\/[a-z0-9][a-z0-9-]{0,62}\.cloudflareaccess\.com$/.test(issuer) ||
        !/^[a-f0-9]{64}$/.test(audience)) throw Error("ACCESS_CONFIGURATION");
    const token = request.headers.get("Cf-Access-Jwt-Assertion");
    if (!token || token.length > 16384) throw Error("ACCESS_REQUIRED");
    if (!keys.has(issuer)) {
      // One deployment uses one team. A changed config cannot grow this indefinitely.
      keys.clear();
      keys.set(issuer, createRemoteJWKSet(new URL(issuer + "/cdn-cgi/access/certs"), {
        timeoutDuration: 3000, cooldownDuration: 30000, cacheMaxAge: 300000,
      }));
    }
    const { payload } = await jwtVerify(token, keys.get(issuer), {
      issuer, audience, algorithms: ["RS256"],
      requiredClaims: ["exp", "iat", "iss", "aud"],
      clockTolerance: 0,
    });
    if (!Number.isFinite(payload.iat) || payload.iat > Date.now() / 1000) throw Error("ACCESS_TIME");
  };
}
