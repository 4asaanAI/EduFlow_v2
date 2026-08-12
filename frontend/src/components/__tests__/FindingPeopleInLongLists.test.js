/**
 * Owner note, 2026-08-07: "there should be a search option for the name among the
 * list. Also the whole list of students is not appearing here and same at other
 * places too... and no search option among the list".
 *
 * Two separate faults, and they have to be fixed together:
 *   1. Screens asked the server for students with no limit, so it answered with its
 *      default of twenty. On 1,802 students that is a list that LOOKS complete.
 *   2. Even complete, a dropdown of 1,802 names cannot be used without a search.
 *
 * A search box over a truncated list is worse than the scroll it replaced, because it
 * reports "not found" for a person who is really there.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u-1', role: 'owner', sub_category: 'owner', name: 'Aman Litt' } }),
}));
jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

import SearchablePicker from '../ui/SearchablePicker';
import { getAllStudents, STUDENTS_PAGE_MAX } from '../../lib/api';
import { setAuthSession, resetAuthRedirectGuardForTests } from '../../lib/authSession';

const realFetch = global.fetch;

beforeEach(() => {
  setAuthSession('a-valid-token', { id: 'u-1', role: 'owner' });
  resetAuthRedirectGuardForTests();
});

afterEach(() => {
  jest.restoreAllMocks();
  global.fetch = realFetch;
  resetAuthRedirectGuardForTests();
});

describe('fetching the whole list, not the first page of it', () => {
  const jsonOk = (payload) => ({
    ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload),
  });

  it('walks the pages until every student is collected', async () => {
    // 1,802 students is what this school actually has, and the server caps one
    // request at 500 - so the answer takes four requests, not one.
    const TOTAL = 1802;
    const pageOf = (page) => {
      const start = (page - 1) * STUDENTS_PAGE_MAX;
      const size = Math.min(STUDENTS_PAGE_MAX, TOTAL - start);
      return Array.from({ length: Math.max(0, size) }, (_, i) => ({ id: `s-${start + i}`, name: `Student ${start + i}` }));
    };
    global.fetch = jest.fn((url) => {
      const page = Number(new URL(String(url), 'http://x').searchParams.get('page') || 1);
      return Promise.resolve(jsonOk({ success: true, data: pageOf(page), meta: { total: TOTAL } }));
    });

    const res = await getAllStudents();

    expect(res.success).toBe(true);
    expect(res.data).toHaveLength(TOTAL);
    expect(global.fetch).toHaveBeenCalledTimes(4);
  });

  it('stops when a page comes back short, so a wrong total cannot spin forever', async () => {
    global.fetch = jest.fn(() => Promise.resolve(jsonOk({
      success: true,
      data: [{ id: 's-1', name: 'Only One' }],
      // A total the server got wrong. The short page is what actually ends the loop.
      meta: { total: 999999 },
    })));

    const res = await getAllStudents();

    expect(res.data).toHaveLength(1);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('fails outright if a later page fails, rather than handing back half a roll', async () => {
    /**
     * REVERSED DELIBERATELY on 2026-08-12 (Release 3).
     *
     * This test used to assert the opposite: 500 of 900 students returned as a
     * SUCCESS carrying `meta.partial = true`, on the reasoning that "half a list
     * clearly marked partial beats an error that throws away 500 records".
     *
     * The premise was false in practice. Nothing in the codebase ever read
     * `meta.partial` - every caller was `if (r.success) setStudents(r.data)` - so
     * "clearly marked" marked nothing, and the screen showed 500 of 900 children
     * with no indication that 400 were missing. In a picker used to find a child,
     * that reports a genuinely enrolled student as not there.
     *
     * That is the exact shape of every fault found on 11 and 12 August: a query
     * that quietly returns less than it should. So it fails now, and the failure
     * is the caller's problem to show rather than ours to hide.
     */
    let call = 0;
    global.fetch = jest.fn(() => {
      call += 1;
      if (call === 1) {
        return Promise.resolve(jsonOk({
          success: true,
          data: Array.from({ length: STUDENTS_PAGE_MAX }, (_, i) => ({ id: `s-${i}`, name: `S${i}` })),
          meta: { total: 900 },
        }));
      }
      return Promise.resolve(jsonOk({ success: false, detail: 'Server fell over' }));
    });

    const res = await getAllStudents();

    expect(res.success).toBe(false);
    expect(res.data).toHaveLength(0);
    // The reason travels with the failure so a screen can say what went wrong.
    expect(res.detail).toBe('Server fell over');
  });
});

describe('picking one person out of a long list', () => {
  const options = [
    { value: 's1', label: 'Shriyansh Uppal', hint: '12th-B · 1505' },
    { value: 's2', label: 'Akshay Chahal', hint: '10th-A · 1503' },
    { value: 's3', label: 'Kashish Chaudhary', hint: '11th-B · 1506' },
  ];

  it('narrows the list as you type', () => {
    render(<SearchablePicker label="Student" value="" onChange={() => {}} options={options} data-testid="pick" />);

    expect(screen.getAllByRole('option')).toHaveLength(4);  // three plus "Select…"

    fireEvent.change(screen.getByTestId('pick-search'), { target: { value: 'chaudhary' } });

    const shown = screen.getAllByRole('option').map((o) => o.textContent);
    expect(shown).toContain('Kashish Chaudhary - 11th-B · 1506');
    expect(shown).not.toContain('Akshay Chahal - 10th-A · 1503');
  });

  it('searches the hint too, so a class or admission number finds the child', () => {
    render(<SearchablePicker label="Student" value="" onChange={() => {}} options={options} data-testid="pick" />);

    fireEvent.change(screen.getByTestId('pick-search'), { target: { value: '1503' } });

    const shown = screen.getAllByRole('option').map((o) => o.textContent);
    expect(shown).toContain('Akshay Chahal - 10th-A · 1503');
    expect(shown).toHaveLength(2);  // the match plus "Select…"
  });

  it('keeps the chosen person selectable after the search narrows them out', () => {
    // Otherwise typing after choosing silently clears the selection, and the person
    // presses Generate for a child they did not pick.
    render(<SearchablePicker label="Student" value="s2" onChange={() => {}} options={options} data-testid="pick" />);

    fireEvent.change(screen.getByTestId('pick-search'), { target: { value: 'zzzz' } });

    expect(screen.getByRole('option', { name: /Akshay Chahal/ })).toBeInTheDocument();
    expect(screen.getByTestId('pick')).toHaveValue('s2');
  });

  it('says how many of the list is being shown, rather than implying it is all of them', () => {
    render(<SearchablePicker label="Student" value="" onChange={() => {}} options={options} data-testid="pick" />);
    expect(screen.getByText('3 of 3 shown.')).toBeInTheDocument();
  });

  it('says plainly when there is nothing to choose from', () => {
    render(<SearchablePicker label="Student" value="" onChange={() => {}} options={[]} data-testid="pick" />);
    expect(screen.getByText(/Nothing to choose from yet/i)).toBeInTheDocument();
  });
});

describe('the ID card list', () => {
  const STUDENTS = {
    success: true,
    data: [
      { id: 's-1', name: 'Aarav Sharma', class_id: 'c-1', admission_number: 'ADM1', roll_number: '1' },
      { id: 's-2', name: 'Bhavna Verma', class_id: 'c-1', admission_number: 'ADM2', roll_number: '2' },
    ],
    meta: { total: 2 },
  };

  const jsonOk = (payload) => ({
    ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload),
  });

  beforeEach(() => {
    global.fetch = jest.fn((url) => {
      if (String(url).includes('/students')) return Promise.resolve(jsonOk(STUDENTS));
      return Promise.resolve(jsonOk({ success: true, data: [] }));
    });
  });

  it('can be searched by name', async () => {
    const { IdCardGenerator } = await import('../tools/AdminTools');
    render(<IdCardGenerator />);
    await screen.findByText('Aarav Sharma');

    fireEvent.change(screen.getByTestId('id-card-search'), { target: { value: 'bhavna' } });

    await waitFor(() => expect(screen.queryByText('Aarav Sharma')).not.toBeInTheDocument());
    expect(screen.getByText('Bhavna Verma')).toBeInTheDocument();
  });

  it('selects only what the search has left on screen', async () => {
    // Selecting rows a search has hidden is how somebody prints 1,802 cards while
    // looking at a list of one.
    const { IdCardGenerator } = await import('../tools/AdminTools');
    render(<IdCardGenerator />);
    await screen.findByText('Aarav Sharma');

    fireEvent.change(screen.getByTestId('id-card-search'), { target: { value: 'bhavna' } });
    await waitFor(() => expect(screen.queryByText('Aarav Sharma')).not.toBeInTheDocument());
    fireEvent.click(screen.getByText(/Select all shown/i));

    expect(await screen.findByText(/Download 1 ID Cards PDF/i)).toBeInTheDocument();
  });
});
