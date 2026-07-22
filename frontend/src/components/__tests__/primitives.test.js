/**
 * Shared UI primitives — Epic 9, Story 9.2.
 *
 * These guard the two rules that are easiest to break by accident, because
 * breaking either LOOKS like a tidy-up:
 *   1. an orange button's label must stay navy (white measures 2.65:1);
 *   2. the press must move `transform` only, never a layout property.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button, Pill, EmptyState, Field, VARIANTS } from '../ui/primitives';

describe('Button — contrast contract', () => {
  // Asserted against the VARIANTS map, not the rendered DOM. jsdom's CSS
  // parser silently drops `color` and `background` when the value is a
  // `var()`, so a rendered button reports neither and a DOM assertion would
  // pass vacuously. The map is the actual decision being guarded; the tokens'
  // real values are proved separately by designTokens.contrast.test.js.

  it('gives the orange fill its NAVY label token, never white', () => {
    // White on #F2811D is 2.65:1 and fails NFR-A1. Making this label white
    // would look like a cleanup and would be an accessibility regression.
    expect(VARIANTS.accent.background).toBe('var(--brand-orange)');
    expect(VARIANTS.accent.color).toBe('var(--on-brand-orange)');
    expect(VARIANTS.accent.color).not.toMatch(/#fff|white/i);
  });

  it('uses the DEEPENED blue fill for a white label', () => {
    expect(VARIANTS.primary.background).toBe('var(--brand-blue-fill)');
    expect(VARIANTS.primary.color).toBe('var(--on-brand-blue)');
    // Never the raw brand blue, which is only 3.34:1 against white.
    expect(VARIANTS.primary.background).not.toContain('#2B8FF0');
  });

  it('no variant hard-codes a colour — every one goes through a token', () => {
    for (const [name, v] of Object.entries(VARIANTS)) {
      for (const key of ['background', 'color']) {
        expect(`${name}.${key}: ${v[key]}`).not.toMatch(/#[0-9a-f]{3,8}/i);
      }
    }
  });
});

describe('Button — the press never reflows the row', () => {
  it('moves with transform, and leaves layout properties untouched', () => {
    render(<Button data-testid="b">Press</Button>);
    const el = screen.getByTestId('b');

    expect(el).toHaveStyle({ transform: 'translateY(0)' });
    fireEvent.mouseDown(el);
    // The only thing that moved.
    expect(el.style.transform).toBe('translateY(3px)');
    // Nothing that would push its neighbours around.
    expect(el.style.top).toBe('');
    expect(el.style.marginTop).toBe('');
    expect(el.style.height).toBe('');

    fireEvent.mouseUp(el);
    expect(el.style.transform).toBe('translateY(0)');
  });

  it('springs back if the pointer leaves mid-press', () => {
    render(<Button data-testid="b">Press</Button>);
    const el = screen.getByTestId('b');
    fireEvent.mouseDown(el);
    fireEvent.mouseLeave(el);
    expect(el.style.transform).toBe('translateY(0)');
  });

  it('responds to the keyboard, so it is not a mouse-only affordance', () => {
    render(<Button data-testid="b">Press</Button>);
    const el = screen.getByTestId('b');
    fireEvent.keyDown(el, { key: 'Enter' });
    expect(el.style.transform).toBe('translateY(3px)');
    fireEvent.keyUp(el, { key: 'Enter' });
    expect(el.style.transform).toBe('translateY(0)');
  });

  it('does not depress when disabled', () => {
    render(<Button disabled data-testid="b">Press</Button>);
    const el = screen.getByTestId('b');
    fireEvent.mouseDown(el);
    expect(el.style.transform).toBe('translateY(0)');
  });
});

describe('Button — disabled is more than a colour', () => {
  it('carries the real disabled attribute, not just a faded style', () => {
    render(<Button disabled data-testid="b">Press</Button>);
    expect(screen.getByTestId('b')).toBeDisabled();
  });

  it('drops the shadow, so it visibly stops looking pressable', () => {
    render(<Button disabled data-testid="b">Press</Button>);
    expect(screen.getByTestId('b')).toHaveStyle({ boxShadow: 'none' });
  });

  it('does not fire its handler', () => {
    const onClick = jest.fn();
    render(<Button disabled onClick={onClick} data-testid="b">Press</Button>);
    fireEvent.click(screen.getByTestId('b'));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('every primitive forwards data-testid (UX-DR4)', () => {
  it.each([
    ['Button', <Button data-testid="x">a</Button>],
    ['Pill', <Pill data-testid="x">a</Pill>],
    ['EmptyState', <EmptyState data-testid="x" />],
  ])('%s', (_name, node) => {
    render(node);
    expect(screen.getByTestId('x')).toBeInTheDocument();
  });
});

describe('EmptyState tells the three cases apart', () => {
  it('"not recorded" is not the same as "no data yet"', () => {
    const { unmount } = render(<EmptyState kind="not-recorded" />);
    expect(screen.getByText('Not recorded')).toBeInTheDocument();
    unmount();
    render(<EmptyState kind="empty" />);
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
  });

  it('a failure is announced as an alert; an empty list is not', () => {
    const { unmount } = render(<EmptyState kind="error" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    unmount();
    render(<EmptyState kind="empty" />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('falls back to the neutral copy for an unknown kind rather than blanking', () => {
    render(<EmptyState kind="something-else" />);
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
  });
});

describe('Field', () => {
  it('renders a real label bound to its control, not a placeholder', () => {
    render(
      <Field label="Phone" htmlFor="phone">
        <input id="phone" />
      </Field>
    );
    expect(screen.getByLabelText('Phone')).toBe(document.getElementById('phone'));
  });
});
