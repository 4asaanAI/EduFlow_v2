import { initialsOf, userInitials } from '../initials';

// Owner report 2026-08-07: the principal's badge read "PS" beside "ADESH SINGH".

describe('initialsOf', () => {
  it.each([
    ['ADESH SINGH', 'AS'],
    ['Accountant', 'A'],
    ['Transport Desk', 'TD'],
    ['Reception Desk', 'RD'],
    ['IT Desk', 'ID'],
    ['Maintenance Desk', 'MD'],
    ['Management Desk', 'MD'],
  ])('derives %s -> %s', (name, expected) => {
    expect(initialsOf(name)).toBe(expected);
  });

  it('ignores a title so a doctor badges by their own name', () => {
    expect(initialsOf('DR PERMENDRA KUMAR')).toBe('PK');
    expect(initialsOf('Dr. Permendra Kumar')).toBe('PK');
  });

  it('handles a single name', () => {
    expect(initialsOf('DEEPANSHI')).toBe('D');
  });

  it('takes only the first two words', () => {
    expect(initialsOf('Anjali Chaudhary Devi')).toBe('AC');
  });

  it('copes with extra spacing', () => {
    expect(initialsOf('  ADESH   SINGH  ')).toBe('AS');
  });

  it('shows a question mark rather than nothing when there is no name', () => {
    expect(initialsOf('')).toBe('?');
    expect(initialsOf(null)).toBe('?');
    expect(initialsOf(undefined)).toBe('?');
  });
});

describe('userInitials', () => {
  it('ignores the stale stored value and follows the name', () => {
    expect(userInitials({ name: 'ADESH SINGH', initials: 'PS' })).toBe('AS');
  });

  it('falls back to the stored value only when there is no name', () => {
    expect(userInitials({ name: '', initials: 'PS' })).toBe('PS');
  });

  it('never renders blank', () => {
    expect(userInitials({})).toBe('?');
    expect(userInitials(null)).toBe('?');
  });
});
