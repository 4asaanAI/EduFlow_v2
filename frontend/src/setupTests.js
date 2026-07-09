import '@testing-library/jest-dom';

const { TextDecoder, TextEncoder } = require('util');

if (!global.TextDecoder) global.TextDecoder = TextDecoder;
if (!global.TextEncoder) global.TextEncoder = TextEncoder;
if (!global.crypto) global.crypto = {};
if (!global.crypto.randomUUID) {
  global.crypto.randomUUID = () => `test-${Math.random().toString(16).slice(2)}`;
}

// jsdom does not implement scrollIntoView; ChatInterface (and Layout, which
// embeds it) call it in an effect, which otherwise throws during render in tests.
if (typeof window !== 'undefined' && window.HTMLElement && !window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = function () {};
}
