[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

& (Join-Path $PSScriptRoot 'check_tauri_windows_prereqs.ps1') `
    -RepositoryRoot $RepositoryRoot
$preflightExit = $LASTEXITCODE
& (Join-Path $PSScriptRoot 'check_tauri_npm_audit.ps1') `
    -RepositoryRoot $RepositoryRoot
$auditExit = $LASTEXITCODE

if ($preflightExit -ne 0 -or $auditExit -ne 0) {
    exit 1
}
