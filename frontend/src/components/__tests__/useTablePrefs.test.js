/**
 * Rows-per-page preference — Epic 3, Story 3.2 (UX-DR10).
 *
 * The point of most of these cases: reading localStorage is parsing UNTRUSTED
 * input. The value can be absent, a string, a size an older build offered, or
 * something a person typed into devtools. A throw here would white-screen the
 * entire student list, so every unusable value has to fall back rather than
 * propagate.
 */

import { renderHook, act } from '@testing-library/react';
import {
  useTablePageSize,
  readStoredPageSize,
  PAGE_SIZES,
  DEFAULT_PAGE_SIZE,
} from '../../hooks/useTablePrefs';

beforeEach(() => {
  window.localStorage.clear();
  jest.restoreAllMocks();
});

describe('the offered sizes', () => {
  it('are exactly what UX-DR10 specifies', () => {
    expect(PAGE_SIZES).toEqual([5, 10, 15, 20, 25, 30]);
  });

  it('default to 15, not 20', () => {
    // 20 was the old hard-coded page size; the owner asked for 15.
    expect(DEFAULT_PAGE_SIZE).toBe(15);
    expect(PAGE_SIZES).toContain(DEFAULT_PAGE_SIZE);
  });
});

describe('reading a stored size', () => {
  it('returns the default when nothing is stored', () => {
    expect(readStoredPageSize('students')).toBe(DEFAULT_PAGE_SIZE);
  });

  it('returns a valid stored size', () => {
    window.localStorage.setItem('eduflow.table.students.pageSize', '25');
    expect(readStoredPageSize('students')).toBe(25);
  });

  it.each([
    ['a size an older build offered', '50'],
    ['a value never offered', '7'],
    ['a non-numeric string', 'abc'],
    ['an empty string', ''],
    ['a float', '12.5'],
    ['a negative', '-10'],
    ['a hostile value', '<script>'],
    ['zero', '0'],
  ])('falls back to the default for %s', (_label, stored) => {
    window.localStorage.setItem('eduflow.table.students.pageSize', stored);
    expect(readStoredPageSize('students')).toBe(DEFAULT_PAGE_SIZE);
  });

  it('does not throw when storage itself is unavailable', () => {
    // Private-browsing and blocked-storage modes throw on access. Losing the
    // preference is acceptable; losing the list is not.
    jest.spyOn(window.localStorage.__proto__, 'getItem').mockImplementation(() => {
      throw new DOMException('denied');
    });
    expect(() => readStoredPageSize('students')).not.toThrow();
    expect(readStoredPageSize('students')).toBe(DEFAULT_PAGE_SIZE);
  });
});

describe('the preference is keyed per table', () => {
  it('sizing one table does not resize another', () => {
    // A single app-wide preference would mean sizing the 1,802-row student
    // list also resized the audit log, which is not what anyone means.
    const students = renderHook(() => useTablePageSize('students'));
    act(() => students.result.current[1](30));

    const audit = renderHook(() => useTablePageSize('audit'));
    expect(audit.result.current[0]).toBe(DEFAULT_PAGE_SIZE);
    expect(students.result.current[0]).toBe(30);
  });

  it('uses a namespaced storage key', () => {
    const { result } = renderHook(() => useTablePageSize('students'));
    act(() => result.current[1](10));
    expect(window.localStorage.getItem('eduflow.table.students.pageSize')).toBe('10');
  });
});

describe('setting a size', () => {
  it('remembers the choice across a remount', () => {
    const first = renderHook(() => useTablePageSize('students'));
    act(() => first.result.current[1](5));

    const second = renderHook(() => useTablePageSize('students'));
    expect(second.result.current[0]).toBe(5);
  });

  it('rejects a size that is not on the menu', () => {
    const { result } = renderHook(() => useTablePageSize('students'));
    act(() => result.current[1](1000));
    expect(result.current[0]).toBe(DEFAULT_PAGE_SIZE);
  });

  it('accepts the numeric string a <select> actually emits', () => {
    const { result } = renderHook(() => useTablePageSize('students'));
    act(() => result.current[1]('20'));
    expect(result.current[0]).toBe(20);
  });

  it('still applies the choice when storage refuses to persist it', () => {
    jest.spyOn(window.localStorage.__proto__, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded');
    });
    const { result } = renderHook(() => useTablePageSize('students'));
    expect(() => act(() => result.current[1](25))).not.toThrow();
    expect(result.current[0]).toBe(25);
  });
});
