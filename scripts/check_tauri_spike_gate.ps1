[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

$gatePath = Join-Path $PSScriptRoot 'check_tauri_spike_gate.ps1'
$trustedGateSha256 = ([string]$env:NANA_TAURI_GATE_SHA256).Trim().ToLowerInvariant()
if ($trustedGateSha256 -notmatch '^[0-9a-f]{64}$' -or
    (Get-FileHash -Algorithm SHA256 -LiteralPath $gatePath).Hash.ToLowerInvariant() -ne $trustedGateSha256) {
    throw 'gate script does not match its trusted detached SHA-256 baseline'
}

function Normalize-RepoPath {
    param([string]$Path)
    $normalized = $Path.Replace('\', '/')
    $normalized = $normalized -replace '^(?:\./)+', ''
    if ($normalized -match '(^|/)\.\.(?:/|$)') {
        throw "repository path contains a parent traversal: $Path"
    }
    return $normalized
}

function Test-NoReparseTree {
    param([string]$RootPath)
    $root = Get-Item -LiteralPath $RootPath -Force
    if (($root.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "reparse point is not allowed at the audited root: $RootPath"
    }
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($root.FullName)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($item in @(Get-ChildItem -LiteralPath $current -Force -ErrorAction Stop)) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "reparse point is not allowed in the audited tree: $($item.FullName)"
            }
            if ($item.PSIsContainer) {
                $pending.Push($item.FullName)
            }
        }
    }
}

function Test-AllowedWorktreePath {
    param(
        [string]$Path,
        [object]$Policy,
        [string]$RootPath
    )
    $normalized = Normalize-RepoPath $Path
    if (@($Policy.allowed_exact) -contains $normalized) {
        return $true
    }
    if (@($Policy.trusted_exact) -contains $normalized) {
        $trustedFile = Join-Path $RootPath ($normalized -replace '/', '\\')
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $trustedFile).Hash.ToLowerInvariant() -eq $trustedGateSha256
    }
    foreach ($prefix in @($Policy.allowed_prefixes)) {
        if ($normalized.StartsWith([string]$prefix, [System.StringComparison]::Ordinal)) {
            return $true
        }
    }
    return $false
}

$worktreePolicyPath = Join-Path $RepositoryRoot 'config\tauri-stage1-worktree-allowlist.json'
$expectedWorktreePolicySha256 = '039fd4945e22bd7dbe0021086c5c416c4399c19eeba5d4f0c84614a7550216b0'
$actualWorktreePolicySha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $worktreePolicyPath).Hash.ToLowerInvariant()
if ($actualWorktreePolicySha256 -ne $expectedWorktreePolicySha256) {
    throw "worktree allowlist does not match the gate's trusted baseline"
}
$worktreePolicy = Get-Content -Raw $worktreePolicyPath | ConvertFrom-Json
Test-NoReparseTree (Join-Path $RepositoryRoot 'src-tauri')

$tauriConfigPath = Join-Path $RepositoryRoot 'src-tauri\tauri.conf.json'
$expectedTauriConfigSha256 = '89fa1a09c3713e96302ebd66267c652bfe44191bf7ff977055d32f5bc5190cd5'
$actualTauriConfigSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $tauriConfigPath).Hash.ToLowerInvariant()
if ($actualTauriConfigSha256 -ne $expectedTauriConfigSha256) {
    throw 'Tauri configuration does not match the trusted frontend build target baseline'
}
$tauriConfig = Get-Content -Raw -LiteralPath $tauriConfigPath | ConvertFrom-Json
if ($tauriConfig.build.frontendDist -ne '../nana_web/dist' -or
    $tauriConfig.build.beforeBuildCommand -ne 'npm run build') {
    throw 'Tauri frontendDist or beforeBuildCommand is outside the trusted baseline'
}

$frontendPackagePath = Join-Path $RepositoryRoot 'nana_web\package.json'
$expectedFrontendPackageSha256 = '39c4f335c3c39d2dafb177d55c1e155571f46ccb6635be5b8d6408f5d8fa73ce'
$actualFrontendPackageSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $frontendPackagePath).Hash.ToLowerInvariant()
if ($actualFrontendPackageSha256 -ne $expectedFrontendPackageSha256) {
    throw 'frontend package.json does not match the trusted build command baseline'
}
$frontendPackage = Get-Content -Raw -LiteralPath $frontendPackagePath | ConvertFrom-Json
if ($frontendPackage.scripts.build -ne 'vite build') {
    throw 'frontend build command is outside the trusted baseline'
}
$stageManifestPath = Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-stage1-static-shell-manifest.txt'
$stageManifestDigestPath = Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-stage1-static-shell-manifest.sha256'
$expectedStageManifestSha256 = '57bafa1d1083720b60e9f68e502092cdba7d365a54d086a3761790180039d0a7'
$actualStageManifestSha256 = (Get-Content -Raw -LiteralPath $stageManifestDigestPath).Trim().ToLowerInvariant()
if ($actualStageManifestSha256 -ne $expectedStageManifestSha256) {
    throw 'stage evidence manifest does not match the gate trusted baseline'
}
$changedPaths = @(
    & git -C $RepositoryRoot diff --name-only HEAD --
    & git -C $RepositoryRoot ls-files --others --exclude-standard
) | Where-Object { $_ -and -not (Test-AllowedWorktreePath $_ $worktreePolicy $RepositoryRoot) }
$changedPaths = @($changedPaths)
$worktreePassed = $changedPaths.Count -eq 0
[ordered]@{
    schema = 'nana.tauri.stage1_worktree_audit.v1'
    passed = $worktreePassed
    rejected_paths = @($changedPaths | ForEach-Object { Normalize-RepoPath $_ })
} | ConvertTo-Json -Depth 4

if (-not $worktreePassed) {
    exit 1
}

& git -C $RepositoryRoot diff HEAD --check
$diffCheckExit = $LASTEXITCODE
if ($diffCheckExit -ne 0) {
    exit 1
}

& (Join-Path $PSScriptRoot 'check_tauri_windows_prereqs.ps1') `
    -RepositoryRoot $RepositoryRoot
$preflightExit = $LASTEXITCODE
& (Join-Path $PSScriptRoot 'check_tauri_npm_audit.ps1') `
    -RepositoryRoot $RepositoryRoot
$auditExit = $LASTEXITCODE

& (Join-Path $PSScriptRoot 'check_tauri_frontend_npm_audit.ps1') `
    -RepositoryRoot $RepositoryRoot
$frontendAuditDependencyExit = $LASTEXITCODE

$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
$env:Path = "$cargoBin;$env:Path"
$tauriCli = Join-Path $RepositoryRoot 'tools\tauri-spike\node_modules\.bin\tauri.cmd'
& $tauriCli build --no-bundle --config (Join-Path $RepositoryRoot 'src-tauri\tauri.conf.json')
$tauriBuildExit = $LASTEXITCODE

& python (Join-Path $PSScriptRoot 'check_tauri_frontend_dist.py') `
    --dist (Join-Path $RepositoryRoot 'nana_web\dist')
$frontendAuditExit = $LASTEXITCODE

$manifestArguments = @(
    (Join-Path $RepositoryRoot 'scripts\refresh_evidence_manifest.py'),
    (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-stage1-static-shell-manifest.txt'),
    '--check',
    '--scope', (Join-Path $RepositoryRoot 'config\tauri-stage1-worktree-allowlist.json'),
    '--scope', (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-stage1-static-shell.json'),
    '--scope', (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-cargo-audit-20260817.json'),
    '--scope', (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-spike-entry-manifest.sha256'),
    '--scope', (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-spike-entry-manifest.txt'),
    '--scope', (Join-Path $RepositoryRoot 'docs\tauri_stage1_static_shell_20260817.md'),
    '--scope', (Join-Path $RepositoryRoot 'nana_web\dist'),
    '--scope', (Join-Path $RepositoryRoot 'nana_web\package-lock.json'),
    '--scope', (Join-Path $RepositoryRoot 'nana_web\package.json'),
    '--scope', (Join-Path $RepositoryRoot 'nana_web\src\main.tsx'),
    '--scope', (Join-Path $RepositoryRoot 'scripts\check_tauri_cargo_audit.ps1'),
    '--scope', (Join-Path $RepositoryRoot 'scripts\check_tauri_frontend_npm_audit.ps1'),
    '--scope', (Join-Path $RepositoryRoot 'scripts\check_tauri_frontend_dist.py'),
    '--scope', (Join-Path $RepositoryRoot 'scripts\refresh_evidence_manifest.py'),
    '--scope', (Join-Path $RepositoryRoot 'src-tauri'),
    '--exclude', (Join-Path $RepositoryRoot 'src-tauri\target'),
    '--exclude', (Join-Path $RepositoryRoot 'src-tauri\gen'),
    '--scope', (Join-Path $RepositoryRoot 'tests\test_tauri_static_shell.py'),
    '--scope', (Join-Path $RepositoryRoot 'tools\tauri-spike\package-lock.json'),
    '--scope', (Join-Path $RepositoryRoot 'tools\tauri-spike\package.json')
)
& python @manifestArguments
$manifestExit = $LASTEXITCODE

 $cargoAuditOutput = @(& (Join-Path $PSScriptRoot 'check_tauri_cargo_audit.ps1') `
    -RepositoryRoot $RepositoryRoot 2>&1)
$cargoAuditExit = $LASTEXITCODE
$cargoAuditOutput | Write-Output
$cargoAuditResult = $cargoAuditOutput -join "`n" | ConvertFrom-Json
$cargoEvidence = Get-Content -Raw (Join-Path $RepositoryRoot 'docs\evidence\v0.3.0-dev-tauri-cargo-audit-20260817.json') | ConvertFrom-Json
$cargoEvidenceMatches =
    $cargoAuditResult.status -eq $cargoEvidence.status -and
    $cargoAuditResult.cargo_audit_version -eq $cargoEvidence.tool -and
    $cargoAuditResult.exit_code -eq $cargoEvidence.exit_code -and
    $cargoAuditResult.vulnerabilities.count -eq $cargoEvidence.vulnerabilities
$cargoEvidenceExit = if ($cargoEvidenceMatches) { 0 } else { 1 }
if (-not $cargoEvidenceMatches) {
    Write-Error 'cargo-audit output does not match the checked-in evidence record'
}

if ($preflightExit -ne 0 -or $auditExit -ne 0 -or
    $frontendAuditDependencyExit -ne 0 -or $tauriBuildExit -ne 0 -or
    $frontendAuditExit -ne 0 -or
    $manifestExit -ne 0 -or
    $cargoAuditExit -ne 0 -or $cargoEvidenceExit -ne 0) {
    exit 1
}
