import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CommercialOperations from '../tools/CommercialOperations';

let mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner' };
let mockEntities = [];

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockCurrentUser }),
}));

jest.mock('../../lib/authSession', () => ({ getAuthHeaders: () => ({}) }));

jest.mock('../../lib/api', () => ({
  API: '',
  apiFetch: async (url) => {
    let data = [];
    if (url.includes('/commercial/entities')) data = mockEntities;
    else if (url.includes('/commercial/summary')) data = { totals: { weighted_pipeline_paise: 0 } };
    return { ok: true, json: async () => ({ success: true, data }) };
  },
}));

beforeEach(() => {
  mockCurrentUser = { id: 'owner-1', role: 'owner', name: 'Owner' };
  mockEntities = [];
});

test('owner can bootstrap the first legal entity without an endless loader', async () => {
  render(<CommercialOperations />);
  fireEvent.click(await screen.findByRole('tab', { name: 'Entities' }));
  expect(await screen.findByText('No legal entities configured')).toBeInTheDocument();
  expect(screen.getByLabelText('Legal name')).toBeInTheDocument();
});

test('principal sees the CRM lifecycle', async () => {
  mockCurrentUser = { id: 'principal-1', role: 'admin', sub_category: 'principal', name: 'Principal' };
  mockEntities = [{ id: 'entity-1', name: 'The Aaryans', is_default: true, is_active: true }];
  render(<CommercialOperations />);
  await waitFor(() => expect(screen.getByRole('tab', { name: 'CRM' })).toBeInTheDocument());
  fireEvent.click(screen.getByRole('tab', { name: 'CRM' }));
  expect(await screen.findByTestId('crm-lead-form')).toBeInTheDocument();
  expect(screen.getByLabelText('Estimated value (₹)')).toBeInTheDocument();
});

test('there is no Retail tab, because the school runs no shop', async () => {
  // Campus retail was removed on 2026-08-14. The canteen is an outside vendor renting
  // space, so the school has a tenant rather than a counter of its own. Asserted rather
  // than left to the absence of the old test: a tab that quietly comes back is exactly
  // the kind of thing nobody notices until somebody types real money into it.
  mockCurrentUser = { id: 'principal-1', role: 'admin', sub_category: 'principal', name: 'Principal' };
  mockEntities = [{ id: 'entity-1', name: 'The Aaryans', is_default: true, is_active: true }];
  render(<CommercialOperations />);
  await waitFor(() => expect(screen.getByRole('tab', { name: 'CRM' })).toBeInTheDocument());
  expect(screen.queryByRole('tab', { name: 'Retail' })).not.toBeInTheDocument();
});
