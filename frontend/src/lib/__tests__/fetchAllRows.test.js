/**
 * "All" must mean all, or say that it does not.
 *
 * THE DEFECT THIS PINS (live in production until 2026-08-12):
 *   `ALL_ROWS` is the sentinel -1. Three screens passed it straight to the server
 *   as `limit`. Every list route clamps with some form of `max(1, min(limit, CAP))`,
 *   and `max(1, -1)` is 1 - so asking to see the whole school showed ONE ROW, with
 *   no error anywhere. A school of 1,876 children rendered as a school of one.
 *
 *   The test that matters most here is not "does it fetch everything". It is that a
 *   partial answer is never dressed up as a complete one: a mid-walk failure must
 *   fail, and hitting the ceiling must set `truncated`.
 */

import { fetchAllRows, ALL_ROWS_HARD_CAP } from '../fetchAllRows';

/** A fake endpoint holding `count` rows and clamping like the real ones do. */
function fakeEndpoint(count, { pageMax = 500, reportTotal = true } = {}) {
  const rows = Array.from({ length: count }, (_, i) => ({ id: `r${i}` }));
  const calls = [];
  const fetchPage = async ({ page, limit }) => {
    calls.push({ page, limit });
    // The clamp every real route applies. This is what turned -1 into 1.
    const perPage = Math.max(1, Math.min(limit, pageMax));
    const start = (page - 1) * perPage;
    return {
      success: true,
      data: rows.slice(start, start + perPage),
      meta: reportTotal ? { total: count } : {},
    };
  };
  return { fetchPage, calls };
}

test('collects every row across pages, and reports the true total', async () => {
  const { fetchPage, calls } = fakeEndpoint(1876);
  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.success).toBe(true);
  expect(res.data).toHaveLength(1876);
  expect(res.total).toBe(1876);
  expect(res.truncated).toBe(false);
  // 500 + 500 + 500 + 376: the fourth page is short, which is what stops the walk.
  expect(calls).toHaveLength(4);
  // The sentinel must never reach the server. This single assertion is the defect.
  expect(calls.every((c) => c.limit > 0)).toBe(true);
});

test('the notification route cap of 50 is walked, not assumed to be 500', async () => {
  const { fetchPage, calls } = fakeEndpoint(120, { pageMax: 50 });
  const res = await fetchAllRows(fetchPage, { pageMax: 50 });

  expect(res.data).toHaveLength(120);
  expect(calls).toHaveLength(3);
});

test('an exact multiple of the page size still terminates', async () => {
  // 1000 rows at 500 a page: no short page ever arrives, so the walk can only stop
  // on the reported total. Without that check this loops until the hard cap.
  const { fetchPage } = fakeEndpoint(1000, { pageMax: 500 });
  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.data).toHaveLength(1000);
  expect(res.truncated).toBe(false);
});

test('works when the server reports no total at all', async () => {
  const { fetchPage } = fakeEndpoint(640, { pageMax: 500, reportTotal: false });
  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.data).toHaveLength(640);
  // We walked to the end, so what we collected IS the total.
  expect(res.total).toBe(640);
});

test('an empty list is a success with zero rows, not a failure', async () => {
  const { fetchPage } = fakeEndpoint(0);
  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.success).toBe(true);
  expect(res.data).toEqual([]);
  expect(res.total).toBe(0);
});

test('hitting the ceiling sets truncated and still reports the real total', async () => {
  const { fetchPage } = fakeEndpoint(ALL_ROWS_HARD_CAP + 5000, { pageMax: 500 });
  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.truncated).toBe(true);
  expect(res.data).toHaveLength(ALL_ROWS_HARD_CAP);
  // The count must stay honest: "showing 25,000 of 30,000", never "of 25,000".
  expect(res.total).toBe(ALL_ROWS_HARD_CAP + 5000);
});

test('a failure part-way through fails, rather than returning half the school', async () => {
  let call = 0;
  const fetchPage = async ({ page }) => {
    call += 1;
    if (call === 3) return { success: false, detail: 'Server error' };
    return {
      success: true,
      data: Array.from({ length: 500 }, (_, i) => ({ id: `p${page}-${i}` })),
      meta: { total: 5000 },
    };
  };

  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.success).toBe(false);
  expect(res.detail).toBe('Server error');
  // 1,000 rows presented as the whole roll is the exact fault being prevented.
  expect(res.data).toEqual([]);
});

test('a thrown network error fails loudly rather than returning a short list', async () => {
  let call = 0;
  const fetchPage = async () => {
    call += 1;
    if (call === 2) throw new Error('Network down');
    return { success: true, data: Array.from({ length: 500 }, (_, i) => ({ id: i })), meta: { total: 5000 } };
  };

  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.success).toBe(false);
  expect(res.detail).toBe('Network down');
  expect(res.data).toEqual([]);
});

test('a server that over-reports its total cannot spin the walk forever', async () => {
  // The 2026-08-12 lesson: a wrong count must not become an infinite loop. The
  // server claims 9,000 rows and delivers 300, then nothing.
  let call = 0;
  const fetchPage = async () => {
    call += 1;
    return {
      success: true,
      data: call === 1 ? Array.from({ length: 300 }, (_, i) => ({ id: i })) : [],
      meta: { total: 9000 },
    };
  };

  const res = await fetchAllRows(fetchPage, { pageMax: 500 });

  expect(res.success).toBe(true);
  expect(res.data).toHaveLength(300);
  expect(call).toBe(1);
});
