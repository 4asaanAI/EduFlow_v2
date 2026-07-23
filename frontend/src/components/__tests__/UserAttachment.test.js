/**
 * D-39 — an attached file must show as a compact chip, not dump the whole document
 * into the user's own message bubble. The file text still reaches the model; only the
 * DISPLAY changes.
 */
import { render, screen } from '@testing-library/react';
import MessageRenderer, { splitUserAttachment } from '../MessageRenderer';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../lib/api', () => ({ emitFeedback: jest.fn(), getGeneratedFileLink: jest.fn() }));

const LONG = 'CONTEXT You are an n8n workflow optimization expert '.repeat(20);

describe('splitUserAttachment', () => {
  test('a file-only message yields the filename and no visible text', () => {
    const { text, filename } = splitUserAttachment(`[File attached: notes.txt]\n\n${LONG}`);
    expect(filename).toBe('notes.txt');
    expect(text).toBe('');
  });

  test('typed text plus a file keeps the typed text and drops the file body', () => {
    const { text, filename } = splitUserAttachment(`extract this please\n\n---\n[File attached: plan.txt]\n\n${LONG}`);
    expect(filename).toBe('plan.txt');
    expect(text).toBe('extract this please');
  });

  test('a plain message is returned untouched with no filename', () => {
    const { text, filename } = splitUserAttachment('just a normal message');
    expect(filename).toBeNull();
    expect(text).toBe('just a normal message');
  });
});

describe('MessageRenderer user bubble', () => {
  test('shows an attachment chip and never the dumped document text', () => {
    render(<MessageRenderer message={{ role: 'user', content: `[File attached: New_Build_Prompt.txt]\n\n${LONG}` }} />);
    expect(screen.getByTestId('user-attachment-chip')).toHaveTextContent('New_Build_Prompt.txt');
    // the wall of extracted text must NOT be on screen
    expect(screen.queryByText(/n8n workflow optimization expert/)).not.toBeInTheDocument();
  });

  test('keeps the user typed text alongside the chip', () => {
    render(<MessageRenderer message={{ role: 'user', content: `please summarise\n\n---\n[File attached: doc.txt]\n\n${LONG}` }} />);
    expect(screen.getByText('please summarise')).toBeInTheDocument();
    expect(screen.getByTestId('user-attachment-chip')).toHaveTextContent('doc.txt');
  });

  test('a normal message renders its content and shows no chip', () => {
    render(<MessageRenderer message={{ role: 'user', content: 'show today attendance' }} />);
    expect(screen.getByText('show today attendance')).toBeInTheDocument();
    expect(screen.queryByTestId('user-attachment-chip')).not.toBeInTheDocument();
  });
});
