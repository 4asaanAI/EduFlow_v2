/**
 * A download is complete, or there is no download.
 *
 * THE FAULT THIS PINS. Every serious defect found on 11 and 12 August was a query
 * that quietly returned less than it should. An export is the worst place for that
 * to happen: a short screen is an annoyance, a short file leaves the building, gets
 * mailed to the trust and filed as a record, and carries nothing on its face to say
 * it is partial.
 *
 * So the tests below are mostly about the failing cases. Saving something is easy;
 * refusing to save half of something, loudly, is the part that has to hold.
 */

import { downloadTableRows, downloadServerExport, tableToRows } from '../exportTable';

const originalCreate = global.URL.createObjectURL;
const originalRevoke = global.URL.revokeObjectURL;

let saved;
let clicked;

beforeEach(() => {
  saved = [];
  clicked = [];
  global.URL.createObjectURL = jest.fn(() => 'blob:fake');
  global.URL.revokeObjectURL = jest.fn();
  // Capture the download instead of letting jsdom try to navigate to it.
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click() {
    clicked.push(this.download);
  });
  global.fetch = jest.fn(async (url, options) => {
    saved.push({ url, options });
    return {
      ok: true,
      status: 200,
      blob: async () => new Blob(['col\nvalue']),
    };
  });
});

afterEach(() => {
  jest.restoreAllMocks();
  global.URL.createObjectURL = originalCreate;
  global.URL.revokeObjectURL = originalRevoke;
});

function failingFetch(status, body) {
  global.fetch = jest.fn(async () => ({
    ok: false,
    status,
    json: async () => body,
    blob: async () => new Blob([]),
  }));
}

describe('packaging the rows a screen holds', () => {
  test('posts the headings and rows and saves the file', async () => {
    await downloadTableRows({
      title: 'Vendors',
      headers: ['Name', 'Trade'],
      rows: [['Sharma Works', 'Furniture']],
      format: 'xlsx',
    });

    expect(saved).toHaveLength(1);
    const body = JSON.parse(saved[0].options.body);
    expect(body.headers).toEqual(['Name', 'Trade']);
    expect(body.rows).toEqual([['Sharma Works', 'Furniture']]);
    expect(body.format).toBe('xlsx');
    expect(clicked[0]).toMatch(/^vendors-\d{4}-\d{2}-\d{2}\.xlsx$/);
  });

  test('a refused download throws the SERVER\'s wording, and saves nothing', async () => {
    // The server's message says whether a file was produced and what to do next.
    // Replacing it with "export failed" throws away the only useful sentence.
    failingFetch(413, {
      detail: 'That is more than 50,000 rows. Nothing has been left out of a file: '
        + 'this request produced no file at all.',
    });

    await expect(downloadTableRows({
      title: 'Fees', headers: ['A'], rows: [['x']],
    })).rejects.toThrow(/no file at all/);
    expect(clicked).toHaveLength(0);
  });

  test('a refusal on permission says so in words a person can act on', async () => {
    failingFetch(403, null);
    await expect(downloadTableRows({ title: 'Fees', headers: ['A'], rows: [] }))
      .rejects.toThrow(/permission/i);
    expect(clicked).toHaveLength(0);
  });

  test('a table with no columns is refused before any request is made', async () => {
    await expect(downloadTableRows({ title: 'Empty', headers: [], rows: [] }))
      .rejects.toThrow(/no columns/i);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('using one of the server exports', () => {
  test("carries the screen's live filters through to the download", async () => {
    // A download of "unpaid fees for April" that comes back as every fee ever taken
    // is the same class of fault as a short file, in the other direction.
    await downloadServerExport(
      'fee-transactions', { status: 'unpaid', fee_period: 'April', blank: '' }, 'csv', 'Fees',
    );

    const url = saved[0].url;
    expect(url).toContain('status=unpaid');
    expect(url).toContain('fee_period=April');
    expect(url).toContain('format=csv');
    // An empty filter is not a filter. Sending it would narrow the file to rows
    // whose value is literally blank.
    expect(url).not.toContain('blank=');
  });

  test('a refusal saves nothing', async () => {
    failingFetch(500, null);
    await expect(downloadServerExport('students', {}, 'csv', 'Students')).rejects.toThrow();
    expect(clicked).toHaveLength(0);
  });
});

describe('flattening a table for a spreadsheet', () => {
  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'status', label: 'Status', render: () => 'a react badge' },
    { key: 'due', label: 'Due', exportValue: (r) => r.due_amount },
    { key: 'actions', label: '', exportSkip: true },
  ];

  test('uses exportValue where the screen renders something a file cannot hold', () => {
    const { headers, rows } = tableToRows(columns, [
      { name: 'Aarav', status: { code: 'ok' }, due_amount: 4500 },
    ]);

    expect(headers).toEqual(['Name', 'Status', 'Due']);
    // A cell that would have been an object becomes blank rather than
    // "[object Object]", which is not a value anyone can reconcile against.
    expect(rows).toEqual([['Aarav', '', 4500]]);
  });

  test('leaves out the row-action column instead of exporting blank cells', () => {
    const { headers } = tableToRows(columns, []);
    // A column of empty cells reads as missing data. An absent column reads as a
    // control that did not belong in a file, which is what it is.
    expect(headers).not.toContain('');
    expect(headers).toHaveLength(3);
  });

  test('a missing value is blank, not the screen\'s "not recorded"', () => {
    const { rows } = tableToRows([{ key: 'dob', label: 'DOB' }], [{ dob: null }]);
    // The screen says "not recorded" because a reader needs to tell empty from
    // never-collected. A spreadsheet is also read by formulas and imports, and a
    // word where a date belongs breaks them.
    expect(rows).toEqual([['']]);
  });
});
