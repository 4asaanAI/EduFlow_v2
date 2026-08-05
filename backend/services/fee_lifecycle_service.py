from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs
from tenant import scoped_filter, scoped_query


class FeeLifecycleValidationError(ValueError):
    pass


class FeeLifecycleNotFoundError(ValueError):
    pass


def _session(session) -> dict:
    return session_kwargs(session)


def _positive_amount(value: Any, field: str) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise FeeLifecycleValidationError(f"{field} must be numeric")
    if amount <= 0:
        raise FeeLifecycleValidationError(f"{field} must be greater than zero")
    return amount


def validate_installments(items: Any) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise FeeLifecycleValidationError("installments must be a non-empty array")
    result = []
    seen_codes = set()
    for index, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            raise FeeLifecycleValidationError(f"installment {index} must be an object")
        code = str(raw.get("code") or f"installment-{index}").strip().lower()
        if not code or code in seen_codes:
            raise FeeLifecycleValidationError("installment codes must be unique")
        seen_codes.add(code)
        due_date = str(raw.get("due_date") or "").strip()
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            raise FeeLifecycleValidationError(f"installment {code} requires a YYYY-MM-DD due_date")
        heads = raw.get("fee_heads")
        if not isinstance(heads, list) or not heads:
            raise FeeLifecycleValidationError(f"installment {code} requires fee_heads")
        normalised_heads = []
        seen_heads = set()
        for head in heads:
            name = str((head or {}).get("name") or "").strip()
            key = name.lower()
            if not name or key in seen_heads:
                raise FeeLifecycleValidationError(f"installment {code} fee-head names must be unique")
            seen_heads.add(key)
            normalised_heads.append({"name": name, "amount": _positive_amount(head.get("amount"), f"{code}.{name}")})
        result.append({
            "code": code,
            "label": str(raw.get("label") or code.replace("-", " ").title()).strip(),
            "due_date": due_date,
            "fee_heads": normalised_heads,
        })
    return result


async def snapshot_fee_structure(db, actor_ctx: ActorContext, structure: dict, *, reason: str, session=None) -> dict:
    revision = {
        "id": str(uuid.uuid4()),
        "structure_id": structure["id"],
        "version": int(structure.get("version") or 1),
        "snapshot": {k: v for k, v in structure.items() if k != "_id"},
        "reason": reason,
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_utc().isoformat(),
        "branch_id": actor_ctx.branch_id,
        "schoolId": actor_ctx.school_id,
    }
    await db.fee_structure_revisions.insert_one({**revision, "_id": revision["id"]}, **_session(session))
    return revision


async def replace_installments(db, actor_ctx: ActorContext, structure_id: str, items: Any, *, session=None) -> dict:
    structure = await db.fee_structures.find_one(
        scoped_filter({"id": structure_id}, actor_ctx.school_id), {"_id": 0}, **_session(session)
    )
    if not structure:
        raise FeeLifecycleNotFoundError("Fee structure not found")
    installments = validate_installments(items)
    now = actor_ctx.now_utc().isoformat()
    await snapshot_fee_structure(db, actor_ctx, structure, reason="installments_replaced", session=session)
    next_version = int(structure.get("version") or 1) + 1
    await db.fee_structures.update_one(
        scoped_filter({"id": structure_id}, actor_ctx.school_id),
        {"$set": {"installments": installments, "version": next_version, "updated_at": now}},
        **_session(session),
    )
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "_id": str(uuid.uuid4()), "schoolId": actor_ctx.school_id,
        "entity_type": "fee_structure", "entity_id": structure_id,
        "action": "fee_installments_replaced", "changed_by": actor_ctx.user_id,
        "changes": {"version": next_version, "installment_count": len(installments)},
        "created_at": now,
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)
    return {"structure_id": structure_id, "version": next_version, "installments": installments}


async def build_charge_preview(db, actor_ctx: ActorContext, structure_id: str, *, installment_codes=None) -> dict:
    structure = await db.fee_structures.find_one(
        scoped_filter({"id": structure_id}, actor_ctx.school_id), {"_id": 0}
    )
    if not structure:
        raise FeeLifecycleNotFoundError("Fee structure not found")
    installments = validate_installments(structure.get("installments"))
    selected = set(installment_codes or [])
    if selected:
        installments = [row for row in installments if row["code"] in selected]
        if len(installments) != len(selected):
            raise FeeLifecycleValidationError("One or more installment codes were not found")
    students = await db.students.find(
        scoped_query({"class_id": structure.get("class_id"), "is_active": True}, branch_id=actor_ctx.branch_id),
        {"_id": 0, "id": 1, "name": 1, "admission_number": 1},
    ).to_list(5000)
    version = int(structure.get("version") or 1)
    rows = []
    for student in students:
        for installment in installments:
            for head in installment["fee_heads"]:
                charge_key = f"{student['id']}|{structure_id}|{version}|{installment['code']}|{head['name'].strip().lower()}"
                rows.append({
                    "charge_key": charge_key,
                    "student_id": student["id"],
                    "student_name": student.get("name"),
                    "admission_number": student.get("admission_number"),
                    "structure_id": structure_id,
                    "structure_version": version,
                    "installment_code": installment["code"],
                    "fee_period": installment["code"],
                    "fee_head": head["name"],
                    "amount": head["amount"],
                    "due_date": installment["due_date"],
                })
    existing = await db.fee_transactions.find(
        scoped_query({"charge_key": {"$in": [row["charge_key"] for row in rows]}}, branch_id=actor_ctx.branch_id),
        {"_id": 0, "charge_key": 1},
    ).to_list(len(rows)) if rows else []
    existing_keys = {row.get("charge_key") for row in existing}
    for row in rows:
        row["already_generated"] = row["charge_key"] in existing_keys
    return {
        "structure": {"id": structure_id, "name": structure.get("name"), "version": version},
        "rows": rows,
        "meta": {
            "student_count": len(students),
            "charge_count": len(rows),
            "new_charge_count": sum(not row["already_generated"] for row in rows),
            "total_amount": sum(row["amount"] for row in rows if not row["already_generated"]),
        },
    }


async def generate_charges(db, actor_ctx: ActorContext, structure_id: str, *, installment_codes=None) -> dict:
    preview = await build_charge_preview(db, actor_ctx, structure_id, installment_codes=installment_codes)
    now = actor_ctx.now_utc().isoformat()
    created = []
    skipped = 0
    for row in preview["rows"]:
        if row["already_generated"]:
            skipped += 1
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "branch_id": actor_ctx.branch_id,
            **{k: v for k, v in row.items() if k not in {"student_name", "admission_number", "already_generated"}},
            "fee_type": row["fee_head"],
            "status": "pending",
            "paid_amount": 0,
            "generated_by": actor_ctx.user_id,
            "generated_at": now,
            "created_at": now,
        }
        await db.fee_transactions.update_one(
            scoped_query({"charge_key": row["charge_key"]}, branch_id=actor_ctx.branch_id),
            {"$setOnInsert": {**doc, "_id": doc["id"]}}, upsert=True,
        )
        created.append(doc)
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "_id": str(uuid.uuid4()), "schoolId": actor_ctx.school_id,
        "entity_type": "fee_structure", "entity_id": structure_id,
        "action": "fee_charges_generated", "changed_by": actor_ctx.user_id,
        "changes": {"created_count": len(created), "skipped_count": skipped}, "created_at": now,
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)
    return {"created_count": len(created), "skipped_count": skipped, "charges": created}
