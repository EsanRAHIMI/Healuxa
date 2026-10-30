/**
 * Reads (does NOT verify) access-token claims for UI purposes only: the user id, the current
 * session id (to mark "this device" in the sessions list) and expiry. Authorization is always
 * decided by the backend through token introspection.
 */
export interface AccessClaims {
  sub?: string;
  session_id?: string;
  exp?: number;
  roles?: string[];
  perms?: string[];
}

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function base64UrlDecode(input: string): string {
  const b64 = input.replace(/-/g, '+').replace(/_/g, '/');
  const bytes: number[] = [];
  let buffer = 0;
  let bits = 0;
  for (const ch of b64) {
    if (ch === '=') break;
    const idx = ALPHABET.indexOf(ch);
    if (idx < 0) throw new Error('invalid base64');
    buffer = (buffer << 6) | idx;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((buffer >> bits) & 0xff);
    }
  }
  // UTF-8 decode
  let out = '';
  for (let i = 0; i < bytes.length; ) {
    const b = bytes[i]!;
    let cp: number;
    if (b < 0x80) {
      cp = b;
      i += 1;
    } else if (b < 0xe0) {
      cp = ((b & 0x1f) << 6) | (bytes[i + 1]! & 0x3f);
      i += 2;
    } else if (b < 0xf0) {
      cp = ((b & 0x0f) << 12) | ((bytes[i + 1]! & 0x3f) << 6) | (bytes[i + 2]! & 0x3f);
      i += 3;
    } else {
      cp =
        ((b & 0x07) << 18) | ((bytes[i + 1]! & 0x3f) << 12) | ((bytes[i + 2]! & 0x3f) << 6) | (bytes[i + 3]! & 0x3f);
      i += 4;
    }
    out += String.fromCodePoint(cp);
  }
  return out;
}

export function readClaims(token: string | undefined | null): AccessClaims {
  if (!token) return {};
  const part = token.split('.')[1];
  if (!part) return {};
  try {
    const parsed: unknown = JSON.parse(base64UrlDecode(part));
    return typeof parsed === 'object' && parsed !== null ? (parsed as AccessClaims) : {};
  } catch {
    return {};
  }
}
