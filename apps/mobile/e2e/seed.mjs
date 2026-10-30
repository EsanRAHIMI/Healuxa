#!/usr/bin/env node
/**
 * Seeds the LOCAL mobile E2E databases with synthetic (fictional) directory content through the real
 * identity-service and provider-service APIs. The only out-of-band step is granting the seeding
 * account the platform `admin` role in the local identity_mobile_e2e database, because identity has
 * no role-assignment endpoint. Refuses to run against anything other than localhost.
 *
 * Usage: node apps/mobile/e2e/seed.mjs
 */
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';

const IDENTITY = process.env.E2E_IDENTITY_URL ?? 'http://127.0.0.1:8201';
const PROVIDER = process.env.E2E_PROVIDER_URL ?? 'http://127.0.0.1:8205';
const PSQL = process.env.PSQL ?? '/opt/homebrew/opt/postgresql@16/bin/psql';
const IDENTITY_DB = 'identity_mobile_e2e';
// Local-only test password for synthetic seeding accounts (never used outside the e2e databases).
const SEED_PASSWORD = process.env.E2E_SEED_PASSWORD ?? 'seed-only-Local-e2e-2026';

for (const url of [IDENTITY, PROVIDER]) {
  const host = new URL(url).hostname;
  if (!['127.0.0.1', 'localhost'].includes(host)) {
    throw new Error(`Refusing to seed non-local backend ${url}`);
  }
}

async function call(base, method, path, { token, body, expect = [200, 201, 204] } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (method === 'POST' && path.endsWith('/register')) headers['Idempotency-Key'] = randomUUID();
  const res = await fetch(base + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  if (!expect.includes(res.status)) {
    const err = new Error(`${method} ${path} -> ${res.status}: ${text}`);
    err.status = res.status;
    throw err;
  }
  return json;
}

async function account(identifier) {
  try {
    return await call(IDENTITY, 'POST', '/v1/auth/register', {
      body: { identifier, password: SEED_PASSWORD, locale: 'en' },
      expect: [201],
    });
  } catch (e) {
    if (e.status !== 409) throw e;
    return call(IDENTITY, 'POST', '/v1/auth/login', { body: { identifier, password: SEED_PASSWORD } });
  }
}

const subOf = (jwt) => JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString()).sub;

async function main() {
  const existing = await call(PROVIDER, 'GET', '/v1/providers?limit=5');
  if (existing.data.length >= 2) {
    console.log(`already seeded (${existing.data.length} public providers)`);
    await ensureAvailability();
    return;
  }

  // Platform reviewer: grant the seeded `admin` role locally, then log in again for fresh claims.
  const adminId = subOf((await account('e2e-seed-admin@healuxa.test')).access_token);
  execFileSync(PSQL, ['-h', '127.0.0.1', '-U', 'healuxa', '-d', IDENTITY_DB, '-v', 'ON_ERROR_STOP=1', '-c',
    `INSERT INTO user_roles (user_id, role_id) SELECT '${adminId}', id FROM roles WHERE name='admin' AND tenant_id='healuxa-dubai' ON CONFLICT DO NOTHING;`],
    { env: { ...process.env, PGPASSWORD: process.env.PGPASSWORD ?? 'dev' }, stdio: 'ignore' });
  const admin = (await call(IDENTITY, 'POST', '/v1/auth/login', {
    body: { identifier: 'e2e-seed-admin@healuxa.test', password: SEED_PASSWORD },
  })).access_token;

  const facilityAdmin = (await account('e2e-seed-facility@healuxa.test')).access_token;
  const facility = await call(PROVIDER, 'POST', '/v1/facilities', {
    token: facilityAdmin,
    body: {
      type: 'medical_center',
      name: 'Marina Demo Medical Centre',
      description: { en: 'Fictional facility used for app testing.', ar: 'منشأة افتراضية لاختبار التطبيق.' },
      license_authority: 'dha',
      license_number: `DEMO-FAC-${Date.now()}`,
      website: 'https://example.com',
      phone: '+971 4 000 0000',
    },
  });
  await call(PROVIDER, 'POST', `/v1/facilities/${facility.id}/review`, { token: admin, body: { decision: 'verify' } });
  const branch = await call(PROVIDER, 'POST', `/v1/facilities/${facility.id}/branches`, {
    token: facilityAdmin,
    body: {
      name: 'Dubai Marina', address_line: 'Demo Street 1', city: 'Dubai', emirate: 'Dubai', country: 'AE',
      timezone: 'Asia/Dubai', latitude: 25.08, longitude: 55.14, phone: '+971 4 000 0001',
    },
  });
  await call(PROVIDER, 'PUT', `/v1/branches/${branch.id}/operating-hours`, {
    token: facilityAdmin,
    body: { windows: [0, 1, 2, 3, 4, 5].map((weekday) => ({ weekday, start: '09:00', end: '20:00' })) },
  });

  const practitioners = [
    {
      email: 'e2e-seed-dr-amal@healuxa.test',
      body: {
        type: 'doctor', display_name: 'Dr. Amal Demo', title: 'Consultant Dermatologist',
        bio: { en: 'Fictional dermatologist profile for testing.', ar: 'ملف طبيبة جلدية افتراضي للاختبار.', fa: 'پروفایل آزمایشی متخصص پوست.' },
        specialties: ['Dermatology'], languages: ['en', 'ar'],
      },
      services: [
        { category: 'dermatology', name: 'Dermatology consultation', duration_minutes: 30, price_type: 'fixed', professional_fee_minor: 45000, facility_fee_minor: 15000 },
        { category: 'aesthetics', name: 'Skin assessment', duration_minutes: 45, price_type: 'from', professional_fee_minor: 60000, facility_fee_minor: 20000 },
      ],
    },
    {
      email: 'e2e-seed-dr-reza@healuxa.test',
      body: {
        type: 'doctor', display_name: 'Dr. Reza Demo', title: 'Specialist Nutrition Physician',
        bio: { en: 'Fictional nutrition physician profile for testing.', fa: 'پروفایل آزمایشی پزشک تغذیه.' },
        specialties: ['Nutrition', 'Internal Medicine'], languages: ['en', 'fa'],
      },
      services: [
        { category: 'nutrition', name: 'Nutrition review', duration_minutes: 40, price_type: 'fixed', professional_fee_minor: 35000, facility_fee_minor: 10000 },
        { category: 'nutrition', name: 'Personalised plan', duration_minutes: 60, price_type: 'on_request' },
      ],
    },
  ];

  for (const p of practitioners) {
    const owner = (await account(p.email)).access_token;
    const provider = await call(PROVIDER, 'POST', '/v1/providers', { token: owner, body: p.body });
    const today = new Date();
    const iso = (d) => d.toISOString().slice(0, 10);
    const credential = await call(PROVIDER, 'POST', `/v1/providers/${provider.id}/credentials`, {
      token: owner,
      body: {
        kind: 'professional_license', issuing_authority: 'DHA', jurisdiction: 'AE-DU', number: `DEMO-${randomUUID().slice(0, 8)}`,
        valid_from: iso(new Date(today.getTime() - 30 * 864e5)), valid_until: iso(new Date(today.getTime() + 365 * 864e5)),
      },
    });
    await call(PROVIDER, 'POST', `/v1/providers/${provider.id}/credentials/${credential.id}/review`, { token: admin, body: { decision: 'verify' } });
    await call(PROVIDER, 'POST', `/v1/providers/${provider.id}/status`, { token: admin, body: { status: 'active', reason: 'credentials verified (e2e seed)' } });
    const affiliation = await call(PROVIDER, 'POST', '/v1/affiliations', { token: owner, body: { provider_id: provider.id, branch_id: branch.id } });
    await call(PROVIDER, 'POST', `/v1/affiliations/${affiliation.id}/decision`, { token: facilityAdmin, body: { decision: 'approve' } });
    for (const s of p.services) {
      const svc = await call(PROVIDER, 'POST', `/v1/providers/${provider.id}/services`, {
        token: owner,
        body: { branch_id: branch.id, mode: 'in_person', currency: 'AED', ...s },
      });
      if (svc.status !== 'active') {
        await call(PROVIDER, 'PATCH', `/v1/services/${svc.id}`, { token: owner, body: { status: 'active' } });
      }
    }
    console.log(`seeded provider ${provider.display_name} (${provider.id})`);
  }
  console.log(`seeded facility ${facility.name} (${facility.id})`);
  await ensureAvailability();
}

/** Weekly availability (Mon–Sat 09:00–17:00 branch time) so appointment-service can derive slots. */
async function ensureAvailability() {
  for (const email of ['e2e-seed-dr-amal@healuxa.test', 'e2e-seed-dr-reza@healuxa.test']) {
    const owner = (await account(email)).access_token;
    const me = await call(PROVIDER, 'GET', '/v1/providers/me', { token: owner });
    const rules = await call(PROVIDER, 'GET', `/v1/providers/${me.id}/availability-rules`, { token: owner });
    if (rules.data.length) continue;
    const services = await call(PROVIDER, 'GET', `/v1/services?provider_id=${me.id}`);
    const branchId = services.data[0]?.branch_id;
    if (!branchId) continue;
    const today = new Date().toISOString().slice(0, 10);
    for (const weekday of [0, 1, 2, 3, 4, 5]) {
      await call(PROVIDER, 'POST', `/v1/providers/${me.id}/availability-rules`, {
        token: owner,
        body: { branch_id: branchId, weekday, start: '09:00', end: '17:00', effective_from: today },
      });
    }
    console.log(`availability added for ${me.display_name}`);
  }
}

main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
