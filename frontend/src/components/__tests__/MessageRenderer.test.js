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
});

test('strips style and class attributes from AI-rendered content', () => {
  const { container } = render(
    <MessageRenderer
      message={{
        role: 'assistant',
        content: '<span class="danger" style="background:url(javascript:alert(1))">Warning</span>',
      }}
    />,
  );
  const rendered = screen.getByText('Warning');
  expect(rendered).not.toHaveAttribute('style');
  expect(rendered).not.toHaveAttribute('class');
  expect(container.querySelector('[style*="javascript"]')).toBeNull();
});
