/**
 * NEW-11 - the fee-discount approval address the app uses must be one the server serves.
 *
 * `lib/api.js` used to export `approveFeeDiscount` / `rejectFeeDiscount`, which called
 * POST /api/fees/discounts/{id}/approve|reject. The server has only ever served
 * PATCH /api/fees/discounts/pending-approvals/{approval_id}/approve|reject - wrong path
 * AND wrong method. Nothing called them, so nothing broke; they were leftovers that
 * looked ready to use and would have 404'd the first time anyone reached for them.
 *
 * These are the ONLY two mismatches the full client-to-server audit found (192 client
 * paths against 274 server routes), so this guards the exact hole rather than the class.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', '..');
const apiSource = fs.readFileSync(path.join(SRC, 'lib', 'api.js'), 'utf8');
const feeScreen = fs.readFileSync(
  path.join(SRC, 'components', 'tools', 'FeeCollection.js'),
  'utf8'
);

test('the deleted helpers are not exported again', () => {
  expect(apiSource).not.toMatch(/export\s+async\s+function\s+approveFeeDiscount/);
  expect(apiSource).not.toMatch(/export\s+async\s+function\s+rejectFeeDiscount/);
});

test('nothing addresses a discount approval without the pending-approvals segment', () => {
  // `/fees/discounts/<something>/approve` is only correct via `pending-approvals/{id}`.
  const wrong = /fees\/discounts\/\$\{[^}]+\}\/(approve|reject)/;
  expect(apiSource).not.toMatch(wrong);
  expect(feeScreen).not.toMatch(wrong);
});

test('the Fee Collection screen uses the address the server actually serves', () => {
  expect(feeScreen).toMatch(/fees\/discounts\/pending-approvals\/\$\{[^}]+\}\/approve/);
  expect(feeScreen).toMatch(/fees\/discounts\/pending-approvals\/\$\{[^}]+\}\/reject/);
  // The server routes are PATCH, not POST. Matched by pattern rather than by a
  // hardcoded `${id}`, so renaming the local variable does not fail this for the
  // wrong reason.
  const approve = feeScreen.match(
    /pending-approvals\/\$\{[^}]+\}\/approve[\s\S]{0,200}/
  );
  expect(approve).not.toBeNull();
  expect(approve[0]).toMatch(/method:\s*'PATCH'/);
});
