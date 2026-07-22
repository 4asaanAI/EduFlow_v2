/**
 * Ordering for school classes.
 *
 * Classes come back from the API in insertion order, which is effectively random
 * ("11th-A, 1st-A, 2nd-C, 2nd-E, 3rd-A, … LKG-A, NUR-D, 11th-B …"). A plain
 * alphabetical sort is no better — it puts 10th, 11th and 12th before 1st, and
 * scatters the pre-primary classes.
 *
 * The Aaryans runs NUR → LKG → UKG → 1st … 12th, each with sections A-E.
 * This is the single place that ordering lives; every class dropdown and every
 * class-grouped table should sort through here so they all agree.
 */

// Pre-primary comes before class 1 and has no numeric form of its own.
const PRE_PRIMARY = {
  NUR: -3, NURSERY: -3, PRE_NUR: -4, PRENUR: -4,
  LKG: -2,
  UKG: -1,
};

/**
 * A sortable rank for a class name like "NUR", "LKG", "1st", "10th", "XII".
 * Unknown values sort last rather than throwing, so a stray record never breaks
 * a dropdown.
 */
export function classRank(name) {
  if (!name) return Number.MAX_SAFE_INTEGER;
  const key = String(name).trim().toUpperCase().replace(/[\s.-]+/g, '_');

  if (key in PRE_PRIMARY) return PRE_PRIMARY[key];

  // "1st", "10th", "Class 8", "8" → 1, 10, 8, 8
  const arabic = key.match(/(\d+)/);
  if (arabic) return parseInt(arabic[1], 10);

  // Roman numerals, as used on the school's own paperwork ("III-A", "XII Sci")
  const roman = key.match(/^(X{0,3})(IX|IV|V?I{0,3})/);
  if (roman && (roman[1] || roman[2])) {
    const map = { I: 1, V: 5, X: 10 };
    const s = roman[1] + roman[2];
    let total = 0;
    for (let i = 0; i < s.length; i += 1) {
      const cur = map[s[i]];
      const next = map[s[i + 1]];
      total += next && cur < next ? -cur : cur;
    }
    if (total > 0) return total;
  }

  return Number.MAX_SAFE_INTEGER;
}

/** Compare two {name, section} class records. */
export function compareClasses(a, b) {
  const rank = classRank(a?.name) - classRank(b?.name);
  if (rank !== 0) return rank;
  // Same class: order sections A, B, C…
  const sa = String(a?.section ?? '').toUpperCase();
  const sb = String(b?.section ?? '').toUpperCase();
  if (sa !== sb) return sa < sb ? -1 : 1;
  // Last resort so the order is stable rather than arbitrary
  return String(a?.name ?? '').localeCompare(String(b?.name ?? ''));
}

/** Returns a new array of class records in school order. Never mutates the input. */
export function sortClasses(classes) {
  return Array.isArray(classes) ? [...classes].sort(compareClasses) : [];
}

/** Display label for a class record: "10th-A". */
export function classLabel(c) {
  if (!c) return '';
  return c.section ? `${c.name}-${c.section}` : String(c.name ?? '');
}

/**
 * Sort arbitrary rows that carry a class label in a single string field,
 * e.g. the Class Strength table's "10th-A" rows.
 */
export function compareClassLabels(a, b) {
  const split = (v) => {
    const s = String(v ?? '').trim();
    const i = s.lastIndexOf('-');
    return i > 0 ? { name: s.slice(0, i), section: s.slice(i + 1) } : { name: s, section: '' };
  };
  return compareClasses(split(a), split(b));
}
