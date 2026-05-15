const DRAFT_PREFIX = 'attendance_draft_';
const DRAFT_TTL_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

function parseDraftDate(key) {
  const match = key.match(/(\d{4}-\d{2}-\d{2})$/);
  if (!match) return null;
  const time = new Date(`${match[1]}T00:00:00`).getTime();
  return Number.isNaN(time) ? null : time;
}

export function purgeExpiredAttendanceDrafts(now = new Date()) {
  let purged = 0;
  const nowMs = now.getTime();
  try {
    Object.keys(localStorage)
      .filter(key => key.startsWith(DRAFT_PREFIX))
      .forEach(key => {
        const draftTime = parseDraftDate(key);
        if (draftTime == null) return;
        if ((nowMs - draftTime) / DAY_MS > DRAFT_TTL_DAYS) {
          localStorage.removeItem(key);
          purged += 1;
        }
      });
  } catch {}
  if (purged > 0) console.debug(`Purged ${purged} expired attendance draft key${purged === 1 ? '' : 's'}`);
  return purged;
}
