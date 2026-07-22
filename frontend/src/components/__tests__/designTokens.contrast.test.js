/**
 * The design system's contrast gate — Epic 9, Story 9.1.
 *
 * WHY THIS EXISTS
 *
 * The playful palette was taken from the marketing site (eduflow.layaa.ai), and
 * two of its signature pairings fail WCAG outright:
 *
 *     white on #F2811D (orange)  = 2.65:1
 *     white on #2B8FF0 (blue)    = 3.34:1
 *
 * NFR-A1 requires 4.5:1 for body text. The website carries one huge headline
 * CTA and gets away with it; this app puts 14px labels on hundreds of buttons
 * and does not. So the app deliberately DIVERGES from the brochure:
 * orange fills carry navy text, and the blue fill deepens for white text.
 *
 * That divergence is invisible in a diff and very easy to "tidy" back into a
 * bug — a future change making an orange button's label white would look like
 * a cleanup and would silently break accessibility for every user. This test
 * computes the ratios so that change fails the build instead.
 *
 * Light theme is asserted INDEPENDENTLY of dark (UX-DR2), because a pairing
 * that passes on navy tells you nothing about the same pairing on white.
 */

/* ---- WCAG 2.1 relative luminance and contrast ratio ---- */

function srgbToLinear(channel) {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

export function contrast(fg, bg) {
  const a = luminance(fg);
  const b = luminance(bg);
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

/* Mirrors of the token values. Kept here as literals ON PURPOSE: reading them
   out of the stylesheet would make the test agree with whatever the CSS says,
   which is precisely the thing being guarded. If you change a token, you must
   change it here too — and that is the moment the ratio gets re-checked. */
/* Dark theme is NEUTRAL grey, not navy. The first Epic 9 pass took the
   brochure's navy literally and Abhimanyu reversed it — too much blue. What
   the brochure contributes to dark is the type and the rounded chunky shapes,
   not the background. These greys are the app's original values, with the
   three text weights raised to clear 4.5:1 (#666666 measured 3.03:1). */
const DARK = {
  page: '#141414',
  surface: '#1E1E1E',
  surfaceRaised: '#2A2A2A',
  border: '#4D4D4D',
  borderStrong: '#787878',
  textPrimary: '#F5F5F5',
  textSecondary: '#A8A8A8',
  textMuted: '#8A8A8A',
  accentBlue: '#4F8FF7',
  success: '#34D399',
  danger: '#FB7185',
  warning: '#FBBF24',
  purple: '#A78BFA',
  brandBlueFill: '#1A6FCE',
  brandOrange: '#F2811D',
  onBrandBlue: '#FFFFFF',
  onBrandOrange: '#16203A',
};

const LIGHT = {
  page: '#F4F7FD',
  surface: '#FFFFFF',
  surfaceRaised: '#EEF3FC',
  border: '#D8E2F2',
  borderStrong: '#6E80AE',
  textPrimary: '#16203A',
  textSecondary: '#4A5C84',
  textMuted: '#5A6B95',
  accentBlue: '#1A6FCE',
  success: '#12855C',
  danger: '#D63C56',
  warning: '#965C00',
  purple: '#6D45C7',
  brandBlueFill: '#1A6FCE',
  brandOrange: '#F2811D',
  onBrandBlue: '#FFFFFF',
  onBrandOrange: '#16203A',
};

const BODY_TEXT = 4.5;   // WCAG AA, normal text
const NON_TEXT = 3.0;    // WCAG AA, UI components, borders and large text

describe('contrast ratio helper', () => {
  it('matches the WCAG reference values', () => {
    expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 1);
    expect(contrast('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 5);
  });

  it('is symmetric — order of arguments does not matter', () => {
    expect(contrast('#16203A', '#F2811D')).toBeCloseTo(contrast('#F2811D', '#16203A'), 6);
  });
});

describe.each([['dark', DARK], ['light', LIGHT]])('%s theme', (themeName, T) => {
  describe('body text meets 4.5:1', () => {
    it.each([
      ['primary text on page', 'textPrimary', 'page'],
      ['primary text on card', 'textPrimary', 'surface'],
      ['primary text on raised surface', 'textPrimary', 'surfaceRaised'],
      ['secondary text on page', 'textSecondary', 'page'],
      ['secondary text on card', 'textSecondary', 'surface'],
      ['muted text on page', 'textMuted', 'page'],
      ['muted text on card', 'textMuted', 'surface'],
    ])('%s', (_label, fg, bg) => {
      expect(contrast(T[fg], T[bg])).toBeGreaterThanOrEqual(BODY_TEXT);
    });
  });

  describe('status and accent colours are readable as text', () => {
    it.each([
      ['accent blue', 'accentBlue'],
      ['success', 'success'],
      ['danger', 'danger'],
      ['warning', 'warning'],
      ['purple', 'purple'],
    ])('%s on the card surface', (_label, key) => {
      // These carry words like "overdue" and "present", not just decoration.
      expect(contrast(T[key], T.surface)).toBeGreaterThanOrEqual(BODY_TEXT);
    });
  });

  describe('button labels meet 4.5:1 against their own fill', () => {
    it('primary: white on the DEEPENED blue, not the brand blue', () => {
      expect(contrast(T.onBrandBlue, T.brandBlueFill)).toBeGreaterThanOrEqual(BODY_TEXT);
    });

    it('accent: NAVY on orange — white would be 2.65:1 and must never be used', () => {
      expect(contrast(T.onBrandOrange, T.brandOrange)).toBeGreaterThanOrEqual(BODY_TEXT);
      // The guard rail: prove the tempting "cleanup" is actually a failure.
      expect(contrast('#FFFFFF', T.brandOrange)).toBeLessThan(BODY_TEXT);
    });
  });

  describe('borders and focus rings meet 3:1', () => {
    it('a secondary button is identified by its border, so the border needs 3:1', () => {
      // Not a pedantic assertion. The secondary button's FILL measures only
      // 1.32:1 against the page in dark theme, so the border is what makes the
      // control visible at all — which is exactly the case WCAG 1.4.11 covers.
      // This assertion rejected the original #3A4D7A / #B9C8E4 pair.
      expect(contrast(T.borderStrong, T.page)).toBeGreaterThanOrEqual(NON_TEXT);
      expect(contrast(T.borderStrong, T.surface)).toBeGreaterThanOrEqual(NON_TEXT);
    });

    it('focus ring (brand blue) against the page it is drawn on', () => {
      expect(contrast(T.accentBlue, T.page)).toBeGreaterThanOrEqual(NON_TEXT);
    });

    it('focus ring against the card surface', () => {
      expect(contrast(T.accentBlue, T.surface)).toBeGreaterThanOrEqual(NON_TEXT);
    });
  });
});

describe('the specific brochure pairings this palette refuses to copy', () => {
  it('white on brand orange fails, which is why --on-brand-orange is navy', () => {
    expect(contrast('#FFFFFF', '#F2811D')).toBeLessThan(3.0);
  });

  it('white on brand blue fails body text, which is why the fill is deepened', () => {
    const raw = contrast('#FFFFFF', '#2B8FF0');
    expect(raw).toBeLessThan(BODY_TEXT);
    expect(contrast('#FFFFFF', '#1A6FCE')).toBeGreaterThanOrEqual(BODY_TEXT);
  });

  it('the brochure blue is fine on a dark page but not on white', () => {
    expect(contrast('#2B8FF0', DARK.page)).toBeGreaterThanOrEqual(BODY_TEXT);
    // ...and NOT on white, which is why light theme swaps in the deeper blue.
    expect(contrast('#2B8FF0', '#FFFFFF')).toBeLessThan(BODY_TEXT);
  });

  it('the old muted grey #666 was below the body-text minimum', () => {
    // Recorded so nobody "restores" it as part of a revert. The dark theme
    // went back to grey, but not back to unreadable grey.
    expect(contrast('#666666', DARK.page)).toBeLessThan(BODY_TEXT);
    expect(contrast(DARK.textMuted, DARK.page)).toBeGreaterThanOrEqual(BODY_TEXT);
  });
});
