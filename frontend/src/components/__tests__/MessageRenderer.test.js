import { render, screen } from '@testing-library/react';
import MessageRenderer from '../MessageRenderer';

test('renders assistant markdown smoke test', () => {
  render(<MessageRenderer message={{ role: 'assistant', content: 'Hello **school**' }} />);
  expect(screen.getByTestId('assistant-message')).toHaveTextContent('Hello school');
});

test('strips event handler attributes from generated table HTML', () => {
  const { container } = render(
    <MessageRenderer
      message={{
        role: 'assistant',
        content: '| Name |\n| --- |\n| <img src=x onerror=alert(1)> |',
      }}
    />,
  );
  expect(container.querySelector('[onerror]')).toBeNull();
  expect(container.querySelector('img')).toBeNull(); // img is not in the tag allowlist
});

// R8.4 AC3: markdown now produces real styled ELEMENTS (styled by .prose-chat
// CSS), not plain text. The elements survive the sanitizer; styling is via CSS
// element-selectors, so they carry NO inline style (AI can't inject one either).
test("R8.4 AC3: markdown headings render as elements (styled via CSS, no inline style)", () => {
  const { container } = render(
    <MessageRenderer message={{ role: 'assistant', content: '## Fee Summary' }} />,
  );
  const heading = container.querySelector('h3');
  expect(heading).not.toBeNull();
  expect(heading).toHaveTextContent('Fee Summary');
  expect(heading).not.toHaveAttribute('style');
});

test('R8.4 AC3: markdown tables render as <table> elements', () => {
  const { container } = render(
    <MessageRenderer message={{ role: 'assistant', content: '| Name | Class |\n| --- | --- |\n| Rahul | 5A |' }} />,
  );
  expect(container.querySelector('table')).not.toBeNull();
  expect(container.querySelector('th')).toHaveTextContent('Name');
  expect(container.querySelector('tbody td')).toHaveTextContent('Rahul');
});

// R8.4 AC3: security invariants still hold — AI-authored content cannot inject a
// dangerous protocol via style, an event handler, or borrow a CSS class.
test('R8.4 AC3: dangerous style values, handlers and class hooks are neutralized', () => {
  const { container } = render(
    <MessageRenderer
      message={{
        role: 'assistant',
        content: '<span class="danger" style="background:url(javascript:alert(1))" onclick="x()">Warning</span>',
      }}
    />,
  );
  const rendered = screen.getByText('Warning');
  expect(rendered).not.toHaveAttribute('class');
  expect(rendered).not.toHaveAttribute('onclick');
  expect(container.querySelector('[style*="javascript"]')).toBeNull();
  expect(container.querySelector('[onclick]')).toBeNull();
});

// R8.4 AC3: markdown links get a real, protocol-safe href (was hrefless).
test('R8.4 AC3: safe markdown links render a clickable href, unsafe ones do not', () => {
  const { container } = render(
    <MessageRenderer
      message={{ role: 'assistant', content: 'See [the report](https://example.com/r) now' }}
    />,
  );
  const link = container.querySelector('a');
  expect(link).not.toBeNull();
  expect(link.getAttribute('href')).toBe('https://example.com/r');
  expect(link).toHaveTextContent('the report');
});

test('R8.4 AC3: a javascript: markdown link is not rendered as an anchor', () => {
  const { container } = render(
    <MessageRenderer
      message={{ role: 'assistant', content: 'Click [here](javascript:alert(1))' }}
    />,
  );
  // Either dropped to a span or stripped by DOMPurify — never a javascript: href.
  expect(container.querySelector('a[href^="javascript"]')).toBeNull();
  expect(screen.getByText(/here/)).toBeInTheDocument();
});

// R10.4 AC2: recalled memories used in a reply are disclosed in the "Data used" footer.
test('R10.4 AC2: recalled memories are disclosed in the Data used footer', () => {
  render(
    <MessageRenderer
      message={{
        role: 'assistant',
        content: 'Here is the fee summary.',
        recalled_memories: [{ id: 'm1', text: 'owner prefers concise fee summaries', category: 'preference' }],
      }}
    />,
  );
  const footer = screen.getByTestId('data-used');
  expect(footer).toHaveTextContent('remembered note');
  expect(screen.getByTestId('recalled-memories')).toHaveTextContent('owner prefers concise fee summaries');
});

test('R10.4 AC2: no footer when there are no tools and no recalled memories', () => {
  render(<MessageRenderer message={{ role: 'assistant', content: 'plain reply' }} />);
  expect(screen.queryByTestId('data-used')).toBeNull();
});

test('R10.4 AC2: footer shows both tool count and remembered notes', () => {
  render(
    <MessageRenderer
      message={{
        role: 'assistant',
        content: 'done',
        tool_calls: [{ tool: 'get_fee_summary', result: { meta: { count: 3 } } }],
        recalled_memories: [{ id: 'm1', text: 'note one', category: 'fact' }],
      }}
    />,
  );
  const footer = screen.getByTestId('data-used');
  expect(footer).toHaveTextContent('1 tool');
  expect(footer).toHaveTextContent('1 remembered note');
});
