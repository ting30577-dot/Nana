$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$projectPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$entryPoint = Join-Path $projectRoot "main.py"

if (-not (Test-Path -LiteralPath $projectPython)) {
    throw "Project .venv was not found. Install development dependencies first."
}

Push-Location $projectRoot
try {
    $pyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "Nana"
    )

    # A venv created from Conda needs several runtime DLLs from its base prefix.
    $basePrefix = (& $projectPython -c "import sys; print(sys.base_prefix)").Trim()
    $condaRuntimeDirectory = Join-Path $basePrefix "Library\bin"
    $runtimeDlls = @(
        "ffi.dll",
        "libcrypto-3-x64.dll",
        "libssl-3-x64.dll",
        "liblzma.dll",
        "libbz2.dll",
        "libexpat.dll",
        "sqlite3.dll"
    )
    foreach ($runtimeDll in $runtimeDlls) {
        $runtimePath = Join-Path $condaRuntimeDirectory $runtimeDll
        if (Test-Path -LiteralPath $runtimePath) {
            $pyInstallerArgs += @("--add-binary", "$runtimePath;.")
        }
    }

    $pyInstallerArgs += $entryPoint
    & $projectPython -m PyInstaller @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Host "Build complete: $projectRoot\dist\Nana\Nana.exe"
