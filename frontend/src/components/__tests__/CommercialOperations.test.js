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
    else if (url.includes('/commercial/summary')) data = { totals: { net_sales_paise: 0, weighted_pipeline_paise: 0 } };
    else if (url.includes('/commercial/products')) data = [{ id: 'product-1', name: 'Notebook', unit_price_paise: 1000, tax_rate_bps: 0 }];
    else if (url.includes('/commercial/pos/shifts')) data = [{ id: 'shift-1', shift_number: 'SHIFT-1', cashier_id: 'principal-1', status: 'open' }];
    else if (url.includes('/campus/inventory/items')) data = [{ id: 'item-1', name: 'Notebook', sku: 'NOTE', on_hand: 10 }];
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

test('principal sees CRM lifecycle and multi-line split-payment retail controls', async () => {
  mockCurrentUser = { id: 'principal-1', role: 'admin', sub_category: 'principal', name: 'Principal' };
  mockEntities = [{ id: 'entity-1', name: 'The Aaryans', is_default: true, is_active: true }];
  render(<CommercialOperations />);
  await waitFor(() => expect(screen.getByRole('tab', { name: 'CRM' })).toBeInTheDocument());
  fireEvent.click(screen.getByRole('tab', { name: 'CRM' }));
  expect(await screen.findByTestId('crm-lead-form')).toBeInTheDocument();
  expect(screen.getByLabelText('Estimated value (₹)')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Retail' }));
  expect(await screen.findByText('Add line')).toBeInTheDocument();
  expect(screen.getByText('Add split payment')).toBeInTheDocument();
});
