param(
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python command not found: $Python"
}

# PyInstaller's Qt hook can misread a virtual-environment path containing
# non-ASCII characters on Windows. Keep build-only dependencies in a stable
# ASCII path so the project can be built from folders with Chinese names.
$buildEnvironment = Join-Path $env:LOCALAPPDATA "VoiceInputAssistantBuild\venv"
$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $buildPython)) {
    & $Python -m venv $buildEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the build environment."
    }
}
& $buildPython -m pip install --disable-pip-version-check -r "requirements-build.txt"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install build dependencies."
}

$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install it before running this script."
}

foreach ($folder in @("build", "dist", "installer-output")) {
    $target = Join-Path $PSScriptRoot $folder
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

& $buildPython -m PyInstaller --noconfirm --clean "voice-assistant.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

& $iscc "installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$installer = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "installer-output") -Filter "*.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $installer) {
    throw "Build finished without an installer executable."
}

Write-Output $installer.FullName
