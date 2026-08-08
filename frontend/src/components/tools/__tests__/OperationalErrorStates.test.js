import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StudyPlanner } from '../StudentTools';
import { SubstitutionViewer, WorksheetCreator } from '../TeacherTools';

let mockApiHandler;
let mockBulkMarkAttendance;

jest.mock('../../../contexts/UserContext', () => ({
  useUser: (() => {
    const currentUser = { id: 'user-1', role: 'teacher', name: 'Teacher' };
    return () => ({ currentUser });
  })(),
}));

jest.mock('../../../lib/api', () => {
  const actual = jest.requireActual('../../../lib/api');
  return {
    ...actual,
    API: 'http://api',
    apiFetch: (...args) => mockApiHandler(...args),
    bulkMarkAttendance: (...args) => mockBulkMarkAttendance(...args),
    getAllClasses: async () => ({ success: true, data: [{ id: 'class-1', name: '5th', section: 'A' }] }),
  };
});

const response = (body, ok = true) => ({ ok, json: async () => body });

beforeEach(() => {
  mockApiHandler = async () => response({ success: true, data: [] });
  mockBulkMarkAttendance = async () => ({ success: true });
});

test('worksheet editor stays open and reports a failed save', async () => {
  mockApiHandler = async (url, options = {}) => {
    if (options.method === 'POST') return response({ detail: 'Worksheet could not be saved' }, false);
    return response({ success: true, data: [] });
  };
  render(<WorksheetCreator />);
  fireEvent.click(await screen.findByText('New Worksheet'));
  fireEvent.change(screen.getByPlaceholderText('Chapter/topic name'), { target: { value: 'Fractions' } });
  fireEvent.click(screen.getByText('Save'));

  expect(await screen.findByRole('alert')).toHaveTextContent('Worksheet could not be saved');
  expect(screen.getByPlaceholderText('Chapter/topic name')).toHaveValue('Fractions');
});

test('study planner reports a failed save and does not claim automatic saving', async () => {
  mockApiHandler = async (url, options = {}) => {
    if (options.method === 'POST') return response({ detail: 'Study plan could not be saved' }, false);
    return response({ success: true, data: null });
  };
  render(<StudyPlanner />);
  await screen.findByText('Save My Plan');
  expect(screen.queryByText(/saved automatically/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Save My Plan'));

  expect(await screen.findByRole('alert')).toHaveTextContent('Study plan could not be saved');
});

test('substitution load failure is not presented as an empty schedule', async () => {
  mockApiHandler = async () => { throw new Error('offline'); };
  render(<SubstitutionViewer />);

  await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  expect(screen.getByRole('alert')).toHaveTextContent('Unable to load substitution assignments');
  expect(screen.queryByText(/No substitution assignments/)).not.toBeInTheDocument();
});

test('teacher attendance does not claim success when the save is refused', async () => {
  mockApiHandler = async (url) => {
    if (url.includes('/academics/my-teaching-scope')) {
      return response({
        success: true,
        data: { is_teacher: true, class_teacher_class_ids: ['class-1'], all_class_ids: ['class-1'] },
      });
    }
    if (url.includes('/attendance/student/today/')) {
      return response({
        success: true,
        data: [{ student_id: 'student-1', name: 'A Student', roll_number: '1', status: 'present' }],
      });
    }
    return response({ success: true, data: [] });
  };
  mockBulkMarkAttendance = async () => ({ success: false, detail: 'Attendance was not saved' });

  const { ClassAttendanceMarker } = require('../TeacherTools');
  render(<ClassAttendanceMarker />);
  fireEvent.click(await screen.findByText('Save Attendance'));

  expect(await screen.findByRole('alert')).toHaveTextContent('Attendance was not saved');
  expect(screen.queryByText('Saved!')).not.toBeInTheDocument();
});

test('teacher attendance load failure is not presented as an empty class', async () => {
  mockApiHandler = async (url) => {
    if (url.includes('/academics/my-teaching-scope')) {
      return response({
        success: true,
        data: { is_teacher: true, class_teacher_class_ids: ['class-1'], all_class_ids: ['class-1'] },
      });
    }
    if (url.includes('/attendance/student/today/')) throw new Error('offline');
    return response({ success: true, data: [] });
  };

  const { ClassAttendanceMarker } = require('../TeacherTools');
  render(<ClassAttendanceMarker />);

  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load this attendance register');
  expect(screen.queryByText('No students found')).not.toBeInTheDocument();
});
