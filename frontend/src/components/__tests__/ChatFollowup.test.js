import { fireEvent, render, screen } from '@testing-library/react';
import ChatFollowup, { toolFromDeepLink } from '../ChatFollowup';

describe('toolFromDeepLink', () => {
  test('extracts the tool query param', () => {
    expect(toolFromDeepLink('/app?tool=fees')).toBe('fees');
    expect(toolFromDeepLink('/app?tool=fee-collection&x=1')).toBe('fee-collection');
  });
  test('returns null for malformed/empty input', () => {
    expect(toolFromDeepLink('')).toBeNull();
    expect(toolFromDeepLink(null)).toBeNull();
    expect(toolFromDeepLink('/app')).toBeNull();
  });
});

test('renders nothing when no followup', () => {
  const { container } = render(<ChatFollowup followup={null} />);
  expect(container).toBeEmptyDOMElement();
});

// ── I.3: disambiguation options ─────────────────────────────────────────────

const disambig = {
  kind: 'disambiguation',
  message: "Multiple students match 'Rahul' — please pick one.",
  options: [
    { label: 'Rahul Kumar — Adm 2024-001', value: '2024-001' },
    { label: 'Rahul Singh — Adm 2024-002', value: '2024-002' },
  ],
};

test('I.3 renders selectable disambiguation options', () => {
  render(<ChatFollowup followup={disambig} />);
  expect(screen.getByTestId('chat-disambiguation')).toBeInTheDocument();
  expect(screen.getByText(/Multiple students match/)).toBeInTheDocument();
  expect(screen.getByTestId('disambiguation-option-0')).toHaveTextContent('Rahul Kumar — Adm 2024-001');
  expect(screen.getByTestId('disambiguation-option-1')).toHaveTextContent('Rahul Singh — Adm 2024-002');
});

test('I.3 picking an option fires onPick with the chosen candidate (continues the flow)', () => {
  const onPick = jest.fn();
  render(<ChatFollowup followup={disambig} onPick={onPick} />);
  fireEvent.click(screen.getByTestId('disambiguation-option-1'));
  expect(onPick).toHaveBeenCalledTimes(1);
  expect(onPick.mock.calls[0][0]).toEqual({ label: 'Rahul Singh — Adm 2024-002', value: '2024-002' });
});

test('I.3 disambiguation with no options renders nothing (no dead-end card)', () => {
  const { container } = render(
    <ChatFollowup followup={{ kind: 'disambiguation', message: 'x', options: [] }} />
  );
  expect(container).toBeEmptyDOMElement();
});

test('I.3 picking a value-less option does not call onPick send path', () => {
  const onPick = jest.fn();
  render(
    <ChatFollowup
      followup={{ kind: 'disambiguation', message: 'x', options: [{ label: 'Only label', value: '' }] }}
      onPick={onPick}
    />
  );
  fireEvent.click(screen.getByTestId('disambiguation-option-0'));
  // onPick still fires (parent decides), but the parent guard (tested via
  // ChatInterface) won't send. Here we assert the option is rendered & clickable.
  expect(onPick).toHaveBeenCalledTimes(1);
  expect(onPick.mock.calls[0][0].value).toBe('');
});

// ── I.3: deep-link fallback ─────────────────────────────────────────────────

const deeplink = {
  kind: 'deeplink',
  message: "I couldn't complete that here.",
  url: '/app?tool=fee-collection',
};

test('I.3 renders a deep-link to the matching panel', () => {
  render(<ChatFollowup followup={deeplink} />);
  expect(screen.getByTestId('chat-deeplink')).toBeInTheDocument();
  expect(screen.getByTestId('deeplink-open-panel')).toHaveTextContent(/fee collection/i);
});

test('I.3 clicking the deep-link opens the parsed panel', () => {
  const onOpenPanel = jest.fn();
  render(<ChatFollowup followup={deeplink} onOpenPanel={onOpenPanel} />);
  fireEvent.click(screen.getByTestId('deeplink-open-panel'));
  expect(onOpenPanel).toHaveBeenCalledWith('fee-collection');
});
