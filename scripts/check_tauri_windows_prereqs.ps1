[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

function Resolve-Executable {
    param([string]$Name, [string[]]$Candidates)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Invoke-VersionProbe {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    if (-not $Executable) {
        return [ordered]@{
            passed = $false
            exit_code = $null
            output = $null
        }
    }
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = @(& $Executable @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    $cleanOutput = @(
        $output |
            ForEach-Object { $_.ToString() } |
            Where-Object { $_ -notmatch '^(info|warn):' }
    )
    return [ordered]@{
        passed = $exitCode -eq 0
        exit_code = $exitCode
        output = ($cleanOutput -join "`n").Trim()
    }
}

$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
$rustup = Resolve-Executable 'rustup' @((Join-Path $cargoBin 'rustup.exe'))
$rustc = Resolve-Executable 'rustc' @((Join-Path $cargoBin 'rustc.exe'))
$cargo = Resolve-Executable 'cargo' @((Join-Path $cargoBin 'cargo.exe'))
$node = Resolve-Executable 'node' @()
$npmCandidates = if ($node) {
    @((Join-Path (Split-Path -Parent $node) 'npm.cmd'))
} else {
    @()
}
$npm = Resolve-Executable 'npm.cmd' $npmCandidates

$vswhere = Resolve-Executable 'vswhere' @(
    'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
)
$vsInstance = $null
if ($vswhere) {
    $vsJson = & $vswhere -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
        -format json
    $instances = @($vsJson | ConvertFrom-Json)
    if ($instances.Count -gt 0) {
        $vsInstance = $instances[0]
    }
}

$cl = $null
$link = $null
if ($vsInstance) {
    $toolsRoot = Join-Path $vsInstance.installationPath 'VC\Tools\MSVC'
    $toolsVersion = Get-ChildItem -LiteralPath $toolsRoot -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($toolsVersion) {
        $cl = Join-Path $toolsVersion.FullName 'bin\Hostx64\x64\cl.exe'
        $link = Join-Path $toolsVersion.FullName 'bin\Hostx64\x64\link.exe'
    }
}

$kits = Get-ItemProperty `
    'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' `
    -ErrorAction SilentlyContinue
$kitsRoot = if ($kits) { $kits.KitsRoot10 } else { $null }
$sdkVersion = $null
if ($kitsRoot) {
    $sdkVersion = Get-ChildItem -LiteralPath (Join-Path $kitsRoot 'Lib') -Directory |
        Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName 'um\x64\kernel32.lib')
        } |
        Sort-Object Name -Descending |
        Select-Object -First 1 -ExpandProperty Name
}

$webView = Get-ItemProperty `
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\*' `
    -ErrorAction SilentlyContinue |
    Where-Object { $_.name -like '*WebView2*' } |
    Select-Object -First 1

$tauriCli = Join-Path $RepositoryRoot 'tools\tauri-spike\node_modules\.bin\tauri.cmd'
$toolPackage = Get-Content -Raw `
    (Join-Path $RepositoryRoot 'tools\tauri-spike\package.json') |
    ConvertFrom-Json
$expectedTauriVersion = $toolPackage.devDependencies.'@tauri-apps/cli'
$rustupProbe = Invoke-VersionProbe $rustup @('--version')
$rustcProbe = Invoke-VersionProbe $rustc @('--version')
$cargoProbe = Invoke-VersionProbe $cargo @('--version')
$nodeProbe = Invoke-VersionProbe $node @('--version')
$npmProbe = Invoke-VersionProbe $npm @('--version')
$tauriProbe = Invoke-VersionProbe $tauriCli @('--version')
$activeToolchainProbe = Invoke-VersionProbe $rustup @('show', 'active-toolchain')
$activeToolchain = $activeToolchainProbe.output
$tagRef = 'refs/tags/v0.3.0-dev-d3-final'
$tagCommit = (& git -C $RepositoryRoot rev-parse "$tagRef^{}" 2>$null)
$tagParent = if ($LASTEXITCODE -eq 0) {
    (& git -C $RepositoryRoot rev-parse "$tagRef^{}^" 2>$null)
} else {
    $null
}

$checks = [ordered]@{
    rustup = [ordered]@{
        passed = $rustupProbe.passed
        exit_code = $rustupProbe.exit_code
        version = $rustupProbe.output
    }
    rustc_msvc = [ordered]@{
        passed = $rustcProbe.passed -and
            ($activeToolchain -match 'x86_64-pc-windows-msvc')
        exit_code = $rustcProbe.exit_code
        version = $rustcProbe.output
        active_toolchain = $activeToolchain
    }
    cargo = [ordered]@{
        passed = $cargoProbe.passed
        exit_code = $cargoProbe.exit_code
        version = $cargoProbe.output
    }
    node = [ordered]@{
        passed = $nodeProbe.passed -and ($nodeProbe.output -match '^v\d+\.\d+\.\d+$')
        exit_code = $nodeProbe.exit_code
        version = $nodeProbe.output
    }
    npm = [ordered]@{
        passed = $npmProbe.passed -and ($npmProbe.output -match '^\d+\.\d+\.\d+$')
        exit_code = $npmProbe.exit_code
        version = $npmProbe.output
    }
    msvc_cpp = [ordered]@{
        passed = [bool]$vsInstance -and [bool]$cl -and [bool]$link -and
            (Test-Path -LiteralPath $cl) -and
            (Test-Path -LiteralPath $link)
        installation_version = if ($vsInstance) { $vsInstance.installationVersion } else { $null }
    }
    windows_sdk = [ordered]@{
        passed = [bool]$sdkVersion
        version = $sdkVersion
    }
    webview2 = [ordered]@{
        passed = [bool]$webView
        version = if ($webView) { $webView.pv } else { $null }
    }
    project_local_tauri_cli = [ordered]@{
        passed = $tauriProbe.passed -and
            ($tauriProbe.output -eq "tauri-cli $expectedTauriVersion")
        exit_code = $tauriProbe.exit_code
        version = $tauriProbe.output
        expected_version = $expectedTauriVersion
    }
    d3_baseline_ref = [ordered]@{
        passed = ($tagCommit -eq '2ad24de9bdc166b7c04bd1124bd7054c95c2ce63') -and
            ($tagParent -eq '278f3a4186d7d0f85f6caf715c2882d63c589fc6')
        ref = $tagRef
        commit = $tagCommit
        parent = $tagParent
    }
}

$passed = @($checks.Values | Where-Object { -not $_.passed }).Count -eq 0
$result = [ordered]@{
    schema = 'nana.tauri.windows_prerequisites.v1'
    passed = $passed
    checks = $checks
}
$result | ConvertTo-Json -Depth 6
if (-not $passed) {
    exit 1
}
