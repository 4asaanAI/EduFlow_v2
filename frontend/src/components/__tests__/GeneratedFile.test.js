/**
 * UI Sweep Epic 10, Story 10.3 — a file Flo made, as something you can tap.
 */
import { render, screen } from '@testing-library/react';
import { GeneratedFile } from '../MessageRenderer';

jest.mock('../../contexts/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));

const block = {
  type: 'file',
  file_name: 'principals-circular.docx',
  doc_type: 'docx',
  size_kb: 14,
  download_url: 'https://s3.example/aaryans-joya/uploads/x/x.docx?signed=1',
};

test('the file shows its name, type and size, and a download control', () => {
  render(<GeneratedFile block={block} />);

  expect(screen.getByText('principals-circular.docx')).toBeInTheDocument();
  expect(screen.getByText(/DOCX/)).toBeInTheDocument();
  expect(screen.getByText(/14 KB/)).toBeInTheDocument();

  const link = screen.getByTestId('generated-file-download');
  expect(link).toHaveAttribute('href', block.download_url);
  expect(link).toHaveAttribute('download', 'principals-circular.docx');
});

test('the file type is readable as text, not conveyed by colour alone', () => {
  // WCAG colour-not-only. Also the thing the owner reads on a phone.
  render(<GeneratedFile block={block} />);
  expect(screen.getByTestId('generated-file').textContent).toMatch(/DOCX/);
});

test('an expired link says so instead of failing silently on tap', () => {
  // The presigned URL expires, so an old conversation holds dead links. A tap that
  // does nothing is Epic 4's defect in a new place.
  render(<GeneratedFile block={{ ...block, download_url: '' }} />);

  expect(screen.getByTestId('generated-file-expired')).toBeInTheDocument();
  expect(screen.getByText(/expired/i)).toBeInTheDocument();
  expect(screen.queryByTestId('generated-file-download')).not.toBeInTheDocument();
});

test.each([
  'javascript:alert(1)',
  'data:text/html,<script>alert(1)</script>',
  'file:///etc/passwd',
  'vbscript:msgbox(1)',
])('a non-http link (%s) is never made clickable', (bad) => {
  // Rich blocks are authored by the model. A dangerous scheme must not become a
  // click target just because it arrived in a block.
  render(<GeneratedFile block={{ ...block, download_url: bad }} />);

  expect(screen.queryByTestId('generated-file-download')).not.toBeInTheDocument();
  expect(screen.getByTestId('generated-file-expired')).toBeInTheDocument();
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
});
