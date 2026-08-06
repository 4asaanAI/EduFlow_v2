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

/*
 * Owner report, 2026-08-06 (iPhone 15 Pro): the platform opened already magnified —
 * menu and profile picture cut off the screen edges — and tapping any entry box
 * magnified it further, neither one asked for.
 *
 * One defect behind both complaints. Safari force-zooms the page when a field under
 * 16px takes focus and never zooms back out, so a single tap left the whole site
 * stuck magnified. The 16px floor was ALREADY written here and could not take
 * effect: the platform styles with React inline `style={{}}`, which outranks any
 * plain stylesheet rule, and thirteen shared style objects hard-code 12-15px.
 * `!important` is the only thing that outranks an inline style.
 *
 * These are source-text guards against the rules being deleted. They deliberately do
 * NOT prove the fix works — reading the CSS would have reported the floor as present
 * and correct throughout the whole period it was being silently overridden, which is
 * exactly why this reached the owner. Computed sizes are asserted in the browser, in
 * `tests/e2e/responsive.spec.js`.
 */
test('the iOS zoom floor is enforced hard enough to beat an inline style', () => {
  const css = source('../../index.css');
  // Without !important this rule is decorative: every inline fontSize wins.
  expect(css).toMatch(
    /@media \(max-width: 768px\)[\s\S]*?input:not\(\[type="checkbox"\]\)[\s\S]*?font-size: max\(16px, var\(--text-base\)\) !important/
  );
});

test('the mobile type scale never drops the 16px base that suppresses the zoom', () => {
  const css = source('../../index.css');
  // Both mobile breakpoints must hold 16px. The 420px block steps every other size
  // down and must not take the base with it.
  const blocks = css.match(/@media \(max-width: (?:768|420)px\)\s*{[\s\S]*?--text-base:\s*(\d+)px/g) || [];
  expect(blocks.length).toBe(2);
  blocks.forEach((b) => expect(b).toMatch(/--text-base:\s*16px/));
});

test('the user is never forbidden from zooming the page themselves', () => {
  // The usual one-line "fix" for zoom-on-focus is `maximum-scale=1, user-scalable=no`.
  // Banned twice over: Abhimanyu asked that pinch-zoom keep working when the user
  // chooses it, and removing zoom from people who need it to read is an
  // accessibility failure. The zoom is stopped by removing its cause instead.
  const html = fs.readFileSync(path.resolve(__dirname, '../../../public/index.html'), 'utf8');
  const tag = html.match(/<meta\s+name="viewport"[^>]*>/i);
  // Jest's expect takes no message argument (Playwright's does) — the assertion name
  // carries the meaning instead.
  expect(tag).toBeTruthy();
  expect(tag[0]).not.toMatch(/user-scalable\s*=\s*(no|0)/i);
  expect(tag[0]).not.toMatch(/maximum-scale\s*=\s*1(\.0)?\b/i);
  expect(tag[0]).toMatch(/width\s*=\s*device-width/i);
});
