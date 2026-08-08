import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import Login from '../Login';
import { useUser } from '../../contexts/UserContext';

jest.mock('../../contexts/UserContext', () => ({ useUser: jest.fn() }));
jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}));
jest.mock('../ui/BotMascot', () => function MockBotMascot() {
  return <div data-testid="login-mascot" />;
});

describe('Login', () => {
  test('shows and hides the password without changing its value', () => {
    useUser.mockReturnValue({ loginPassword: jest.fn() });
    render(<Login />);

    const password = screen.getByTestId('login-password');
    const toggle = screen.getByRole('button', { name: 'Show password' });
    fireEvent.change(password, { target: { value: 'Secret123!' } });

    expect(password).toHaveAttribute('type', 'password');
    fireEvent.click(toggle);
    expect(password).toHaveAttribute('type', 'text');
    expect(password).toHaveValue('Secret123!');
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  test('shows the normalized incorrect-credentials message', async () => {
    const loginPassword = jest.fn().mockRejectedValue(
      new Error('Incorrect username or password'),
    );
    useUser.mockReturnValue({ loginPassword });
    render(<Login />);

    fireEvent.change(screen.getByTestId('login-username'), { target: { value: 'adesh.singh' } });
    fireEvent.change(screen.getByTestId('login-password'), { target: { value: 'wrong-password' } });
    fireEvent.click(screen.getByTestId('login-submit'));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(
      'Incorrect username or password',
    ));
  });
});
