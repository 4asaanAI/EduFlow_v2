# One command that runs everything a change has to pass (D-52).
#
#   powershell -File scripts/check.ps1
#
# The same three checks the CI workflow runs (.github/workflows/tests.yml), so a
# green run here means a green run there. Written for this machine: the backend
# virtualenv is backend/.venv (Python 3.12) and PowerShell needs its ABSOLUTE path.
#
# The bar is the FAILURE count, never the passing count. The passing count grows
# every block; pinning it is what produced three stale "the suite should show N"
# instructions in the registers (D-51 / D-56).

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$failed = @()

function Announce($text) {
    Write-Host ""
    Write-Host "── $text ────────────────────────────────────────────" -ForegroundColor Cyan
}

# ── Backend ──────────────────────────────────────────────────────────────────
Announce "Backend suite"
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No backend virtualenv at $python" -ForegroundColor Yellow
    Write-Host "Build it with:  py -3.12 -m venv backend\.venv" -ForegroundColor Yellow
    $failed += "backend (no virtualenv)"
} else {
    # Pin the database first or a fail-closed guard in conftest.py stops the run,
    # which exists so a test run can never reach the school's real data (D-04).
    $env:MONGO_URL = "mongodb://127.0.0.1:27099/eduflow_test"
    $env:DB_NAME = "eduflow_test"
    & $python -m pytest (Join-Path $repo "tests\backend") -q
    if ($LASTEXITCODE -ne 0) { $failed += "backend suite" }
}

# ── Frontend ─────────────────────────────────────────────────────────────────
Announce "Frontend suite"
Push-Location (Join-Path $repo "frontend")
try {
    $env:CI = "true"
    npx craco test --watchAll=false
    if ($LASTEXITCODE -ne 0) { $failed += "frontend suite" }

    Announce "Production build (hook-dependency rule at error)"
    npx craco build
    if ($LASTEXITCODE -ne 0) { $failed += "production build" }
} finally {
    Pop-Location
}

# ── Verdict ──────────────────────────────────────────────────────────────────
Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "All checks passed." -ForegroundColor Green
    exit 0
}
Write-Host "FAILED: $($failed -join ', ')" -ForegroundColor Red
Write-Host "Do not merge or deploy on this. A red suite reaching main is D-52." -ForegroundColor Red
exit 1
