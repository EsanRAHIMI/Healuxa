// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['ios/*', 'android/*', 'dist/*', '.expo/*', 'artifacts/*', 'e2e/.logs/*'],
  },
  {
    rules: {
      // Tokens must never be stored outside expo-secure-store.
      'no-restricted-imports': [
        'error',
        {
          paths: [
            { name: '@react-native-async-storage/async-storage', message: 'Use src/auth/tokenStore (secure store) or src/storage/fileStore for public cache only.' },
          ],
        },
      ],
    },
  },
  {
    files: ['e2e/**/*.{js,mjs}', 'scripts/**/*.{js,mjs}', 'plugins/**/*.js', '*.config.js'],
    languageOptions: { globals: { Buffer: 'readonly', process: 'readonly', console: 'readonly', require: 'readonly', module: 'writable', __dirname: 'readonly', fetch: 'readonly', URL: 'readonly' } },
  },
  {
    files: ['e2e/**/*.{js,mjs,ts}', 'jest.setup.ts', '**/__tests__/**'],
    languageOptions: {
      globals: { describe: 'readonly', it: 'readonly', expect: 'readonly', beforeAll: 'readonly', afterAll: 'readonly', beforeEach: 'readonly', afterEach: 'readonly', jest: 'readonly', device: 'readonly', element: 'readonly', by: 'readonly', waitFor: 'readonly' },
    },
  },
]);
