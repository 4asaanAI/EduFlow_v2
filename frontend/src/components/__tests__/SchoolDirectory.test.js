/**
 * Epic 7 — A Directory Shaped Like The School.
 *
 * Two things are pinned here:
 *  1. The staff-vocabulary HONESTY rule (Story 7.1). A register code is shown
 *     ONLY where confidently derivable (Principal → PRIN). The teacher tier
 *     (NTT/PRT/TGT/PGT) is not in the data and must NOT be invented.
 *  2. The nav gating and consolidation (Stories 7.2/7.3). 'school-directory'
 *     is Owner + Principal ONLY, and the consolidated maintenance set does not
 *     silently regain its duplicate 'raise-maintenance' entry point.
 * The server is the authoritative gate; these pin the convenience layer so it
 * cannot drift back to advertising the wrong thing.
 */

import { registerCode, designationOf } from '../tools/SchoolDirectory';
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

describe('nav gating — Directory is Owner + Principal only', () => {
  it('is in the Owner set', () => {
    expect(OWNER_TOOLS).toContain('school-directory');
  });

  it('is in the Principal set', () => {
    expect(TOOL_SETS.admin_principal).toContain('school-directory');
  });

  it.each([
    'admin_accountant',
    'admin_transport_head',
    'admin_receptionist',
    'admin_it_tech',
    'admin_maintenance',
    'student',
    'teacher',
  ])('is ABSENT from %s', (key) => {
    expect(TOOL_SETS[key]).not.toContain('school-directory');
  });
});

describe('consolidation — no silent re-introduction of duplicates', () => {
  it('the maintenance set keeps the queue and drops the duplicate report shortcut', () => {
    expect(TOOL_SETS.admin_maintenance).toContain('facility-requests');
    expect(TOOL_SETS.admin_maintenance).not.toContain('raise-maintenance');
  });

  it("'raise-maintenance' still exists for the roles it is the only way in for", () => {
    expect(TOOL_SETS.admin_accountant).toContain('raise-maintenance');
    expect(TOOL_SETS.admin_it_tech).toContain('raise-maintenance');
  });
});
