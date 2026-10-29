/**
 * Idempotency-Key helpers (shared components: 8–128 chars; same key + same body replays the original
 * response, same key + different body -> 409 idempotency_conflict).
 *
 * Generate ONE key per user intent (e.g. when a form is first rendered or submitted) and reuse it for
 * every retry of that intent. Never reuse a key for a different request body.
 */

function randomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c && typeof c.getRandomValues === "function") {
    c.getRandomValues(bytes);
    return bytes;
  }
  // React Native without a crypto polyfill: still unique enough for retry de-duplication, not for secrets.
  for (let i = 0; i < length; i++) bytes[i] = Math.floor(Math.random() * 256);
  return bytes;
}

/** RFC 4122 v4 UUID; uses crypto.randomUUID when present (browsers, Node 19+), else getRandomValues. */
export function newIdempotencyKey(prefix?: string): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  let uuid: string;
  if (c && typeof c.randomUUID === "function") {
    uuid = c.randomUUID();
  } else {
    const b = randomBytes(16);
    b[6] = (b[6]! & 0x0f) | 0x40;
    b[8] = (b[8]! & 0x3f) | 0x80;
    const hex = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
    uuid = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  const key = prefix ? `${prefix}-${uuid}` : uuid;
  if (key.length > 128) throw new RangeError("Idempotency key prefix too long (max 128 chars total)");
  return key;
}

const KEY_PATTERN = /^[A-Za-z0-9._:-]{8,128}$/;

export function isValidIdempotencyKey(key: string): boolean {
  return KEY_PATTERN.test(key);
}

/** Header object for openapi-fetch `params.header` / `headers`. Validates caller-supplied keys. */
export function idempotencyHeader(key: string = newIdempotencyKey()): { "Idempotency-Key": string } {
  if (!isValidIdempotencyKey(key)) throw new RangeError("Idempotency-Key must be 8–128 URL-safe characters");
  return { "Idempotency-Key": key };
}
