import { fireEvent, render, screen } from '@testing-library/react';
import ErrorBoundary from '../ErrorBoundary';

let shouldThrow = true;

function ThrowingChild() {
  if (shouldThrow) throw new Error('render failed');
  return <div>Recovered panel</div>;
}

beforeEach(() => {
  shouldThrow = true;
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('shows named contained fallback and can reset the panel', () => {
  const onError = jest.fn();
  render(
    <ErrorBoundary name="FeeCollection" onError={onError}>
      <ThrowingChild />
    </ErrorBoundary>,
  );

  expect(screen.getByText((_, node) => node?.textContent === 'Something went wrong in FeeCollection')).toBeInTheDocument();
  expect(onError).toHaveBeenCalledTimes(1);

  shouldThrow = false;
  fireEvent.click(screen.getByRole('button', { name: /reload this panel/i }));
  expect(screen.getByText('Recovered panel')).toBeInTheDocument();
});
