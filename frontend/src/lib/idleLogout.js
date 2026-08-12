/**
 * Sign a person out after a stretch of doing nothing.
 *
 * Reported 2026-08-12: a tab opened long earlier, signed in as the management head,
 * simply refreshed instead of asking for the password again. The reason was not that
 * one profile was exempt - NOTHING was ever signing anybody out. The Settings screen
 * offered a "Session timeout" dropdown reading 30 min / 1 hour / 2 hours, and that
 * control saved nothing and nothing read it. A sign-in lasted seven days and renewed
 * itself quietly in the background.
 *
 * A control that claims a protection which does not exist is worse than no control:
 * it is read as a decision already taken. Abhimanyu's decision on 2026-08-12 was one
 * hour, for every profile including the school's owner.
 *
 * How it works, and why it is done this way:
 *
 *  - The deadline is a TIMESTAMP written down, not a countdown running in memory.
 *    A laptop that sleeps for two hours stops its timers; on waking, a countdown
 *    would happily resume with time left. Comparing against a stored moment means
 *    sleep, hibernation and a closed lid all count as idle, which is the whole point.
 *
 *  - The deadline lives in localStorage, so every open tab shares one clock. Working
 *    in one tab keeps the others alive, and signing out closes all of them. Two tabs
 *    with independent timers would sign a person out of one window while they typed
 *    in the next.
 *
 *  - It only ever ENDS a session early. It cannot extend one: the server's own seven
 *    day limit still applies underneath and is untouched by anything here.
 */

export const IDLE_DEADLINE_KEY = 'eduflow.idleDeadline';
export const IDLE_MINUTES_KEY = 'eduflow.idleMinutes';

/** The choices offered in Settings, and the one that applies unless changed. */
export const IDLE_CHOICES = [30, 60, 120];
export const DEFAULT_IDLE_MINUTES = 60;

/** Activity that counts as somebody being at the machine. */
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart', 'visibilitychange'];

/** How often the deadline is checked. Loose on purpose: this is not a stopwatch. */
const CHECK_EVERY_MS = 15_000;

/** Bunch up activity so a burst of typing writes to storage once, not once per key. */
const WRITE_AT_MOST_EVERY_MS = 5_000;

export function readIdleMinutes(storage = window.localStorage) {
  const raw = Number(storage.getItem(IDLE_MINUTES_KEY));
  return IDLE_CHOICES.includes(raw) ? raw : DEFAULT_IDLE_MINUTES;
}

export function writeIdleMinutes(minutes, storage = window.localStorage) {
  if (!IDLE_CHOICES.includes(Number(minutes))) return readIdleMinutes(storage);
  storage.setItem(IDLE_MINUTES_KEY, String(minutes));
  return Number(minutes);
}

/**
 * Start watching. Returns a function that stops watching and clears the deadline.
 *
 * `onIdle` is called at most once per start, so a slow sign-out cannot be triggered
 * twice by the timer firing again while the first one is still going.
 */
export function startIdleWatch({
  onIdle,
  storage = window.localStorage,
  now = () => Date.now(),
  minutes = null,
} = {}) {
  const limitMs = () => (minutes || readIdleMinutes(storage)) * 60 * 1000;
  let firedAlready = false;
  let lastWriteAt = 0;

  const extend = (force = false) => {
    const at = now();
    if (!force && at - lastWriteAt < WRITE_AT_MOST_EVERY_MS) return;
    lastWriteAt = at;
    storage.setItem(IDLE_DEADLINE_KEY, String(at + limitMs()));
  };

  const expired = () => {
    const deadline = Number(storage.getItem(IDLE_DEADLINE_KEY));
    // A missing or unreadable deadline is treated as "not idle" and a fresh one is
    // written. Failing the other way would sign people out the moment storage was
    // cleared by anything at all, which is a worse failure than a late sign-out.
    if (!Number.isFinite(deadline) || deadline <= 0) {
      extend(true);
      return false;
    }
    return now() >= deadline;
  };

  const check = () => {
    if (firedAlready) return;
    if (!expired()) return;
    firedAlready = true;
    storage.removeItem(IDLE_DEADLINE_KEY);
    onIdle();
  };

  const onActivity = () => {
    // A tab being hidden is not activity, and must not push the deadline back -
    // otherwise minimising the window would keep the session alive indefinitely.
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
    if (firedAlready) return;
    extend();
    check();
  };

  extend(true);
  ACTIVITY_EVENTS.forEach(name => window.addEventListener(name, onActivity, { passive: true }));
  const timer = setInterval(check, CHECK_EVERY_MS);

  return function stopIdleWatch() {
    clearInterval(timer);
    ACTIVITY_EVENTS.forEach(name => window.removeEventListener(name, onActivity));
    storage.removeItem(IDLE_DEADLINE_KEY);
  };
}
