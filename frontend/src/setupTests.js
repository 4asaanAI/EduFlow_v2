import '@testing-library/jest-dom';

const { TextDecoder, TextEncoder } = require('util');

if (!global.TextDecoder) global.TextDecoder = TextDecoder;
if (!global.TextEncoder) global.TextEncoder = TextEncoder;
if (!global.crypto) global.crypto = {};
if (!global.crypto.randomUUID) {
  global.crypto.randomUUID = () => `test-${Math.random().toString(16).slice(2)}`;
}
