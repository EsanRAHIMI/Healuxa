/** CSP + random token helpers (edge/node safe, no server-only import: used by the proxy). */

function randomBase64Url(bytes: number): string {
  const buf = new Uint8Array(bytes);
  crypto.getRandomValues(buf);
  let bin = "";
  for (const b of buf) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function newNonce(): string {
  return randomBase64Url(18);
}

export function newCsrfToken(): string {
  return randomBase64Url(32);
}

/**
 * Strict, nonce-based CSP: scripts only from this origin with the per-request nonce
 * ('strict-dynamic' lets Next's nonce'd loader pull its chunks). The browser never talks to backend
 * services directly (connect-src 'self'): all API calls go through Server Components/Actions.
 */
export function buildCsp(nonce: string, { dev = false, https = false }: { dev?: boolean; https?: boolean } = {}): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...(dev ? ["'unsafe-eval'"] : [])],
    // Inline style attributes/elements (React style props, Radix scroll-lock) are allowed; no remote CSS.
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:"],
    "font-src": ["'self'"],
    "connect-src": ["'self'", ...(dev ? ["ws:", "wss:"] : [])],
    "manifest-src": ["'self'"],
    "worker-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    "frame-src": ["'none'"],
  };
  const parts = Object.entries(directives).map(([k, v]) => `${k} ${v.join(" ")}`);
  if (https) parts.push("upgrade-insecure-requests");
  return parts.join("; ");
}
