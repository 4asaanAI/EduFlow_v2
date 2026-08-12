"""Measure what every school profile can reach, across Flo tools and API routes.

This is the script that produced the table in
`_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md` §1.1.
It is committed rather than thrown away so the numbers in that plan can be
re-measured after each sub-part instead of being trusted.

SAFE: imports the FastAPI app and the tool registry and reads them in memory.
Touches no database, sends no request, writes nothing outside --out.

    backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py
    backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py --out routes.json

KNOWN LIMIT, read before quoting the route numbers: 106 routes carry no
dependency-level guard and check permission inside the handler body instead
(`students.py`, `staff.py`, `payroll.py`, `audit.py`, `import_data.py`,
`tools.py` are the ones that matter here). They are counted as UNGUARDED below,
not as reachable, so the route column UNDERSTATES what a profile can actually
reach. Read those files by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

# Dev-only values so the app imports. None of these reach a real service: the
# script never opens a connection.
for _key, _value in {
    "SCHOOL_ID": "aaryans-joya",
    "ENVIRONMENT": "development",
    "MONGO_URL": "mongodb://127.0.0.1:27099/eduflow_test",
    "DB_NAME": "eduflow_test",
    "JWT_SECRET": "dev-only-not-a-real-secret",
    "AZURE_OPENAI_ENDPOINT": "https://example.invalid",
    "AZURE_OPENAI_API_KEY": "dev-only",
}.items():
    os.environ.setdefault(_key, _value)


# Every profile the platform issues a token for, per
# `middleware.auth.SUB_CATEGORIES_BY_ROLE`. All nine admin-side profiles are
# here on purpose: a sweep that only covers the four named in Release 2 cannot
# see it silently stripping the other four.
PROFILES = {
    "owner": {"role": "owner", "sub_category": "owner"},
    "principal": {"role": "admin", "sub_category": "principal"},
    "accountant": {"role": "admin", "sub_category": "accountant"},
    "management": {"role": "admin", "sub_category": "management"},
    "transport_head": {"role": "admin", "sub_category": "transport_head"},
    "receptionist": {"role": "admin", "sub_category": "receptionist"},
    "it_tech": {"role": "admin", "sub_category": "it_tech"},
    "maintenance": {"role": "admin", "sub_category": "maintenance"},
    "support_staff": {"role": "admin", "sub_category": "support_staff"},
}


def measure_tools() -> dict:
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    out = {}
    for name, user in PROFILES.items():
        allowed = [d for d in TOOL_REGISTRY.values() if is_tool_authorized(user, d)]
        writes = [
            d for d in allowed
            if d.get("dispatch_type") == "write" or d.get("requires_confirmation")
        ]
        out[name] = {"tools": len(allowed), "writes": len(writes)}
    out["_total_registry"] = len(TOOL_REGISTRY)
    return out


def _describe(call) -> str:
    """Name a route guard, unwrapping the closures `require_role`/`require_access` return."""
    name = getattr(call, "__name__", None) or str(call)
    if name != "dependency":
        return name
    cells = {}
    try:
        for var, cell in zip(call.__code__.co_freevars, call.__closure__ or ()):
            try:
                cells[var] = cell.cell_contents
            except ValueError:
                pass
    except Exception:
        pass
    roles, sub, subs = cells.get("roles"), cells.get("sub_category"), cells.get("sub_categories")
    if roles is not None and (sub is not None or subs is not None):
        return f"require_access({','.join(roles)}|sub={sub or subs})"
    if roles is not None:
        return f"require_role({','.join(roles)})"
    if subs is not None:
        return f"require_owner_or_subs({','.join(subs)})"
    return f"dependency<{sorted(cells)}>"


def _allows(guard: str, role: str, sub: str):
    """True / False, or None when the guard is not one this script understands."""
    if guard == "get_current_user":
        return True
    m = re.match(r"require_role\((.*)\)$", guard)
    if m:
        return role in m.group(1).split(",")
    m = re.match(r"require_access\((.*)\|sub=(.*)\)$", guard)
    if m:
        return role in m.group(1).split(",") and sub in str(m.group(2))
    m = re.match(r"require_owner_or_subs\((.*)\)$", guard)
    if m:
        return role == "owner" or (role == "admin" and sub in m.group(1).split(","))
    # Release 3: the export gates are derived from the permission table rather than
    # re-stated as role names, so this asks the table the same question the route
    # does instead of keeping a second copy of the answer here.
    m = re.match(r"require_export\((.*)\)$", guard)
    if m:
        from routes.exports import EXPORT_EXTRA_ROLES, EXPORT_SCREENS
        from services import profile_matrix

        key = m.group(1)
        user = {"role": role, "sub_category": sub}
        profile = profile_matrix.profile_of(user)
        if profile:
            if profile_matrix.PROFILE_MATRIX[profile]["status"] != "live":
                return False
            return any(
                profile_matrix.may_open_screen(user, s)
                for s in EXPORT_SCREENS.get(key, ())
            )
        return role in EXPORT_EXTRA_ROLES.get(key, ())
    fixed = {
        "require_owner": lambda: role == "owner",
        "require_owner_or_principal": lambda: role == "owner" or (role == "admin" and sub == "principal"),
        "require_owner_principal_or_management": lambda: role == "owner" or (role == "admin" and sub in ("principal", "management")),
        "require_owner_principal_or_accountant": lambda: role == "owner" or (role == "admin" and sub in ("principal", "accountant")),
        "require_owner_accountant_or_principal": lambda: role == "owner" or (role == "admin" and sub in ("principal", "accountant")),
        "_require_owner_or_accountant": lambda: role == "owner" or (role == "admin" and sub == "accountant"),
        "require_exam_manager": lambda: role == "owner" or (role == "admin" and sub in ("principal", "management")),
        "require_exam_editor": lambda: role == "owner" or (role == "admin" and sub in ("principal", "management")),
        "_require_it_tech_access": lambda: role == "owner" or (role == "admin" and sub in ("principal", "it_tech")),
        "require_custom_form_reader": lambda: True,
        "require_federation_auth": lambda: False,
    }
    fn = fixed.get(guard)
    return fn() if fn else None


def measure_routes(dump_path: str | None) -> dict:
    import server

    rows = []
    for route in server.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        guards: list[str] = []

        def walk(dep):
            for sub_dep in getattr(dep, "dependencies", []):
                guards.append(_describe(getattr(sub_dep, "call", None)))
                walk(sub_dep)

        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            walk(dependant)
        rows.append({
            "path": path,
            "methods": sorted(m for m in (getattr(route, "methods", []) or []) if m not in ("HEAD", "OPTIONS")),
            "guards": sorted(set(guards)),
            "module": getattr(getattr(route, "endpoint", None), "__module__", ""),
        })

    unknown = set()
    out = {name: 0 for name in PROFILES}
    unguarded = 0
    for row in rows:
        if not row["guards"]:
            unguarded += 1
            continue
        for name, user in PROFILES.items():
            verdicts = [_allows(g, user["role"], user["sub_category"]) for g in row["guards"]]
            unknown.update(g for g, v in zip(row["guards"], verdicts) if v is None)
            if all(v is not False for v in verdicts):
                out[name] += 1

    if dump_path:
        with open(dump_path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1)

    return {
        "reachable": out,
        "total": len(rows),
        "unguarded_body_checked": unguarded,
        "guards_this_script_does_not_understand": sorted(unknown),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="write the full route map to this JSON file")
    args = parser.parse_args()

    tools = measure_tools()
    routes = measure_routes(args.out)

    print(f"Flo tool registry: {tools.pop('_total_registry')} tools")
    print(f"API routes: {routes['total']} "
          f"({routes['unguarded_body_checked']} guarded inside the handler body, counted as UNREACHABLE here)")
    print()
    print(f"{'profile':16s} {'tools':>6s} {'writes':>7s} {'routes':>7s}")
    for name in PROFILES:
        t = tools[name]
        print(f"{name:16s} {t['tools']:6d} {t['writes']:7d} {routes['reachable'][name]:7d}")

    if routes["guards_this_script_does_not_understand"]:
        print("\nGuards this script does not understand (routes using them were treated as reachable):")
        for guard in routes["guards_this_script_does_not_understand"]:
            print(f"  {guard}")


if __name__ == "__main__":
    main()
