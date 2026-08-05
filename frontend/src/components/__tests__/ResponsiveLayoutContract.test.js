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
