# Quick Spec: Assessment Result Integrity

**Status:** done  
**Source gap:** Frappe Education Assessment Result validation and ERPNext submitted-document correction history

## Goal

Prevent dangling, cross-class, inflated, or silently overwritten assessment results while keeping the existing exam and marks-entry workflow intact.

## Acceptance Criteria

1. Bulk marks entry validates referenced exams and students and, when supplied, subject/class membership.
2. Zero marks are preserved exactly and numeric conversion failures become row errors.
3. Max marks prefer the stored exam/subject schedule over client-supplied values.
4. Batch validation uses batched reads rather than one exam and student lookup per row.
5. Updating an unpublished row preserves its stable result ID and creation metadata.
6. Published results cannot be silently overwritten through bulk entry.
7. School owner/principal can correct a published result only with a reason; the previous value is written to immutable correction history.
8. The marks grid renders published cells as locked instead of presenting an editable input that will fail.
9. Existing role gates and student publication visibility remain unchanged.

## Non-Goals

- No hard-coded CBSE grade bands.
- No policy assumption about weighted assessment criteria.
- No branding or theme change.

## Suggested Review Order

1. Batched bulk validation and stable upsert.
2. Correction endpoint and correction-history index.
3. Published-cell frontend behavior.
4. Regression and security tests.
