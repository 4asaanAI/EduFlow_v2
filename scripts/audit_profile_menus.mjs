/**
 * Measure which screens each school profile is OFFERED in the menus.
 *
 * The third surface behind the table in
 * `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md` §1.1.
 * The other two (Flo tools, API routes) are in `scripts/audit_profile_reach.py`.
 *
 * SAFE: imports two frontend modules and calls pure functions. No network, no
 * database, no writes.
 *
 *     node scripts/audit_profile_menus.mjs
 *     node scripts/audit_profile_menus.mjs --ids     # also list every screen id
 *
 * Being offered a screen is NOT the same as being allowed to use it. The server
 * is the real gate, and the two disagree today (plan §1.8). This measures the
 * offer only.
 *
 * KNOWN LIMIT, read before quoting the last five rows as zero. This measures the
 * HUB menu only. Only owner, principal, accountant and management get hubs;
 * transport_head, receptionist, it_tech, maintenance and support_staff are built
 * from the flat `ADMIN_SUBCATEGORY_TOOLS` list in `frontend/src/components/Sidebar.js`
 * instead, which this script does not import (it would pull in React and the whole
 * icon set). A 0 below means "no hubs", never "no screens". Read Sidebar.js for
 * those five, and note that `support_staff` has NO entry in that map at all, so it
 * falls through to the entire generic admin list minus the hubs.
 */

import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const libDir = path.join(repoRoot, 'frontend', 'src', 'lib');

// managementHubs.js imports './toolPermissions' with no file extension, which
// Node's ESM resolver rejects. Copy both into a temp dir and add the extension
// rather than editing the real source.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eduflow-menu-audit-'));
fs.copyFileSync(path.join(libDir, 'toolPermissions.js'), path.join(tmp, 'toolPermissions.js'));
fs.writeFileSync(
  path.join(tmp, 'managementHubs.js'),
  fs.readFileSync(path.join(libDir, 'managementHubs.js'), 'utf8')
    .replace("'./toolPermissions'", "'./toolPermissions.js'"),
);

const { MANAGEMENT_HUBS, hubsForUser, hubItemsForUser } =
  // pathToFileURL, not a bare path: on Windows an absolute path starts with a
  // drive letter, which Node's ESM loader reads as an unsupported URL scheme.
  await import(pathToFileURL(path.join(tmp, 'managementHubs.js')).href);

// Same nine profiles as the Python script, and for the same reason: a sweep
// that covers only the four in Release 2 cannot see the other four being
// silently stripped.
const PROFILES = {
  owner: { role: 'owner', sub_category: 'owner' },
  principal: { role: 'admin', sub_category: 'principal' },
  accountant: { role: 'admin', sub_category: 'accountant' },
  management: { role: 'admin', sub_category: 'management' },
  transport_head: { role: 'admin', sub_category: 'transport_head' },
  receptionist: { role: 'admin', sub_category: 'receptionist' },
  it_tech: { role: 'admin', sub_category: 'it_tech' },
  maintenance: { role: 'admin', sub_category: 'maintenance' },
  support_staff: { role: 'admin', sub_category: 'support_staff' },
};

const showIds = process.argv.includes('--ids');

// Which audience each hub row was written for, so we can report rows a profile
// sees that were never meant for it (plan §1.2).
const audienceOf = new Map();
for (const hub of MANAGEMENT_HUBS) {
  for (const [id, , , audience] of hub.items) audienceOf.set(id, audience);
}

console.log(`${MANAGEMENT_HUBS.length} hubs defined\n`);
console.log(`${'profile'.padEnd(16)} ${'hubs'.padStart(5)} ${'screens'.padStart(8)}`);

const offered = {};
for (const [name, user] of Object.entries(PROFILES)) {
  const hubs = hubsForUser(user);
  const ids = hubs.flatMap((hub) => hubItemsForUser(hub, user).map((item) => item[0]));
  offered[name] = ids;
  console.log(`${name.padEnd(16)} ${String(hubs.length).padStart(5)} ${String(ids.length).padStart(8)}`);
}

console.log(
  '\nNOTE: 0 means "no HUBS", not "no screens". The five profiles below management\n' +
  '      are built from the flat ADMIN_SUBCATEGORY_TOOLS list in Sidebar.js, which\n' +
  '      this script does not read. See the header comment.',
);

// A profile seeing rows tagged for a different audience is the defect behind
// the screenshot Abhimanyu sent on 2026-08-10.
console.log('\nRows a profile is offered that were tagged for someone else:');
for (const [name, ids] of Object.entries(offered)) {
  if (name === 'owner' || name === 'principal') continue;
  const wrong = ids.filter((id) => ['owner', 'principal'].includes(audienceOf.get(id)));
  if (wrong.length) console.log(`  ${name}: ${wrong.join(', ')}`);
}

if (showIds) {
  console.log('\nEvery screen offered, per profile:');
  for (const [name, ids] of Object.entries(offered)) {
    console.log(`\n  ${name} (${ids.length})`);
    console.log(`    ${ids.join(', ') || '(none)'}`);
  }
}

fs.rmSync(tmp, { recursive: true, force: true });
