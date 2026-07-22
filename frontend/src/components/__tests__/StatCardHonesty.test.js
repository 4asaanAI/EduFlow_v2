/**
 * UI Sweep Epic 4, Story 4.2 — a figure that failed to load must not look like a zero.
 *
 * These assert the text a person actually READS, not that a promise resolved. The
 * previous epic's lesson was that a fixture shaped to match whatever the component
 * currently expects proves nothing.
 */
import { render, screen } from '@testing-library/react';
import { StatCard } from '../tools/ToolPage';

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));

test('a real figure is shown as itself', () => {
  render(<StatCard value="1802" label="ENROLLED STUDENTS" data-testid="c" />);
  expect(screen.getByText('1802')).toBeInTheDocument();
  expect(screen.getByTestId('c')).toHaveAttribute('data-stat-state', 'ok');
});

test('an unavailable figure never renders as a number', () => {
  render(<StatCard value={0} label="TOTAL COLLECTED" state="unavailable" data-testid="c" />);

  expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  expect(screen.queryByText('0')).not.toBeInTheDocument();
  expect(screen.getByText(/not a zero/i)).toBeInTheDocument();
});

test('a never-recorded figure says so rather than showing a blank', () => {
  render(<StatCard value="" label="DATE OF BIRTH" state="not-recorded" data-testid="c" />);

  expect(screen.getByText(/not recorded/i)).toBeInTheDocument();
  expect(screen.getByText(/never filled in/i)).toBeInTheDocument();
});

test('a genuine zero is distinguishable from an unavailable one', () => {
  // The whole battle: the school really has ₹0 collected, because it has one fee
  // record for 1,802 students. He must be able to tell that from a failed request at
  // a glance, on a phone, without hovering anything.
  const { rerender } = render(
    <StatCard value="₹0" label="TOTAL COLLECTED" state="ok" note="1 fee record on file" data-testid="c" />
  );
  const real = screen.getByTestId('c');
  expect(real).toHaveAttribute('data-stat-state', 'ok');
  expect(screen.getByText('₹0')).toBeInTheDocument();
  expect(screen.getByText('1 fee record on file')).toBeInTheDocument();

  rerender(<StatCard value="₹0" label="TOTAL COLLECTED" state="unavailable" data-testid="c" />);
  expect(screen.getByTestId('c')).toHaveAttribute('data-stat-state', 'unavailable');
  expect(screen.queryByText('₹0')).not.toBeInTheDocument();
});

test('the states are told apart by text, not by colour alone', () => {
  // WCAG colour-not-only. A colour-only difference is invisible to a colour-blind
  // reader and to anyone glancing at a phone in a meeting room.
  const { rerender } = render(<StatCard value="5" label="X" state="ok" data-testid="c" />);
  const okText = screen.getByTestId('c').textContent;

  rerender(<StatCard value="5" label="X" state="unavailable" data-testid="c" />);
  const errText = screen.getByTestId('c').textContent;

  expect(okText).not.toEqual(errText);
  expect(errText).toMatch(/unavailable/i);
});
