import {
  startIdleWatch,
  readIdleMinutes,
  writeIdleMinutes,
  DEFAULT_IDLE_MINUTES,
  IDLE_DEADLINE_KEY,
  IDLE_MINUTES_KEY,
} from '../idleLogout';

// A storage that behaves like localStorage but is thrown away between tests, and
// which several "tabs" can share - the point being that one clock serves them all.
function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: key => map.delete(key),
    _map: map,
  };
}

const MINUTE = 60 * 1000;

describe('signing out after a stretch of doing nothing', () => {
  // Reported 2026-08-12: a tab left open for hours, signed in as the management head,
  // just refreshed. Nothing had ever been signing anybody out; the Settings control
  // that appeared to set a timeout saved nothing and nothing read it.

  afterEach(() => jest.useRealTimers());

  test('an hour of nothing signs the person out', () => {
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });

    clock = 59 * MINUTE;
    jest.advanceTimersByTime(60 * MINUTE);
    expect(onIdle).not.toHaveBeenCalled();

    clock = 60 * MINUTE;
    jest.advanceTimersByTime(MINUTE);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  test('a laptop asleep for two hours counts as two hours idle', () => {
    // This is why the deadline is a written-down moment rather than a countdown.
    // A closed lid stops timers; a countdown would wake up with time still on it and
    // leave the school's records open on an unattended machine.
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });

    clock = 2 * 60 * MINUTE; // the machine was asleep; almost no timers fired
    jest.advanceTimersByTime(MINUTE);

    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  test('working keeps the session alive', () => {
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });

    for (let i = 1; i <= 6; i += 1) {
      clock = i * 30 * MINUTE;
      window.dispatchEvent(new Event('keydown'));
      jest.advanceTimersByTime(30 * MINUTE);
    }

    expect(onIdle).not.toHaveBeenCalled();
  });

  test('every open tab shares one clock, so one tab cannot sign the others out', () => {
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const idleA = jest.fn();
    const idleB = jest.fn();

    startIdleWatch({ onIdle: idleA, storage, now: () => clock });
    startIdleWatch({ onIdle: idleB, storage, now: () => clock });

    // Half an hour later somebody types in one of the tabs. Both tabs read the same
    // stored deadline, so both stay alive.
    clock = 30 * MINUTE;
    window.dispatchEvent(new Event('keydown'));
    jest.advanceTimersByTime(MINUTE);

    clock = 80 * MINUTE; // 50 minutes after the last activity, not 80
    jest.advanceTimersByTime(MINUTE);

    expect(idleA).not.toHaveBeenCalled();
    expect(idleB).not.toHaveBeenCalled();
  });

  test('it only ever fires once, however long the sign-out takes', () => {
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });
    clock = 90 * MINUTE;
    jest.advanceTimersByTime(10 * MINUTE);

    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  test('stopping the watch clears the deadline behind it', () => {
    const storage = makeStorage();
    const stop = startIdleWatch({ onIdle: jest.fn(), storage, now: () => 0 });

    expect(storage.getItem(IDLE_DEADLINE_KEY)).not.toBeNull();
    stop();
    expect(storage.getItem(IDLE_DEADLINE_KEY)).toBeNull();
  });

  test('a missing deadline does not sign anybody out', () => {
    // Storage can be cleared by all sorts of things. Failing this way round means a
    // late sign-out; failing the other way would throw people out mid-sentence.
    jest.useFakeTimers();
    const storage = makeStorage();
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });
    storage.removeItem(IDLE_DEADLINE_KEY);
    jest.advanceTimersByTime(MINUTE);

    expect(onIdle).not.toHaveBeenCalled();
  });
});

describe('the Settings control that used to be decoration', () => {
  test('one hour applies unless somebody chooses otherwise', () => {
    expect(DEFAULT_IDLE_MINUTES).toBe(60);
    expect(readIdleMinutes(makeStorage())).toBe(60);
  });

  test('a chosen value is stored and read back', () => {
    const storage = makeStorage();
    expect(writeIdleMinutes(30, storage)).toBe(30);
    expect(readIdleMinutes(storage)).toBe(30);
    expect(storage.getItem(IDLE_MINUTES_KEY)).toBe('30');
  });

  test('a value that is not on offer is refused, not stored', () => {
    const storage = makeStorage();
    expect(writeIdleMinutes(99999, storage)).toBe(60);
    expect(storage.getItem(IDLE_MINUTES_KEY)).toBeNull();
  });

  test('the chosen value is what the watch actually uses', () => {
    jest.useFakeTimers();
    const storage = makeStorage();
    writeIdleMinutes(30, storage);
    let clock = 0;
    const onIdle = jest.fn();

    startIdleWatch({ onIdle, storage, now: () => clock });
    clock = 31 * MINUTE;
    jest.advanceTimersByTime(MINUTE);

    expect(onIdle).toHaveBeenCalledTimes(1);
    jest.useRealTimers();
  });
});
