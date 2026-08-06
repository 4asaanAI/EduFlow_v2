/**
 * Old tool names that now point at a screen reachable under another name (D-44 part 2).
 *
 * `fee-receipts` and `fee-collection` were never two screens — both loaded
 * `components/tools/FeeCollection`, and the school's owner was offered BOTH of them,
 * in the same sidebar, under two different names. Retiring the duplicate name is the
 * merge; this map is what stops it from breaking anything that still says the old
 * name: a bookmarked `?tool=fee-receipts`, a notification deep link, or Flo being
 * asked "open fee receipts".
 *
 * Resolution happens in exactly one place — `Layout` reads the URL through
 * `resolveToolId` — so every way in (deep link, ⌘K, sidebar, the `open-tool` event,
 * a notification) gets the same answer. Do NOT add a second alias map anywhere; four
 * hand-kept copies of the tool list is how these registries drifted apart before.
 *
 * Rule for adding to this map: the old name must go, in the same change, from every
 * menu that offers it. This map is for names still in circulation OUTSIDE the app,
 * not a way to keep a dead entry alive inside it. `ToolMerge.test.js` enforces both.
 */
export const TOOL_ALIASES = {
  'fee-receipts': 'fee-collection',
  // D-44 cluster D, done 2026-08-07. The school's owner reported "two views of the
  // student database for some reason": `school-directory` listed every student
  // read-only, `student-database` listed the same students with the buttons that
  // actually do something. They are one screen now — `student-database`, retitled
  // "School Directory", with the Directory's Staff tab folded in.
  'school-directory': 'student-database',
};

/** Canonical id for a tool name, or the name unchanged if it is already canonical. */
export function resolveToolId(toolId) {
  if (!toolId) return toolId;
  return TOOL_ALIASES[toolId] || toolId;
}
