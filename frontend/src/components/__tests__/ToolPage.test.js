import { fireEvent, render, screen } from '@testing-library/react';
import { DataTable, ErrorCard } from '../tools/ToolPage';

test('DataTable shows loading placeholder instead of empty state', () => {
  render(<DataTable headers={['Name']} rows={[]} loading emptyMsg="No rows" />);
  expect(screen.getByRole('status')).toHaveTextContent(/loading data/i);
  expect(screen.queryByText('No rows')).not.toBeInTheDocument();
});

test('DataTable shows empty state when not loading', () => {
  render(<DataTable headers={['Name']} rows={[]} emptyMsg="No rows" />);
  expect(screen.getByText('No rows')).toBeInTheDocument();
});

test('ErrorCard calls retry handler', () => {
  const retry = jest.fn();
  render(<ErrorCard message="Failed" onRetry={retry} />);
  fireEvent.click(screen.getByRole('button', { name: /retry/i }));
  expect(retry).toHaveBeenCalledTimes(1);
});
