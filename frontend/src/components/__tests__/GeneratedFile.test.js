/**
 * UI Sweep Epic 10, Story 10.3 — a file Flo made, as something you can tap.
 *
 * D-37: the chat message now carries only a short opaque `file_id`. The download
 * button exchanges it for a fresh, short-lived link server-side when tapped, so the
 * ~1,200-character signed URL never travels through the model and can never be stale.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GeneratedFile } from '../MessageRenderer';
import { getGeneratedFileLink } from '../../lib/api';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
jest.mock('../../lib/api', () => ({
  emitFeedback: jest.fn(),
  getGeneratedFileLink: jest.fn(),
}));

const block = {
  type: 'file',
  file_name: 'principals-circular.docx',
  doc_type: 'docx',
  size_kb: 14,
  file_id: 'b1c2d3e4-1111-2222-3333-444455556666',
};

beforeEach(() => {
  jest.clearAllMocks();
  window.open = jest.fn();
});

test('the file shows its name, type and size, and a download control', () => {
  render(<GeneratedFile block={block} />);

  expect(screen.getByText('principals-circular.docx')).toBeInTheDocument();
  expect(screen.getByText(/DOCX/)).toBeInTheDocument();
  expect(screen.getByText(/14 KB/)).toBeInTheDocument();
  expect(screen.getByTestId('generated-file-download')).toBeInTheDocument();
});

test('the file type is readable as text, not conveyed by colour alone', () => {
  // WCAG colour-not-only. Also the thing the owner reads on a phone.
  render(<GeneratedFile block={block} />);
  expect(screen.getByTestId('generated-file').textContent).toMatch(/DOCX/);
});

test('tapping download fetches a fresh link by file_id and opens it', async () => {
  // The signed URL is minted at tap time and never carried in the message (D-37).
  getGeneratedFileLink.mockResolvedValue({
    success: true,
    data: { download_url: 'https://s3.example/aaryans-joya/uploads/x/x.docx?signed=fresh' },
  });

  render(<GeneratedFile block={block} />);
  fireEvent.click(screen.getByTestId('generated-file-download'));

  await waitFor(() => expect(getGeneratedFileLink).toHaveBeenCalledWith(block.file_id));
  await waitFor(() =>
    expect(window.open).toHaveBeenCalledWith(
      'https://s3.example/aaryans-joya/uploads/x/x.docx?signed=fresh',
      '_blank',
      'noopener,noreferrer',
    ),
  );
});

test('a fetch that fails says so instead of failing silently', async () => {
  // A tap that does nothing is Epic 4's defect in a new place. A missing or forbidden
  // file (the endpoint throws) must turn into a plain "ask again", not a dead button.
  getGeneratedFileLink.mockRejectedValue(new Error('404'));

  render(<GeneratedFile block={block} />);
  fireEvent.click(screen.getByTestId('generated-file-download'));

  expect(await screen.findByTestId('generated-file-expired')).toBeInTheDocument();
  expect(screen.getByText(/expired|again/i)).toBeInTheDocument();
  expect(window.open).not.toHaveBeenCalled();
});

test.each([
  'javascript:alert(1)',
  'data:text/html,<script>alert(1)</script>',
  'file:///etc/passwd',
  'vbscript:msgbox(1)',
])('a non-http link (%s) from the server is never opened', async (bad) => {
  // Even a URL that came back from our own endpoint is checked before it is opened.
  getGeneratedFileLink.mockResolvedValue({ success: true, data: { download_url: bad } });

  render(<GeneratedFile block={block} />);
  fireEvent.click(screen.getByTestId('generated-file-download'));

  expect(await screen.findByTestId('generated-file-expired')).toBeInTheDocument();
  expect(window.open).not.toHaveBeenCalled();
});

test('an old block with a raw download_url and no file_id is treated as expired', async () => {
  // Backwards compatibility: conversations from before D-37 hold a raw (now dead)
  // presigned URL and no file_id. Following it would render S3's XML error page with
  // the school's account number on screen, so the card refuses and asks for a fresh one.
  render(<GeneratedFile block={{
    type: 'file', file_name: 'old.docx', doc_type: 'docx', size_kb: 9,
    download_url: 'https://s3.example/old/expired.docx?signed=stale',
  }} />);

  expect(screen.getByTestId('generated-file-expired')).toBeInTheDocument();
  expect(screen.queryByTestId('generated-file-download')).not.toBeInTheDocument();
  expect(getGeneratedFileLink).not.toHaveBeenCalled();
});

test('a hostile file name is shown as text, never as markup', () => {
  render(<GeneratedFile block={{ ...block, file_name: '<img src=x onerror=alert(1)>.docx' }} />);

  const card = screen.getByTestId('generated-file');
  expect(card.querySelector('img')).toBeNull();
  expect(card.textContent).toContain('<img src=x onerror=alert(1)>.docx');
});

test('a block with missing details still renders without throwing', () => {
  render(<GeneratedFile block={{ type: 'file' }} />);
  expect(screen.getByTestId('generated-file')).toBeInTheDocument();
  expect(screen.getByText('document')).toBeInTheDocument();
  // No file_id → nothing to fetch → the honest "ask again" state, not a dead button.
  expect(screen.getByTestId('generated-file-expired')).toBeInTheDocument();
});
