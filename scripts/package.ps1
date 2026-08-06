# Package source release (no embedded Python)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host "========================================"
Write-Host "  Package release"
Write-Host "========================================"
Write-Host ""
Write-Host "Packages source files only."
Write-Host "Target PC needs Python 3.11/3.12."
Write-Host ""

$AppName = "plate-number"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$DistRoot = Join-Path $Root "dist"
$Stage = Join-Path $DistRoot $AppName
$ZipPath = Join-Path $DistRoot "$AppName-$Stamp.zip"

if (Test-Path $Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

$ExcludeDirs = @(
    "venv", ".venv", "env", "runtime", "__pycache__", ".git",
    ".idea", ".vscode", "dist", "output", ".pytest_cache", ".mypy_cache"
)

Write-Host "[1/2] Copy project files..."
Get-ChildItem -LiteralPath $Root -Force | Where-Object {
    $ExcludeDirs -notcontains $_.Name
} | ForEach-Object {
    $dest = Join-Path $Stage $_.Name
    if ($_.PSIsContainer) {
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
    } else {
        if ($_.Extension -in @(".zip", ".pyc", ".pyo", ".7z")) { return }
        if ($_.Name -in @("test_output.stl", "verify_output.stl")) { return }
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }
}

$modelsSrc = Join-Path $Root "assets\models"
$fontsSrc = Join-Path $Root "assets\fonts"
$modelsDst = Join-Path $Stage "assets\models"
$fontsDst = Join-Path $Stage "assets\fonts"
New-Item -ItemType Directory -Force -Path $modelsDst | Out-Null
New-Item -ItemType Directory -Force -Path $fontsDst | Out-Null
if (Test-Path $modelsSrc) {
    Get-ChildItem -Path $modelsSrc -Filter *.stl -File -ErrorAction SilentlyContinue |
        Copy-Item -Destination $modelsDst -Force
}
if (Test-Path $fontsSrc) {
    Get-ChildItem -Path $fontsSrc -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".ttf", ".otf") } |
        Copy-Item -Destination $fontsDst -Force
}

# 多款式资源：assets/styles/<style>/{models,fonts}
$stylesSrc = Join-Path $Root "assets\styles"
$stylesDst = Join-Path $Stage "assets\styles"
if (Test-Path $stylesSrc) {
    Get-ChildItem -LiteralPath $stylesSrc -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $styleId = $_.Name
        $dstModels = Join-Path $stylesDst "$styleId\models"
        $dstFonts = Join-Path $stylesDst "$styleId\fonts"
        New-Item -ItemType Directory -Force -Path $dstModels | Out-Null
        New-Item -ItemType Directory -Force -Path $dstFonts | Out-Null
        Get-ChildItem -Path (Join-Path $_.FullName "models") -Filter *.stl -File -ErrorAction SilentlyContinue |
            Copy-Item -Destination $dstModels -Force
        Get-ChildItem -Path (Join-Path $_.FullName "fonts") -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in @(".ttf", ".otf") } |
            Copy-Item -Destination $dstFonts -Force
    }
}

@(
    (Join-Path $Stage "dist"),
    (Join-Path $Stage "runtime"),
    (Join-Path $Stage "venv")
) | ForEach-Object {
    if (Test-Path $_) { Remove-Item -LiteralPath $_ -Recurse -Force }
}

$Readme = @"
Plate Number Keychain

1. Install Python 3.11 or 3.12:
   https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
   (check "Add python.exe to PATH")
2. Double-click start.bat
3. First run installs dependencies (needs network)
4. Open http://127.0.0.1:5001
"@
Set-Content -Path (Join-Path $Stage "README-RUN.txt") -Value $Readme -Encoding UTF8

Write-Host "[2/2] Compressing ZIP..."
if (Test-Path $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal -Force

Write-Host "Done"
Write-Host "Output: $ZipPath"
explorer.exe /select,"$ZipPath"
