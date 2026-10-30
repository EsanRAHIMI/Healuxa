/**
 * Expo config plugin: configures Android release signing from environment variables or Gradle
 * properties, so the generated android/ project never contains key material.
 *
 * Provide (env or ~/.gradle/gradle.properties):
 *   HEALUXA_UPLOAD_STORE_FILE      absolute path to the upload keystore (.jks)
 *   HEALUXA_UPLOAD_STORE_PASSWORD
 *   HEALUXA_UPLOAD_KEY_ALIAS
 *   HEALUXA_UPLOAD_KEY_PASSWORD
 *
 * When they are absent, release builds fall back to the debug keystore and the build prints a
 * warning: such artifacts prove compilation only and must never be uploaded to Google Play.
 */
const { withAppBuildGradle } = require('expo/config-plugins');

const MARKER = '// @healuxa/release-signing';

const SIGNING_BLOCK = `
    ${MARKER}
    def healuxaProp = { String name ->
        def fromEnv = System.getenv(name)
        if (fromEnv != null && !fromEnv.isEmpty()) return fromEnv
        return project.hasProperty(name) ? project.property(name) : null
    }
    def healuxaStoreFile = healuxaProp('HEALUXA_UPLOAD_STORE_FILE')
    def healuxaHasUploadKey = healuxaStoreFile != null && file(healuxaStoreFile).exists()
    if (!healuxaHasUploadKey) {
        logger.warn("[healuxa] No upload keystore configured: release artifacts are debug-signed and NOT uploadable.")
    }
`;

function addSigning(contents) {
  if (contents.includes(MARKER)) return contents;
  // 1. helper block at the top of `android {`
  contents = contents.replace(/android\s*\{/, (m) => `${m}${SIGNING_BLOCK}`);
  // 2. a `release` signing config next to the template's debug one
  contents = contents.replace(
    /signingConfigs\s*\{\s*debug\s*\{[\s\S]*?\}\s*/,
    (m) =>
      `${m}release {
            if (healuxaHasUploadKey) {
                storeFile file(healuxaStoreFile)
                storePassword healuxaProp('HEALUXA_UPLOAD_STORE_PASSWORD')
                keyAlias healuxaProp('HEALUXA_UPLOAD_KEY_ALIAS')
                keyPassword healuxaProp('HEALUXA_UPLOAD_KEY_PASSWORD')
            }
        }
        `
  );
  // 3. release build type uses it when present
  contents = contents.replace(
    /(buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?)signingConfig\s+signingConfigs\.debug/,
    '$1signingConfig healuxaHasUploadKey ? signingConfigs.release : signingConfigs.debug'
  );
  return contents;
}

module.exports = function withAndroidReleaseSigning(config) {
  return withAppBuildGradle(config, (cfg) => {
    if (cfg.modResults.language !== 'groovy') {
      throw new Error('withAndroidReleaseSigning expects a Groovy app/build.gradle');
    }
    cfg.modResults.contents = addSigning(cfg.modResults.contents);
    return cfg;
  });
};

module.exports.addSigning = addSigning;
