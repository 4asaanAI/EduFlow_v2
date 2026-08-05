import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import TimetableBuilder from '../TimetableBuilder';
import { apiFetch } from '../../../lib/api';

jest.mock('../../../lib/api', () => ({ API: 'http://api', apiFetch: jest.fn() }));
jest.mock('../../../lib/authSession', () => ({ getAuthHeaders: () => ({ Authorization: 'Bearer test' }) }));
jest.mock('../../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'owner-1', role: 'owner', name: 'School Owner' } }),
}));
jest.mock('../../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));

function response(data, ok = true) {
  return Promise.resolve({ ok, json: async () => data });
}

beforeEach(() => {
  apiFetch.mockImplementation((url) => {
    if (url.includes('/settings/classes')) {
      return response({ success: true, data: [{ id: 'class-1', name: 'Class 5', section: 'A' }] });
    }
    if (url.includes('/staff/')) {
      return response({ success: true, data: [{ id: 'teacher-1', name: 'Teacher One', staff_type: 'teacher' }] });
    }
    if (url.includes('/academics/subjects')) {
      return response({ success: true, data: [{ id: 'subject-1', name: 'Mathematics', class_id: 'class-1' }] });
    }
    if (url.includes('/academics/timetable/')) {
      return response({ success: true, data: [] });
    }
    return response({ success: true, data: {} });
  });
});

afterEach(() => jest.clearAllMocks());

test('loads class subjects and offers real subject IDs in the slot editor', async () => {
  const { container } = render(<TimetableBuilder />);

  const classSelect = await screen.findByDisplayValue('Select class...');
  await waitFor(() => expect(classSelect.querySelector('option[value="class-1"]')).not.toBeNull());
  fireEvent.change(classSelect, { target: { value: 'class-1' } });

  await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
    'http://api/academics/subjects?class_id=class-1',
    expect.any(Object),
  ));

  fireEvent.click(screen.getAllByText('+')[0]);
  expect(await screen.findByRole('option', { name: 'Mathematics' })).toHaveValue('subject-1');
  expect(container.querySelector('.responsive-form-grid')).toBeInTheDocument();
});
