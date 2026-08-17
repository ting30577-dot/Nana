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

$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
$rustup = Resolve-Executable 'rustup' @((Join-Path $cargoBin 'rustup.exe'))
$rustc = Resolve-Executable 'rustc' @((Join-Path $cargoBin 'rustc.exe'))
$cargo = Resolve-Executable 'cargo' @((Join-Path $cargoBin 'cargo.exe'))

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
$tagRef = 'refs/tags/v0.3.0-dev-d3-final'
$tagCommit = (& git -C $RepositoryRoot rev-parse "$tagRef^{}" 2>$null)
$tagParent = if ($LASTEXITCODE -eq 0) {
    (& git -C $RepositoryRoot rev-parse "$tagRef^{}^" 2>$null)
} else {
    $null
}

$checks = [ordered]@{
    rustup = [ordered]@{
        passed = [bool]$rustup
        version = if ($rustup) { (& $rustup --version | Select-Object -First 1) } else { $null }
    }
    rustc_msvc = [ordered]@{
        passed = [bool]$rustc -and ((& $rustup show active-toolchain) -match 'x86_64-pc-windows-msvc')
        version = if ($rustc) { (& $rustc --version) } else { $null }
    }
    cargo = [ordered]@{
        passed = [bool]$cargo
        version = if ($cargo) { (& $cargo --version) } else { $null }
    }
    msvc_cpp = [ordered]@{
        passed = [bool]$vsInstance -and (Test-Path -LiteralPath $cl) -and
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
        passed = Test-Path -LiteralPath $tauriCli
        version = if (Test-Path -LiteralPath $tauriCli) { (& $tauriCli --version) } else { $null }
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
