/**
 * UI Sweep — Flo's face beside every reply, not a star.
 *
 * Abhimanyu reported on 2026-07-22 that the star was still there. The code was
 * already correct; nothing had been deployed. These tests exist so that next time
 * the question "is it the code or the deploy?" is answered in seconds rather than
 * by reading the diff again.
 */
import { render, screen } from '@testing-library/react';
import MessageRenderer from '../MessageRenderer';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: { id: 'u1', role: 'owner', name: 'Aman' } }),
}));

const assistantMessage = {
  role: 'assistant',
  content: 'Attendance today is 91%.',
};

test('an assistant reply shows Flo, not a star', () => {
  render(<MessageRenderer message={assistantMessage} />);

  const avatar = screen.getByTestId('flo-avatar');
  expect(avatar).toBeInTheDocument();
  // The mascot identifies itself to screen readers by name.
  expect(screen.getByLabelText(/Flo, the EduFlow AI assistant/i)).toBeInTheDocument();
});

test('the avatar is the head-only crop, not the whole robot', () => {
  // A full-body robot at 28px is an unreadable smudge, and the float animation
  // repeated down a long conversation is a room full of bobbing heads.
  const { container } = render(<MessageRenderer message={assistantMessage} />);

  const svg = container.querySelector('[data-testid="flo-avatar"] svg');
  expect(svg).toBeTruthy();
  expect(svg.getAttribute('viewBox')).toBe('38 0 164 182');

  // No floating group and no ground shadow in the avatar crop.
  expect(container.querySelector('[data-testid="flo-avatar"] .eh-mascot-float')).toBeNull();
  expect(container.querySelector('[data-testid="flo-avatar"] .eh-mascot-shadow')).toBeNull();
});

test('the full mascot still floats and casts a shadow', () => {
  // Guards the other direction: the avatar crop must not have quietly stripped
  // the animation from the sign-in screen and the chat greeting.
  const BotMascot = require('../ui/BotMascot').default;
  const { container } = render(<BotMascot size={120} data-testid="full-mascot" />);

  const svg = container.querySelector('svg');
  expect(svg.getAttribute('viewBox')).toBe('0 0 240 264');
  expect(container.querySelector('.eh-mascot-float')).toBeTruthy();
  expect(container.querySelector('.eh-mascot-shadow')).toBeTruthy();
});
