[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

function Resolve-CargoAudit {
    $candidate = Join-Path $env:USERPROFILE '.cargo\bin\cargo-audit.exe'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    return $null
}

$cargoAudit = Resolve-CargoAudit
$manifest = Join-Path $RepositoryRoot 'src-tauri\Cargo.toml'
$expectedCargoAuditVersion = 'cargo-audit 0.22.2'
$result = [ordered]@{
    schema = 'nana.tauri.cargo_audit.v1'
    status = 'NOT_OBTAINED'
    command = 'cd src-tauri; cargo audit --no-fetch'
    tool_installed = [bool]$cargoAudit
    cargo_audit_version = $null
    exit_code = $null
    vulnerabilities = $null
    reason = $null
}

if ($cargoAudit) {
    $versionOutput = @(& $cargoAudit --version 2>&1) -join "`n"
    $result.cargo_audit_version = $versionOutput.Trim()
    if ($result.cargo_audit_version -ne $expectedCargoAuditVersion) {
        $result.status = 'FAIL_TOOL_IDENTITY'
        $result.reason = "Expected $expectedCargoAuditVersion but found $($result.cargo_audit_version)."
    }
    $advisoryDb = Join-Path $env:USERPROFILE '.cargo\advisory-db\crates'
    if ($result.status -eq 'FAIL_TOOL_IDENTITY') {
        # Keep the result deterministic and do not execute an untrusted tool.
    } elseif (-not (Test-Path -LiteralPath $advisoryDb -PathType Container)) {
        $result.status = 'BLOCKED_EXTERNAL_ADVISORY_DB'
        $result.reason = 'The RustSec advisory database is not available locally.'
    } else {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Push-Location (Split-Path -Parent $manifest)
    $raw = @(& $cargoAudit audit --no-fetch --json 2>&1) -join "`n"
    $result.exit_code = $LASTEXITCODE
    Pop-Location
    $ErrorActionPreference = $previousPreference
    try {
        $parsed = $raw | ConvertFrom-Json
    $result.vulnerabilities = $parsed.vulnerabilities
    $result.advisory_database = $parsed.database
    } catch {
        $parsed = $null
    }
    if ($result.exit_code -eq 0 -and
        $parsed -and $parsed.vulnerabilities -and
        $null -ne $parsed.vulnerabilities.count -and
        $parsed.vulnerabilities.found -eq $false -and
        $parsed.vulnerabilities.count -eq 0) {
        $result.status = 'PASS'
    } elseif ($parsed -and $parsed.vulnerabilities -and
        $null -ne $parsed.vulnerabilities.count -and
        ($parsed.vulnerabilities.found -ne $false -or $parsed.vulnerabilities.count -ne 0)) {
        $result.status = 'FAIL_VULNERABILITIES'
    } else {
        $result.status = 'FAIL_TOOL'
    }
    }
}

$result | ConvertTo-Json -Depth 8
if ($result.status -ne 'PASS') {
    exit 1
}
