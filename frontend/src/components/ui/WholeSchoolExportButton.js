/**
 * "Download the whole school" - one Excel file, a separate sheet per area.
 *
 * Release 3, item B. Children, staff, fees and payments, attendance, exam results,
 * classes, transport, expenses and enquiries, in one workbook the office can tab
 * across.
 *
 * FOR THE SCHOOL'S OWNER AND THE PRINCIPAL ONLY (Abhimanyu, 2026-08-12). This
 * component hides itself for everybody else, and the server refuses everybody else
 * as well. The hiding is a courtesy so nobody taps a button that will only tell them
 * no; the refusal is the actual rule. Neither is a substitute for the other.
 *
 * IT READS BACK EVERY SHEET'S SIZE. The server sends the counts on a header, so the
 * screen can say "Children 1,876, Staff 62..." without anybody opening the file.
 * Nine tabs is precisely the shape where one coming back empty would go unnoticed,
 * and this download is the largest copy of the school's records that exists.
 *
 * No confirm step, like every other export in this release.
 */

import React, { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from './primitives';
import { downloadWholeSchool } from '../../lib/exportTable';

/** True only for the school's owner and the principal. */
export function mayDownloadWholeSchool(user) {
  if (!user) return false;
  if (user.role === 'owner') return true;
  return user.role === 'admin' && user.sub_category === 'principal';
}

export default function WholeSchoolExportButton({ user, testId = 'whole-school-export' }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');

  if (!mayDownloadWholeSchool(user)) return null;

  async function run() {
    setBusy(true);
    setError('');
    setDone('');
    try {
      const counts = await downloadWholeSchool();
      setDone(counts ? `Downloaded. ${counts.replace(/;/g, ',')}.` : 'Downloaded.');
    } catch (err) {
      // Say it out loud. A browser that silently saves nothing looks exactly like one
      // that saved a file.
      setError(err.message || 'The download failed. Nothing was saved.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <Button
        size="sm"
        variant="secondary"
        data-testid={testId}
        disabled={busy}
        onClick={run}
      >
        <Download size={14} aria-hidden="true" style={{ marginRight: 6 }} />
        {busy ? 'Preparing the whole school...' : 'Download the whole school'}
      </Button>
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
