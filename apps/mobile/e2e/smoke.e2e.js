/* eslint-env detox/detox, jest */
/**
 * Smoke test against the REAL local backends (scripts/e2e-backends.sh + e2e/seed.mjs):
 * launch → browse directory → open provider → register → sign out → sign in → sign out.
 * Creates one synthetic account per run (e2e-<timestamp>@healuxa.test) in identity_mobile_e2e.
 */
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const email = `e2e-${Date.now()}@healuxa.test`;
const password = `Local-e2e-${Date.now()}`;
const SHOTS = process.env.E2E_SCREENSHOT_DIR;

async function shot(name) {
  if (!SHOTS) return;
  const file = await device.takeScreenshot(name);
  execFileSync('cp', [file, path.join(SHOTS, `${name}.png`)]);
}

async function visible(matcher, timeout = 20000) {
  await waitFor(element(matcher)).toBeVisible().withTimeout(timeout);
}

describe('Healuxa smoke', () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true, delete: true, permissions: { notifications: 'NO' } });
  });

  it('shows the welcome screen on first launch', async () => {
    await visible(by.id('welcome-screen'));
    await shot('01-welcome');
  });

  it('browses the public directory', async () => {
    await element(by.id('welcome-browse')).tap();
    await visible(by.id('directory-screen'));
    await visible(by.text('Dr. Amal Demo'));
    await shot('02-directory');
  });

  it('opens a provider profile with verified credentials and fee breakdown', async () => {
    await element(by.text('Dr. Amal Demo')).tap();
    await visible(by.id('provider-name'));
    await expect(element(by.id('provider-name'))).toHaveText('Dr. Amal Demo');
    await visible(by.id('provider-credentials'));
    await shot('03-provider-profile');
    await element(by.id('provider-screen')).scrollTo('bottom');
    await visible(by.text('Professional fee').withAncestor(by.id('provider-offerings')));
    await shot('04-provider-fees');
  });

  it('opens the facility page', async () => {
    await element(by.id('provider-screen')).scrollTo('top');
    await element(by.id('provider-screen')).scroll(400, 'down');
    await element(by.text('Marina Demo Medical Centre')).tap();
    await visible(by.id('facility-name'));
    await shot('05-facility');
  });

  it('registers a new account', async () => {
    await device.launchApp({ newInstance: true });
    await element(by.id('tab-account')).tap();
    await visible(by.id('account-register'));
    await element(by.id('account-register')).tap();
    await visible(by.id('register-identifier'));
    await element(by.id('register-identifier')).typeText(email);
    await element(by.id('register-password')).typeText(password);
    await shot('06-register');
    await element(by.id('register-submit')).tap();
    await visible(by.id('account-identity'));
    await expect(element(by.id('account-identifier'))).toHaveText(email);
    await shot('07-account');
  });

  it('lists sessions including this device', async () => {
    await element(by.id('account-sessions')).tap();
    await visible(by.id('session-current'));
    await shot('08-sessions');
    await device.launchApp({ newInstance: true });
    await element(by.id('tab-account')).tap();
  });

  it('signs out', async () => {
    await visible(by.id('account-sign-out'));
    await element(by.id('account-sign-out')).tap();
    await visible(by.id('account-sign-in'));
  });

  it('signs in with the new account and signs out again', async () => {
    await element(by.id('account-sign-in')).tap();
    await visible(by.id('sign-in-identifier'));
    await element(by.id('sign-in-identifier')).typeText(email);
    await element(by.id('sign-in-password')).typeText(password);
    await element(by.id('sign-in-submit')).tap();
    await visible(by.id('account-identity'));
    await expect(element(by.id('account-identifier'))).toHaveText(email);
    await element(by.id('account-sign-out')).tap();
    await visible(by.id('account-sign-in'));
  });

  it('rejects a wrong password with a clear message', async () => {
    await element(by.id('account-sign-in')).tap();
    await element(by.id('sign-in-identifier')).typeText(email);
    await element(by.id('sign-in-password')).typeText('definitely-wrong');
    await element(by.id('sign-in-submit')).tap();
    await visible(by.id('sign-in-form-error'));
    await shot('09-sign-in-error');
  });
});
