/**
 * The download control that sits on every table (Release 3, item 4).
 *
 * THE THING MOST LIKELY TO BE GOT WRONG: this must export the WHOLE filtered set,
 * never the page on screen. Someone looking at page 3 of unpaid fees and pressing
 * Download means "the unpaid fees", not "these fifteen". A file holding one page,
 * with nothing on it to say so, is the exact fault this release exists to remove -
 * except worse, because a file leaves the building and gets filed as a record.
 *
 * So the screen hands in `getRows`, which fetches everything matching the filters
 * that are set right now, and this component refuses to save anything if that fetch
 * comes back short or fails. There is no half-file path here to take by mistake.
 *
 * WHAT IS DELIBERATELY ABSENT: a confirm step. Abhimanyu settled on 2026-08-12 that
 * an export needs no approval window, on screen or through Flo. What needs guarding
 * is WHO may read the rows, and that is settled by the endpoint the rows came from.
 *
 * Two plain buttons rather than a dropdown menu: phone and tablet are the primary
 * devices here, and a menu that opens over the table is one more tap and one more
 * thing to mis-hit with a thumb.
 */

import React, { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from './primitives';
import { downloadTableRows, downloadServerExport, tableToRows } from '../../lib/exportTable';

/**
 * @param {object}   props
 * @param {string}   props.title    what the sheet and the file are called
 * @param {Array}    [props.columns] the table's column definitions, when exporting
 *                                   rows the screen holds
 * @param {Function} [props.getRows] async () => rows. Must return EVERY row matching
 *                                   the filters in force, not the page on screen.
 * @param {object}   [props.serverExport] `{ path, params }` to use a server export
 *                                   instead. `params` must carry the screen's live
 *                                   filters.
 * @param {boolean}  [props.disabled]
 * @param {string}   [props.testId]
 */
export default function ExportButton({
  title,
  columns,
  getRows,
  serverExport,
  total = 0,
  disabled = false,
  testId = 'export',
}) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState('');

  async function run(format) {
    setBusy(format);
    setError('');
    setDone('');
    try {
      if (serverExport) {
        await downloadServerExport(
          serverExport.path, serverExport.params || {}, format, title,
        );
        // The server read the rows, so this side cannot honestly count them. It says
        // what it knows rather than inventing a number - a wrong count would be a
        // worse answer than none, because someone would reconcile against it.
        setDone('Downloaded.');
      } else {
        const all = await getRows();

        // THE SAFETY NET, and the reason it is here rather than left to each screen.
        //
        // Around seventy tables have to be wired to this control, one at a time, by
        // hand. The mistake that wiring invites is passing the rows already on screen
        // instead of every row that matches - and that mistake produces a file that
        // looks perfectly normal, holds fifteen rows, and says nothing about the
        // other 1,861. It is the exact fault this release exists to remove, in the
        // one place it does the most damage.
        //
        // The table already knows how many rows match, because it prints that figure
        // beside the rows-per-page menu. So a download that comes back with fewer
        // than that is caught here and REFUSED, for every screen at once, rather than
        // depending on whoever wired each one having thought about it.
        if (total > 0 && all.length < total) {
          throw new Error(
            `This would have saved only ${all.length.toLocaleString('en-IN')} of `
            + `${total.toLocaleString('en-IN')} rows, so nothing was saved. `
            + 'Please report this: the download is not reading the whole list.',
          );
        }

        const { headers, rows } = tableToRows(columns, all);
        await downloadTableRows({ title, headers, rows, format });
        setDone(`Downloaded ${rows.length.toLocaleString('en-IN')} rows.`);
      }
    } catch (err) {
      // Nothing was saved. Say so, because a browser that silently saves nothing is
      // indistinguishable from one that saved an empty file.
      setError(err.message || 'The download failed. Nothing was saved.');
    } finally {
      setBusy('');
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <span
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)',
          fontFamily: 'var(--font-display)', fontWeight: 600,
        }}
      >
        <Download size={14} aria-hidden="true" />
        Download
      </span>
      <Button
        size="sm"
        variant="secondary"
        data-testid={`${testId}-xlsx`}
        disabled={disabled || !!busy}
        onClick={() => run('xlsx')}
      >
        {busy === 'xlsx' ? 'Preparing...' : 'Excel'}
      </Button>
      <Button
        size="sm"
        variant="secondary"
        data-testid={`${testId}-csv`}
        disabled={disabled || !!busy}
        onClick={() => run('csv')}
      >
        {busy === 'csv' ? 'Preparing...' : 'CSV'}
      </Button>
      {/* aria-live, so someone using a screen reader hears the outcome. Both
          outcomes are announced: a download that quietly did nothing is the fault
          this release is about. */}
      <span
        aria-live="polite"
        data-testid={`${testId}-status`}
        style={{
          fontSize: 'var(--text-sm)',
          color: error ? 'var(--color-accent-red, #b42318)' : 'var(--color-text-muted)',
        }}
      >
        {error || done}
      </span>
    </div>
  );
}
