const globals = require('globals');
const reactHooks = require('eslint-plugin-react-hooks');

module.exports = [
{ ignores: ['**/*.test.js', '**/__tests__/**'] },
{
  files: ['src/**/*.{js,jsx}'],
  linterOptions: { reportUnusedDisableDirectives: false },
  languageOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    parserOptions: { ecmaFeatures: { jsx: true } },
    globals: { ...globals.browser, ...globals.node },
  },
  plugins: { 'react-hooks': reactHooks },
  rules: {
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'error',
  },
}];
