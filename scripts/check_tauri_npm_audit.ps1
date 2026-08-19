[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
$toolRoot = Join-Path $RepositoryRoot 'tools\tauri-spike'
$registry = 'https://registry.npmjs.org'
$displayCommand = 'npm --prefix tools/tauri-spike audit --registry=https://registry.npmjs.org --json'

$raw = $null
$exitCode = $null
$parsed = $null
if ($node -and $npm) {
    $raw = @(& $npm.Source --prefix $toolRoot audit `
        "--registry=$registry" --json 2>$null) -join "`n"
    $exitCode = $LASTEXITCODE
    try {
        $parsed = $raw | ConvertFrom-Json
    } catch {
        $parsed = $null
    }
}

$total = $null
if ($parsed -and
    ($parsed.PSObject.Properties.Name -contains 'metadata') -and
    $parsed.metadata -and
    ($parsed.metadata.PSObject.Properties.Name -contains 'vulnerabilities')) {
    $total = $parsed.metadata.vulnerabilities.total
}
$passed = [bool]$node -and [bool]$npm -and $exitCode -eq 0 -and $total -eq 0

[ordered]@{
    schema = 'nana.tauri.npm_audit.v1'
    passed = $passed
    command = $displayCommand
    registry = $registry
    node_executable = [bool]$node
    npm_executable = [bool]$npm
    exit_code = $exitCode
    vulnerabilities_total = $total
} | ConvertTo-Json -Depth 4

if (-not $passed) {
    exit 1
}
