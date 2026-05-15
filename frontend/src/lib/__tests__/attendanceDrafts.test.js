import { purgeExpiredAttendanceDrafts } from '../attendanceDrafts';

beforeEach(() => {
  localStorage.clear();
  jest.spyOn(console, 'debug').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('purges attendance drafts older than seven days', () => {
  localStorage.setItem('attendance_draft_class-1_2026-05-01', 'old');
  localStorage.setItem('attendance_draft_class-2_2026-05-07', 'also-old');
  localStorage.setItem('attendance_draft_class-3_2026-05-12', 'recent');
  localStorage.setItem('other_key', 'keep');

  const purged = purgeExpiredAttendanceDrafts(new Date('2026-05-15T12:00:00'));

  expect(purged).toBe(2);
  expect(localStorage.getItem('attendance_draft_class-1_2026-05-01')).toBeNull();
  expect(localStorage.getItem('attendance_draft_class-2_2026-05-07')).toBeNull();
  expect(localStorage.getItem('attendance_draft_class-3_2026-05-12')).toBe('recent');
  expect(localStorage.getItem('other_key')).toBe('keep');
});
