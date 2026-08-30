# Build the unsigned onedir Windows folder with PyInstaller.
#
# Usage:
#   scripts\build_windows.ps1
#
# Refuses to run when vendor/ffmpeg/windows/ffmpeg.exe is missing or free disk is
# under 5 GB (override with $env:PIXELART_APP_MIN_FREE_MB). Does not install
# PyInstaller. Run on Windows or Windows CI — not on macOS/Linux.

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Spec = Join-Path $RepoRoot "packaging\windows.spec"
$Ffmpeg = if ($env:PIXELART_FFMPEG_BUNDLE) { $env:PIXELART_FFMPEG_BUNDLE } else { Join-Path $RepoRoot "vendor\ffmpeg\windows\ffmpeg.exe" }
$MinFreeMb = if ($env:PIXELART_APP_MIN_FREE_MB) { [int]$env:PIXELART_APP_MIN_FREE_MB } else { 5120 }
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Die([string]$Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $Spec -PathType Leaf)) {
    Die "missing PyInstaller spec at $Spec"
}

$problems = 0

if (-not (Test-Path -LiteralPath $Ffmpeg -PathType Leaf)) {
    Write-Error @"
bundled ffmpeg is missing at $Ffmpeg.
The onedir bundle cannot convert without it. Build it first (MSYS2 MINGW64):
  scripts/build_ffmpeg_lgpl.sh --platform windows
See scripts/build_ffmpeg_lgpl_windows.md
"@
    $problems = 1
}

$drive = [System.IO.Path]::GetPathRoot($RepoRoot)
$disk = Get-PSDrive -Name ($drive.TrimEnd('\').TrimEnd(':'))
$availableMb = [int]($disk.Free / 1MB)
if ($availableMb -lt $MinFreeMb) {
    Write-Error @"
only ${availableMb} MB free on $drive, need ${MinFreeMb} MB (5 GB).
PyInstaller plus Qt/FFmpeg staging needs several GB. Free disk space before building.
This machine cannot produce the Windows bundle until ffmpeg is built and disk is freed.
"@
    $problems = 1
}

if ($problems -ne 0) {
    Die "cannot build the Windows onedir bundle until the problems above are fixed"
}

try {
    & $Python -c "import PyInstaller" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller not importable"
    }
} catch {
    Die @"
PyInstaller is not installed for $Python.
On a Windows machine with enough disk: pip install pyinstaller
Do not install it on a volume that is already nearly full.
"@
}

Set-Location -LiteralPath $RepoRoot
Write-Host "building unsigned onedir bundle with $Python -m PyInstaller"
& $Python -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) {
    Die "PyInstaller failed with exit code $LASTEXITCODE"
}

$OutDir = Join-Path $RepoRoot "dist\pixelart-converter"
$OutExe = Join-Path $OutDir "pixelart-converter.exe"
if (-not (Test-Path -LiteralPath $OutExe -PathType Leaf)) {
    Die "PyInstaller finished but $OutExe was not created"
}

Write-Host "ok: $OutDir"
Write-Host "Run: $OutExe"
Write-Host "SmartScreen may warn on first launch; see docs/packaging.md"
