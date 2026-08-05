# Handoff — night of 2026-08-06

Written at the end of a long session that fixed a production outage, deployed `main`, and
cleaned up the migration situation. **Read this before touching anything.**

Previous handoff: `_bmad-output/HANDOFF-2026-08-04-evening.md` (still valid for the data load).

---

## State right now

**The platform is UP and running current code.** Verified end to end, not from a status page:

- Backend health: `{"db":"ok","ai":"ok","s3":"ok","sms":"ok","overall":"ready"}`
- Deployed version: **`eduflow-main-20260806-3a02b20`** (this is `main`, first deploy since 25 July)
- Rollback target if ever needed: `eduflow-uisweep-20260722-217`
- Frontend: Amplify auto-builds from `main`, already current
- `main` and `origin/main` are in sync; working tree clean

**Suites at close:** backend 2173 passed / 0 failed / 15 deselected; frontend 439 passed /
0 failed; production build clean. The bar is the FAILURE count and it is ZERO. Never pin a
passing count (D-51/D-56).

---

## ⚠️ THE ONE CONSTRAINT THAT WILL BITE YOU

**AWS allows exactly ONE small server in this account.** The on-demand vCPU quota is **1**.
The backend runs on a single `t2.small` (1 vCPU) in **ap-south-1b**.

**Do not start any stopped EC2 instance.** Doing so takes the only slot and the school goes
down. That includes `Layaa_OS`, `eduflow-mongodb` and `Migration Database`. It is also why the
Layaa front door still times out.

Quota increase request: case `178589415000933`, asking for 5, `CASE_OPENED` since
2026-08-05 07:11 IST, still not granted.

---

## What happened tonight (short version)

1. **Outage, ~39 hours, resolved.** AWS cut the vCPU quota to 1; the `t3.small` backend (2 vCPU)
   could not launch. Someone tried the correct fix (switch to 1-vCPU `t2.small`) and **our own
   cost guardrail blocked it** — IAM policy `Claude-CloudFrontStaticHostingFix` on the
   `claude-hosting` user explicitly denies `ec2:RunInstances`. The failed update rolled back and
   terminated the last running server. Abhimanyu fixed it from the console as an admin.
2. **Deployed `main`** (23 commits, 70 backend files ahead of what was running). In-place,
   76 seconds, no downtime.
3. **Migrations sorted.** See below.
4. **Full-repo audit fixes** shipped earlier the same day (commit `9d606e1`).

---

## ⛔ MIGRATIONS — read before you go near them

**Never run `python backend/migrations/run_all.py` against production.** Both `CLAUDE.md` and
`AGENTS.md` now say so with the reasoning; that wording is new tonight.

The tracking collection was empty while the work behind the migrations had long been done, so
the runner reported **0 of 29 applied** and would have executed all of them against 1,802 real
students. Six insert convincing fake data into what they assume is a fresh demo school: bus
routes with real Joya stop names (004), NCERT library books (005), vendors (006), discounts plus
a profile per student (007), events (008), expenses billed to UPPCL (009). `002` reassigns
houses to students who already have them.

**Now: 28 of 29 recorded.** Each entry written without running carries a category
(`SEEDS-FAKE-DATA`, `already-done`, `no-op`, `obsolete`, `retired`) plus evidence, and
`marked_without_running: true`.

**Actually executed tonight, each after a dry run:** `016` (matched **zero** accounts — all 7
admins and the owner already had a sub-category), `020` (stamped the school id on the 2 of 4
uploads missing it), `028` and `029` (the commercial indexes, which were genuinely needed).

**`012_migrate_uploads_to_s3` is deliberately still pending.** It is the only real outstanding
migration. 4 legacy uploads; its own docstring says rehearse against a copy of production first.

**Also note:** `_create_indexes()` is disabled in production on purpose (Codex's decision) so
deploying code can never silently alter the school's database. 90 of 91 declared index rules
already exist; the one missing is on an empty collection. Nothing is waiting on indexes.

---

## THE WORK FOR THE NEXT SESSION

Abhimanyu will supply the specifics. Two jobs:

### 1. Frontend distortions
Screens that got visually broken by the 2026-08-05 enterprise release. Prime suspects are the
nine new management hubs (`frontend/src/components/tools/ManagementHub.js`,
`frontend/src/lib/managementHubs.js`) and the sidebar regrouping (`Sidebar.js`), since that
release moved a lot of navigation. **Get a screenshot and the role before changing anything.**

### 2. Owner profile changes Aman asked for
`owner` is a **school** role — the account is Aman Litt. Abhimanyu is the platform founder and
does NOT hold it. Never write "you" to Abhimanyu for an owner-role capability. Get Aman's
requests in his own words; do not infer intent on a role that governs who may do what.

### Rules for this work
- **Frontend changes reach the school automatically** via Amplify on push to `main`. No deploy
  needed, easy to reverse.
- **Backend changes need another deploy.** Do those deliberately, not casually.
- **Batch the commits.** Abhimanyu asked explicitly: make all edits, then push **once** at the
  end, because every push to `main` triggers an Amplify build that costs money.
- Test conventions are in `CLAUDE.md`. Do NOT add `pytestmark = pytest.mark.asyncio`;
  `asyncio_mode = auto` handles it.

---

## Open items, none blocking

**Needs Abhimanyu, cannot be done by an agent:**
- Quota increase (above). Until then, one server only.
- **Rotate the GitHub token** embedded in the git remote of `E:\Github\Layaa AI\eduflow`
  (a `ghp_...` in the remote URL). Live credential in a config file.
- The cost guardrail that caused the outage still blocks all server starts. Narrow it so
  genuinely expensive provisioning stays blocked but small instances are allowed, or accept that
  automated recovery fails and takes the running server with it.
- SSH open to `0.0.0.0/0` on `eduflow-mongo-sg` (`sg-0176ca188e25225fb`). Harmless while that
  machine is off; key-only login. Narrow before starting anything in that group.
- `iam:PutRolePolicy` on `claude-hosting` (D-34), WAF to Block **after** adding the `/api/*`
  exclusion (D-46), old log purge (D-64), make the GitHub Tests check required (D-52).

**Worth checking soon:**
- **LayaaStat should now be receiving data.** Both `LAYAASTAT_URL` and `LAYAASTAT_INGEST_KEY`
  are confirmed set in production, and the fixed code is finally deployed. Look for the
  once-a-minute heartbeat, an LLM span after one Flo message, a product event after one login.
- **The live AI model is the Azure deployment `Odin`**, not the `gpt-5.3-chat` the docs claimed
  and not Gemini (`LLM_MODEL` and `GEMINI_API_KEY` are read by no code). The blocked AI-quality
  baseline needs the key for **Odin**.
- An unexplained failed deploy at 2026-08-05T20:19Z, before the successful one. Nothing broken.
- 89 staff records but only 88 have a role; the 7 admins and owner exist as logins with no
  matching staff record. Not breaking anything, but it matters once a second school arrives.
- **The real-Mongo test tier cannot run on this desktop.** Only MongoDB 8.3 is installed and it
  dies silently on this Windows build; the working 7.0.16 zip is gone.

**Unchanged from the previous handoff:** the data load from `aaryans_database/` (match on
admission number only; never take class or section from the 2025-26 detainees workbook), and
`D-44` part 2 tool merges.

---

## Where the durable record lives

`E:\Github\Aasaan AI\claude-memory-vault` — `Open-Defects.md` has the full outage post-mortem,
the migration analysis, and the AI-model correction. `Projects/Layaa AI/eduflow.md` is current.
Pull it before reading, commit and push before ending.
