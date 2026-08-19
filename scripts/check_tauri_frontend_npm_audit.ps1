[CmdletBinding()]
param(
    [string]$RepositoryRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}

$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
$registry = 'https://registry.npmjs.org'
$frontendRoot = Join-Path $RepositoryRoot 'nana_web'
$npmCache = Join-Path ([IO.Path]::GetTempPath()) 'nana-tauri-frontend-npm-cache'
[void](New-Item -ItemType Directory -Force -Path $npmCache)
$npmTimeoutMilliseconds = 120000

function Invoke-NpmWithTimeout {
    param(
        [string[]]$Arguments,
        [bool]$CaptureOutput = $true
    )
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $npm.Source
    $startInfo.WorkingDirectory = $RepositoryRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $CaptureOutput
    $startInfo.RedirectStandardError = $CaptureOutput
    $startInfo.Arguments = (($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + $_.Replace('"', '\"') + '"'
        } else {
            $_
        }
    }) -join ' ')
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $completed = $process.WaitForExit($npmTimeoutMilliseconds)
    if (-not $completed) {
        try { $process.Kill($true) } catch { $process.Kill() }
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Output = ''
            Error = 'npm command exceeded the 120 second timeout.'
        }
    }
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        TimedOut = $false
        Output = if ($CaptureOutput) { $process.StandardOutput.ReadToEnd() } else { '' }
        Error = if ($CaptureOutput) { $process.StandardError.ReadToEnd() } else { '' }
    }
}
$result = [ordered]@{
    schema = 'nana.tauri.frontend_npm_audit.v1'
    status = 'NOT_OBTAINED'
    install_command = 'npm --prefix nana_web ci --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org --cache=<temporary-cache>'
    command = 'npm --prefix nana_web audit --registry=https://registry.npmjs.org --json --cache=<temporary-cache>'
    registry = $registry
    install_exit_code = $null
    exit_code = $null
    vulnerabilities_total = $null
    attempts = 0
}

if ($npm) {
    $installResult = Invoke-NpmWithTimeout @('--prefix', $frontendRoot, 'ci', '--ignore-scripts', '--no-audit', '--no-fund', "--registry=$registry", "--cache=$npmCache", '--fetch-timeout=10000', '--fetch-retries=0', '--loglevel=error') $false
    $result.install_exit_code = $installResult.ExitCode
    if ($result.install_exit_code -ne 0) {
        $result.status = 'FAIL_NPM_CI'
    }
}

if ($npm -and $result.install_exit_code -eq 0) {
    do {
        $result.attempts++
        $auditResult = Invoke-NpmWithTimeout @('--prefix', $frontendRoot, 'audit', "--registry=$registry", '--json', "--cache=$npmCache", '--fetch-timeout=10000', '--fetch-retries=0')
        $raw = ($auditResult.Output + $auditResult.Error).Trim()
        $result.exit_code = $auditResult.ExitCode
        if ($result.exit_code -ne 0 -and $result.attempts -lt 2) {
            Start-Sleep -Seconds 1
        }
    } while ($result.exit_code -ne 0 -and $result.attempts -lt 2)
    try {
        $parsed = $raw | ConvertFrom-Json
        $result.vulnerabilities_total = $parsed.metadata.vulnerabilities.total
    } catch {
        $parsed = $null
    }
    if ($result.exit_code -eq 0 -and $result.vulnerabilities_total -eq 0) {
        $result.status = 'PASS_0_VULNERABILITIES'
    } else {
        $result.status = 'FAIL_VULNERABILITIES_OR_TOOL'
    }
}

$result | ConvertTo-Json -Depth 6
if ($result.status -ne 'PASS_0_VULNERABILITIES') {
    exit 1
}
