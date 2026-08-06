import fs from 'fs';
import path from 'path';

function source(relativePath) {
  return fs.readFileSync(path.resolve(__dirname, relativePath), 'utf8');
}

test('shared responsive utilities collapse fixed layouts at phone widths', () => {
  const css = source('../../App.css');

  expect(css).toContain('.responsive-form-grid > *');
  expect(css).toContain('.responsive-table-region');
  expect(css).toMatch(/@media \(max-width: 640px\)[\s\S]*\.responsive-form-grid\s*{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) !important/);
  expect(css).toMatch(/@media \(max-width: 480px\)[\s\S]*\.responsive-stat-grid\s*{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\) !important/);
});

test.each([
  '../StudentProfileEditor.js',
  '../tools/AdminTools.js',
  '../tools/StudentDatabase.js',
  '../tools/StudentTools.js',
  '../tools/TeacherTools.js',
  '../tools/TimetableBuilder.js',
  '../tools/AdmissionsWorkflow.js',
  '../tools/StudentLeaveRequest.js',
  '../tools/StudentLeaveManager.js',
  '../tools/EnterpriseCampusTools.js',
  '../tools/FinanceControlTools.js',
  '../tools/QuizTools.js',
  '../tools/ParentTools.js',
])('%s opts fixed form grids into the responsive contract', (file) => {
  expect(source(file)).toContain('responsive-form-grid');
});

test('high-density role summaries and wide registers have narrow-screen safeguards', () => {
  expect(source('../tools/SchoolPulse.js')).toContain('responsive-stat-grid');
  expect(source('../tools/AttendanceRecorder.js')).toContain('responsive-table-region');
  expect(source('../tools/StudentTools.js')).toContain('responsive-table-region');
});

/*
 * Owner request 20 remainder, 2026-08-07.
 *
 * The two defects Aman named were fixed with rules keyed off `:has(> table)`, which
 * only reaches a wrapper whose DIRECT child is the table. Sweeping the rest of the
 * platform found the same two defects in three shapes that selector cannot reach.
 * These tests pin each shape, so a later edit to the CSS cannot quietly drop one.
 */
test('a table card that is the grandparent loses its side borders on phones', () => {
  const css = source('../../index.css');
  // Shape 1: <card border+radius><scroll div><table>. `.prose-chat` must stay
  // excluded, or a chat reply holding a markdown table loses its corners too.
  expect(css).toMatch(
    /:has\(> :is\(div, section\) > table\):not\(\.prose-chat\)[\s\S]*?border-radius: 0 !important/
  );
});

test('a table drawing its own border loses its side edges on phones', () => {
  const css = source('../../index.css');
  // Shape 2: TransportOptimisation puts the border on the <table>, so removing a
  // wrapper's border does nothing.
  expect(css).toMatch(
    /@media \(max-width: 900px\)[\s\S]*?\.app-main-content table\s*{[\s\S]*?border-left: none !important/
  );
});

test('every sideways-scrolling region gets the thin scrollbar, not only tables', () => {
  const css = source('../../index.css');
  // Shape 3: the chunky default scrollbar over a rounded edge is the defect Aman
  // described. It looked the same on non-table scroll regions, which were skipped.
  expect(css).toContain('.app-main-content .responsive-table-region::-webkit-scrollbar');
  expect(css).toContain('.app-main-content [style*="overflow-x: auto"]::-webkit-scrollbar');
  expect(css).toMatch(/\.app-main-content \.responsive-table-card[\s\S]*?scrollbar-width: thin/);
});

test('the shared tool table carries the card hook used by the phone rules', () => {
  // ToolPage's DataTable is the table on roughly twenty screens across every role,
  // which made it the single widest instance of shape 1.
  expect(source('../tools/ToolPage.js')).toContain('className="responsive-table-card"');
});
