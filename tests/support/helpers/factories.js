/**
 * Data Factories — EduFlow Test Data
 *
 * Provides factory functions for generating test data objects.
 * All factories accept an optional `overrides` object to customize fields.
 *
 * Convention:
 *   - Use `build<Entity>()` to get a plain data object (no DB write)
 *   - Factories are deterministic but use counters for uniqueness
 *   - Never use real PII — always synthetic data
 */

let _counter = 0;
function uid() {
  return ++_counter;
}

/**
 * Reset the counter (useful in beforeEach to keep IDs predictable).
 */
function resetFactoryCounter() {
  _counter = 0;
}

// ─── Student Factory ─────────────────────────────────────────────────────────

/**
 * Build a student data object.
 * @param {Partial<{name: string, class_name: string, section: string, roll_number: string, parent_phone: string}>} overrides
 */
function buildStudent(overrides = {}) {
  const n = uid();
  return {
    name: `Test Student ${n}`,
    class_name: 'Class 5',
    section: 'A',
    roll_number: `ROLL${String(n).padStart(4, '0')}`,
    parent_name: `Parent ${n}`,
    parent_phone: `900000${String(n).padStart(4, '0')}`,
    date_of_birth: '2014-01-15',
    address: `${n} Test Lane, Test City`,
    gender: 'M',
    ...overrides,
  };
}

// ─── Staff Factory ───────────────────────────────────────────────────────────

/**
 * Build a staff member data object.
 * @param {Partial<{name: string, role: string, subject: string, phone: string}>} overrides
 */
function buildStaff(overrides = {}) {
  const n = uid();
  return {
    name: `Test Teacher ${n}`,
    role: 'teacher',
    subject: 'Mathematics',
    phone: `800000${String(n).padStart(4, '0')}`,
    email: `teacher${n}@testschool.edu`,
    employee_id: `EMP${String(n).padStart(4, '0')}`,
    join_date: '2023-06-01',
    ...overrides,
  };
}

// ─── Fee Record Factory ──────────────────────────────────────────────────────

/**
 * Build a fee record data object.
 * @param {Partial<{amount: number, fee_type: string, due_date: string}>} overrides
 */
function buildFeeRecord(overrides = {}) {
  const n = uid();
  return {
    amount: 5000,
    fee_type: 'tuition',
    due_date: '2026-06-30',
    description: `Fee record ${n}`,
    academic_year: '2025-26',
    ...overrides,
  };
}

// ─── Login Credential Factory ─────────────────────────────────────────────────

/**
 * Build login credentials.
 * @param {'admin'|'teacher'|'parent'} role
 */
function buildCredentials(role = 'admin') {
  const map = {
    admin: {
      username: process.env.TEST_ADMIN_USERNAME || 'admin',
      password: process.env.TEST_ADMIN_PASSWORD || 'admin123',
    },
    teacher: {
      username: process.env.TEST_TEACHER_USERNAME || 'teacher1',
      password: process.env.TEST_TEACHER_PASSWORD || 'teacher123',
    },
    parent: {
      username: process.env.TEST_PARENT_USERNAME || 'parent1',
      password: process.env.TEST_PARENT_PASSWORD || 'parent123',
    },
  };
  return map[role] || map.admin;
}

module.exports = {
  buildStudent,
  buildStaff,
  buildFeeRecord,
  buildCredentials,
  resetFactoryCounter,
};
