/**
 * Detox E2E config. The iOS app is a Release simulator build with the JS bundle embedded and
 * APP_ENV=e2e, which points at the native local backends (identity :8201, provider :8205).
 * See apps/mobile/README.md#e2e.
 */
const derivedData = process.env.DETOX_DERIVED_DATA ?? 'ios/build/detox';

/** @type {Detox.DetoxConfig} */
module.exports = {
  testRunner: {
    args: { $0: 'jest', config: 'e2e/jest.config.js' },
    jest: { setupTimeout: 240000 },
  },
  apps: {
    'ios.release': {
      type: 'ios.app',
      binaryPath: `${derivedData}/Build/Products/Release-iphonesimulator/Healuxa.app`,
      build:
        `xcodebuild -workspace ios/Healuxa.xcworkspace -scheme Healuxa -configuration Release -sdk iphonesimulator ` +
        `-destination 'generic/platform=iOS Simulator' -derivedDataPath ${derivedData} build`,
    },
  },
  devices: {
    simulator: {
      type: 'ios.simulator',
      device: { type: process.env.DETOX_DEVICE ?? 'iPhone 17' },
    },
  },
  configurations: {
    'ios.sim.release': { device: 'simulator', app: 'ios.release' },
  },
  artifacts: {
    rootDir: 'artifacts/detox',
    plugins: { screenshot: 'failing', log: 'failing' },
  },
};
