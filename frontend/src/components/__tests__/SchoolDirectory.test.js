/**
 * Epic 7 — A Directory Shaped Like The School.
 *
 * Two things are pinned here:
 *  1. The staff-vocabulary HONESTY rule (Story 7.1). A register code is shown
 *     ONLY where confidently derivable (Principal → PRIN). The teacher tier
 *     (NTT/PRT/TGT/PGT) is not in the data and must NOT be invented.
 *  2. The nav gating and consolidation (Stories 7.2/7.3), restated 2026-08-07 when
 *     'school-directory' merged into 'student-database' — one screen instead of two
 *     listing the same students. The old id resolves through lib/toolAliases, and the
 *     Owner+Principal limit now guards the Staff TAB inside the merged screen. The
 *     consolidated maintenance set still does not silently regain its duplicate
 *     'raise-maintenance' entry point.
 * The server is the authoritative gate; these pin the convenience layer so it
 * cannot drift back to advertising the wrong thing.
 */

import { registerCode, designationOf } from '../tools/SchoolDirectory';
import { resolveToolId } from '../../lib/toolAliases';
import { OWNER_TOOLS, TOOL_SETS } from '../ToolDashboard';

describe('staff vocabulary — honest register codes', () => {
  it('derives PRIN for a principal by sub_category', () => {
    expect(registerCode({ sub_category: 'principal' })).toEqual({
      code: 'PRIN',
      full: 'Principal',
    });
  });

  it('derives PRIN when the stored designation is Principal', () => {
    expect(registerCode({ designation: 'Principal' })?.code).toBe('PRIN');
  });

  it('NEVER invents a teacher-tier code — it is not in the data', () => {
    // A class teacher has no stored NTT/PRT/TGT/PGT distinction. Returning a
    // guessed code would be the failure-that-looks-like-a-fact defect.
    expect(registerCode({ designation: 'Class Teacher', sub_category: 'class_teacher' })).toBeNull();
    expect(registerCode({ role: 'teacher', staff_type: 'teacher' })).toBeNull();
  });

  it('falls back to the readable designation, never role / sub_category', () => {
    expect(designationOf({ designation: 'Class Teacher' })).toBe('Class Teacher');
    expect(designationOf({ sub_category: 'transport_head' })).toBe('Transport Head');
    expect(designationOf({})).toBe('—');
  });
});

describe('nav gating after the merge (2026-08-07)', () => {
  // The Directory and the Student Database were two screens listing the same
  // students, and the school's owner reported them as "two views of the student
  // database for some reason". They are one screen now, under the id
  // 'student-database'. The Directory's id is retired and resolves through
  // lib/toolAliases, so old links and bookmarks still land.
  //
  // The merged screen reaches MORE roles than the Directory did, because the Student
  // Database always did. That is why the Staff tab inside it is gated separately, to
  // owner and principal — the roles the Directory itself was limited to. Losing that
  // gate would hand the staff list to the accountant and the receptionist.
  const MERGED = 'student-database';

  it('the retired name is offered by no menu', () => {
    expect(OWNER_TOOLS).not.toContain('school-directory');
    Object.values(TOOL_SETS).forEach((set) => expect(set).not.toContain('school-directory'));
  });

  it('the retired name still resolves, so old links and bookmarks work', () => {
    expect(resolveToolId('school-directory')).toBe(MERGED);
  });

  it('is in the Owner set', () => {
    expect(OWNER_TOOLS).toContain(MERGED);
  });

  it('is in the Principal set', () => {
    expect(TOOL_SETS.admin_principal).toContain(MERGED);
  });

  it('the owner is offered it exactly once — the merge removed a duplicate', () => {
    expect(OWNER_TOOLS.filter((id) => id === MERGED)).toHaveLength(1);
  });

  it.each(['student', 'teacher'])('is ABSENT from %s', (key) => {
    expect(TOOL_SETS[key]).not.toContain(MERGED);
  });
});

describe('consolidation — no silent re-introduction of duplicates', () => {
  it('the maintenance set keeps the queue and drops the duplicate report shortcut', () => {
    expect(TOOL_SETS.admin_maintenance).toContain('facility-requests');
    expect(TOOL_SETS.admin_maintenance).not.toContain('raise-maintenance');
  });

  it("'raise-maintenance' stays non-financial and remains available to IT support", () => {
    expect(TOOL_SETS.admin_accountant).not.toContain('raise-maintenance');
    expect(TOOL_SETS.admin_it_tech).toContain('raise-maintenance');
  });
});
