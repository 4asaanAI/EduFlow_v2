---
title: 'Enterprise Commercial Operations for EduFlow'
type: 'feature'
created: '2026-08-05'
status: 'done'
baseline_commit: 'a74620f9ce9a125dfa43e53d286408803d0be62d'
context:
  - '_bmad-output/project-context.md'
  - '_bmad-output/planning-artifacts/research/technical-eduflow-vs-erpnext-and-frappe-education-research-2026-08-05.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** EduFlow has admissions, inventory, procurement, fees, and accounting locks, but lacks the connected CRM, campus retail/POS, and legal-entity controls needed for enterprise commercial operations.

**Approach:** Adapt only useful ERPNext domain rules into EduFlow's React/FastAPI/MongoDB services: extend admission enquiries into a school CRM, reuse campus inventory for retail, add lightweight trust/school legal-entity ownership and consolidation, consolidate owner/principal tools into domain hubs, and verify Flo's prompt/knowledge contracts without importing Frappe, Desk/Vue, SQL, or generic ERP complexity.

## Boundaries & Constraints

**Always:** Preserve branding, theme, current behavior, legacy records, deep links, and the single active Joya branch; reduce owner/principal navigation entries by grouping related capabilities into obvious domain hubs without removing access; use additive schemas and default-entity fallback; school/branch/entity-scope every record; use shared services for REST/Flo parity; use append-only sales, returns, stock, activities, and audit events; enforce RBAC, idempotency, accounting-period locks, non-negative stock, and responsive 320px-1440px UI; test only against fakes or isolated temporary databases.

**Ask First:** Any live-data migration, production deployment, multi-branch activation, inter-entity posting, tax/e-invoice integration, payment-provider mutation, or change to AI write-lockdown policy.

**Never:** Read or write the school's live database; add hostel management; replace the stack or visual identity; duplicate admissions/inventory/finance sources of truth; silently backfill existing data; permit group entities to transact; overwrite posted sales or returns; claim Frappe/ERPNext feature parity.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| CRM lifecycle | School prospect with source, owner, follow-up and opportunity | Valid staged conversion links the existing enquiry/application/student chain | Reject duplicate contact and illegal transition; require lost reason |
| POS sale | Open cashier shift, stocked items, one or more payment modes | Idempotent receipt, atomic stock issue, entity/period/audit attribution | Reject closed shift/period, payment mismatch, stale price, or insufficient stock |
| POS return | Posted receipt with returnable quantity | Linked reversal receipt and stock return; original stays immutable | Reject excess, duplicate, cross-entity, or closed-period return |
| Entity reporting | Default operating entity plus optional group/children | Per-entity views and owner-only consolidated read totals | Reject group posting and unauthorized/cross-entity access |
| Legacy record | Record has no entity_id | Read through configured default entity without modifying the record | Fail closed if multiple entities exist and no default is configured |

</frozen-after-approval>

## Code Map

- `backend/services/enquiry_service.py` - existing admission-enquiry source of truth to extend, not replace.
- `backend/services/campus_ops_service.py` - inventory and atomic stock movement rules reused by retail.
- `backend/services/accounting_period_service.py` - posting-lock guard extended to entity context.
- `backend/routes/commercial.py` and `backend/services/commercial_service.py` - bounded CRM, POS, shift, return, entity, and reporting APIs.
- `backend/ai/tool_functions_v2.py` and registry/parity tests - scoped conversational reads and confirmed shared-service writes allowed by current policy.
- `frontend/src/components/tools/CommercialOperations.js` plus tool routing/navigation - responsive CRM, POS, and entity panels using current design tokens.
- `backend/migrations/029_commercial_operations.py` - indexes/default configuration only; no live backfill.

## Tasks & Acceptance

**Execution:**
- [x] Add legal entities, default resolution, entity-scoped numbering, RBAC, and owner-only consolidated reporting.
- [x] Extend enquiry CRM with activities, follow-ups, opportunities, probability/value, conversion links, aging, and loss reasons.
- [x] Add catalog pricing, cashier shifts, immutable POS sales/returns, split payments, inventory movements, receipts, and accounting locks.
- [x] Add Flo tools through shared services and current confirmation/lockdown contracts.
- [x] Add responsive panels, navigation, API bindings, empty/error/loading states, and accessibility labels without restyling EduFlow.
- [x] Consolidate owner/principal navigation into domain hubs for school database, finance, admissions/CRM, academics/activities, campus/library, transport, people, AI/insights, and settings while retaining deep-link compatibility.
- [x] Audit Flo's global and role prompts, tool registry parity, school KB/context, learned-memory fencing, and built-in communication habit; repair only evidenced gaps and add regression tests.
- [x] Add indexes, isolated migration rehearsal, backend/frontend/security/tenant/entity/parity/responsive tests, and documentation.

**Acceptance Criteria:**
- Given any new endpoint, unauthenticated and unauthorized callers receive 401 and 403, and cross-school/branch/entity records never leak.
- Given an admissions lead, authorized staff can manage it through conversion without duplicating the existing applicant/student workflow.
- Given concurrent or retried retail requests, exactly one financial and stock outcome is committed and auditable.
- Given legacy production-shaped data, existing screens and APIs continue to work with zero data mutation.
- Given supported role and viewport combinations, each new panel is usable without horizontal page overflow or hidden primary actions.
- Given the full quality gate, backend tests have zero failures, frontend tests and production build pass, and responsive E2E passes.

## Spec Change Log

- 2026-08-05 acceptance clarification: legal entities are reporting/ownership dimensions within one branch, not separately entitled tenants. Authorized owner/principal/commercial profiles may select any active operating entity in their branch. "Cross-entity isolation" means every query and posting is filtered to the selected entity and cannot mix records from another entity; per-user entity assignments are outside this phase.

## Design Notes

Legal entities represent accounting/reporting ownership inside one school deployment, not new tenants or branches. Group entities consolidate but never post. POS deliberately omits loyalty, complex promotions, serial/batch stock, inter-company invoices, and full general-ledger replication until separately approved.

## Verification

**Commands:**
- `python -m pytest tests/backend/ -q` - 2,163 passed, 15 credentialed tests deselected, zero failures (2026-08-05; pinned local test database environment).
- `cd frontend && CI=true npx craco test --watchAll=false` - 439 passed, zero failures (2026-08-05).
- `cd frontend && npx craco build` - production build succeeded; only the pre-existing `html2pdf.js` missing-source-map warning remains.
- `npx playwright test tests/e2e/responsive.spec.js` - 3 passed, covering authenticated shell, management hubs, and commercial workspace at target widths.
- Migration 029 was rehearsed twice against the isolated fake migration database - idempotent and no application-data writes. The credentialed real-Mongo transaction tier remains intentionally deselected because the local replica-set service is unavailable.
