from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _env_names() -> set[str]:
    names: set[str] = set()
    for line in (ROOT / "backend" / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        names.add(stripped.split("=", 1)[0])
    return names


def test_deployment_runbook_documents_all_example_env_vars():
    runbook = (ROOT / "docs" / "deployment-runbook.md").read_text(encoding="utf-8")

    missing = sorted(name for name in _env_names() if f"`{name}`" not in runbook)
    assert missing == []


def test_operations_and_deployment_runbook_sections_exist():
    operations = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "deployment-runbook.md").read_text(encoding="utf-8")

    for heading in (
        "## 1. Pre-Deploy Checklist",
        "## 2. Backend Deploy Steps",
        "## 3. Migration Procedure",
        "## 4. Rollback Procedure",
        "## 5. Environment Variables",
        "## 6. Seed Procedure",
        "## 7. Multi-School Setup",
    ):
        assert heading in runbook

    assert "## Backup Policy" in operations
    assert "## Restore Procedure" in operations
