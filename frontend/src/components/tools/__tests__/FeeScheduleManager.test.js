import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import FeeScheduleManager from '../FeeScheduleManager';
import { apiFetch } from '../../../lib/api';

jest.mock('../../../lib/api', () => ({ API: 'http://api', apiFetch: jest.fn() }));
jest.mock('../../../lib/authSession', () => ({ getAuthHeaders: () => ({ Authorization: 'Bearer test' }) }));

function response(data, ok = true) {
  return Promise.resolve({ ok, json: async () => data });
}

beforeEach(() => {
  apiFetch.mockImplementation((url, options = {}) => {
    if (url === 'http://api/fees/structures' && !options.method) {
      return response({
        success: true,
        data: [{
          id: 'structure-1', name: 'Class 5 fees', version: 2,
          installments: [{ code: 'TERM-1', label: 'Term 1', due_date: '2026-08-31', fee_heads: [{ name: 'Tuition', amount: 12000 }] }],
        }],
      });
    }
    if (url.endsWith('/installments')) return response({ success: true, data: { version: 3 } });
    if (url.endsWith('/charges/preview')) return response({ success: true, data: { charge_count: 20, student_count: 20, total_amount: 240000 } });
    return response({ success: true, data: {} });
  });
});

afterEach(() => jest.clearAllMocks());

test('owner can edit, version, and preview an installment schedule', async () => {
  render(<FeeScheduleManager currentUser={{ id: 'owner-1', role: 'owner' }} />);

  const structureSelect = await screen.findByLabelText('Fee structure');
  await waitFor(() => expect(structureSelect).toHaveValue('structure-1'));
  fireEvent.change(screen.getByLabelText('Installment 1 amount 1'), { target: { value: '12500' } });
  fireEvent.click(screen.getByRole('button', { name: /save schedule/i }));

  await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
    'http://api/fees/structures/structure-1/installments',
    expect.objectContaining({
      method: 'PUT',
      body: expect.stringContaining('12500'),
    }),
  ));
  await waitFor(() => expect(screen.getByRole('button', { name: /preview charges/i })).not.toBeDisabled());

  fireEvent.click(screen.getByRole('button', { name: /preview charges/i }));
  await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
    'http://api/fees/structures/structure-1/charges/preview',
    expect.objectContaining({ method: 'POST' }),
  ));
  await waitFor(() => expect(screen.getByLabelText('Fee structures and installments')).toHaveTextContent('20 charges'));
  expect(screen.getByLabelText('Fee structures and installments')).toHaveTextContent('Rs 2,40,000');
});

test('non-owner roles do not receive the schedule editor', () => {
  const { container } = render(<FeeScheduleManager currentUser={{ id: 'admin-1', role: 'admin' }} />);
  expect(container).toBeEmptyDOMElement();
  expect(apiFetch).not.toHaveBeenCalled();
});
