"""Controlled school-defined schemas and rows shared by REST and Flo."""

from __future__ import annotations

import re
import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit
from tenant import scoped_filter


FIELD_TYPES = {
    "text", "textarea", "number", "date", "email", "phone", "select", "checkbox",
}
MAX_FIELDS = 100
MAX_TEXT_LENGTH = 10_000


class CustomFormValidationError(Exception):
    pass


class CustomFormNotFoundError(Exception):
    pass


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")[:64]


def _fields(value) -> list:
    if not isinstance(value, list) or not value:
        raise CustomFormValidationError("At least one field is required")
    if len(value) > MAX_FIELDS:
        raise CustomFormValidationError(f"A form may contain at most {MAX_FIELDS} fields")
    result = []
    seen = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise CustomFormValidationError("Each field must be an object")
        source_name = raw.get("label") or raw.get("name") or raw.get("id") or raw.get("key")
        label = str(source_name or "").strip()
        key = _key(raw.get("key") or raw.get("id") or raw.get("name") or label)
        field_type = str(raw.get("type") or "text").strip().lower()
        if not label or not key:
            raise CustomFormValidationError("Every field needs a label and key")
        if key in seen:
            raise CustomFormValidationError(f"Duplicate field key: {key}")
        if field_type not in FIELD_TYPES:
            raise CustomFormValidationError(f"Unsupported field type: {field_type}")
        options = raw.get("options") or []
        if field_type == "select" and (not isinstance(options, list) or not options):
            raise CustomFormValidationError(f"Select field '{label}' needs options")
        if field_type == "select" and len(options) > 100:
            raise CustomFormValidationError(f"Select field '{label}' has too many options")
        seen.add(key)
        result.append({
            "key": key, "label": label, "type": field_type,
            "required": bool(raw.get("required", False)),
            **({"options": [str(item) for item in options]} if field_type == "select" else {}),
        })
    return result


def _validated_answer(field: dict, value):
    if value in (None, ""):
        return value
    field_type = field["type"]
    if field_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CustomFormValidationError(f"{field['label']} must be a number")
        return value
    if field_type == "checkbox":
        if not isinstance(value, bool):
            raise CustomFormValidationError(f"{field['label']} must be true or false")
        return value
    if not isinstance(value, str):
        raise CustomFormValidationError(f"{field['label']} must be text")
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        raise CustomFormValidationError(f"{field['label']} is too long")
    if field_type == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise CustomFormValidationError(f"{field['label']} must be a valid email address")
    if field_type == "phone" and not re.fullmatch(r"[+0-9()\-\s]{7,20}", value):
        raise CustomFormValidationError(f"{field['label']} must be a valid phone number")
    if field_type == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CustomFormValidationError(f"{field['label']} must use YYYY-MM-DD")
    if field_type == "select" and value not in field.get("options", []):
        raise CustomFormValidationError(f"{field['label']} must be one of its configured options")
    return value


async def create_form(db, actor: ActorContext, params: dict) -> dict:
    title = str(params.get("title") or "").strip()
    if not title:
        raise CustomFormValidationError("Title is required")
    if len(title) > 200:
        raise CustomFormValidationError("Title is too long")
    fields = _fields(params.get("fields"))
    form_id = str(uuid.uuid4())
    now = actor.now_iso()
    doc = {
        "_id": form_id, "id": form_id, "schoolId": actor.school_id,
        "title": title, "fields": fields, "schema_version": 1,
        "audience": str(params.get("audience") or "all"),
        "public_slug": str(params.get("public_slug") or uuid.uuid4().hex[:8]),
        "expires_at": params.get("expires_at"), "created_by": actor.user_id,
        "is_active": True, "created_at": now, "updated_at": now,
    }
    await db.custom_forms.insert_one(doc)
    await write_audit(
        db, action="custom_form_create", entity_id=form_id, collection="custom_forms",
        changed_by=actor.user_id or "", changed_by_role=actor.role or "",
        school_id=actor.school_id, branch_id=actor.branch_id or "",
        changes={"title": title, "fields": fields, "schema_version": 1},
    )
    return {key: value for key, value in doc.items() if key != "_id"}


async def update_form(db, actor: ActorContext, form_id: str, params: dict) -> dict:
    existing = await db.custom_forms.find_one(
        scoped_filter({"id": form_id}, actor.school_id), {"_id": 0}
    )
    if not existing:
        raise CustomFormNotFoundError("Form not found")
    update = {}
    if "title" in params:
        title = str(params.get("title") or "").strip()
        if not title:
            raise CustomFormValidationError("Title cannot be empty")
        update["title"] = title
    if "fields" in params:
        update["fields"] = _fields(params.get("fields"))
        update["schema_version"] = int(existing.get("schema_version") or 1) + 1
    for field in ("audience", "expires_at", "is_active"):
        if field in params:
            update[field] = params[field]
    if not update:
        raise CustomFormValidationError("At least one editable field is required")
    update["updated_at"] = actor.now_iso()
    await db.custom_forms.update_one(
        scoped_filter({"id": form_id}, actor.school_id), {"$set": update}
    )
    await write_audit(
        db, action="custom_form_update", entity_id=form_id, collection="custom_forms",
        changed_by=actor.user_id or "", changed_by_role=actor.role or "",
        school_id=actor.school_id, branch_id=actor.branch_id or "",
        changes={"before": {key: existing.get(key) for key in update}, "after": update},
    )
    return {**existing, **update}


async def submit_response(db, actor: ActorContext, form_id: str, params: dict) -> dict:
    form = await db.custom_forms.find_one(
        scoped_filter({"id": form_id, "is_active": True}, actor.school_id), {"_id": 0}
    )
    if not form:
        raise CustomFormNotFoundError("Active form not found")
    answers = params.get("answers")
    if not isinstance(answers, dict):
        raise CustomFormValidationError("answers must be an object")
    allowed = {field["key"]: field for field in form.get("fields") or []}
    unknown = sorted(set(answers) - set(allowed))
    if unknown:
        raise CustomFormValidationError(f"Unknown field keys: {', '.join(unknown)}")
    missing = [
        field["label"] for field in allowed.values()
        if field.get("required") and answers.get(field["key"]) in (None, "")
    ]
    if missing:
        raise CustomFormValidationError(f"Required fields missing: {', '.join(missing)}")
    validated_answers = {
        key: _validated_answer(allowed[key], value) for key, value in answers.items()
    }
    response_id = str(uuid.uuid4())
    now = actor.now_iso()
    doc = {
        "_id": response_id, "id": response_id, "schoolId": actor.school_id,
        "form_id": form_id, "schema_version": form.get("schema_version", 1),
        "submitted_by": actor.user_id, "submitted_by_name": actor.actor_name,
        "submitted_by_role": actor.role, "answers": validated_answers, "submitted_at": now,
    }
    await db.form_responses.insert_one(doc)
    await write_audit(
        db, action="form_response_submit", entity_id=response_id, collection="form_responses",
        changed_by=actor.user_id or "", changed_by_role=actor.role or "",
        school_id=actor.school_id, branch_id=actor.branch_id or "",
        changes={"form_id": form_id, "schema_version": doc["schema_version"]},
    )
    return {key: value for key, value in doc.items() if key != "_id"}


async def delete_form(db, actor: ActorContext, form_id: str) -> dict:
    form = await db.custom_forms.find_one(
        scoped_filter({"id": form_id}, actor.school_id), {"_id": 0}
    )
    if not form:
        raise CustomFormNotFoundError("Form not found")
    response_count = await db.form_responses.count_documents(
        scoped_filter({"form_id": form_id}, actor.school_id)
    )
    await db.custom_forms.delete_one(scoped_filter({"id": form_id}, actor.school_id))
    await db.form_responses.delete_many(scoped_filter({"form_id": form_id}, actor.school_id))
    await write_audit(
        db, action="custom_form_delete", entity_id=form_id, collection="custom_forms",
        changed_by=actor.user_id or "", changed_by_role=actor.role or "",
        school_id=actor.school_id, branch_id=actor.branch_id or "",
        changes={"title": form.get("title"), "deleted_responses": response_count},
    )
    return {"form": form, "deleted_responses": response_count}
