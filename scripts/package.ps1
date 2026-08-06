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

# 按款式复制：assets/{models,fonts}/<style_id>/
function Copy-StyleAssets([string]$SrcRoot, [string]$DstRoot, [string[]]$Extensions) {
    if (-not (Test-Path $SrcRoot)) { return }
    New-Item -ItemType Directory -Force -Path $DstRoot | Out-Null
    Get-ChildItem -LiteralPath $SrcRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $dst = Join-Path $DstRoot $_.Name
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -LiteralPath $_.FullName -File -ErrorAction SilentlyContinue |
            Where-Object { $Extensions -contains $_.Extension.ToLowerInvariant() } |
            Copy-Item -Destination $dst -Force
    }
    # 兼容旧布局：根目录下直接放文件
    Get-ChildItem -LiteralPath $SrcRoot -File -ErrorAction SilentlyContinue |
        Where-Object { $Extensions -contains $_.Extension.ToLowerInvariant() } |
        Copy-Item -Destination $DstRoot -Force
}

Copy-StyleAssets -SrcRoot (Join-Path $Root "assets\models") -DstRoot (Join-Path $Stage "assets\models") -Extensions @(".stl")
Copy-StyleAssets -SrcRoot (Join-Path $Root "assets\fonts") -DstRoot (Join-Path $Stage "assets\fonts") -Extensions @(".ttf", ".otf")

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
2. Create venv and install deps:
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   (or: powershell -File scripts\install_deps.ps1)
3. python app.py
4. Open http://127.0.0.1:5001
"@
Set-Content -Path (Join-Path $Stage "README-RUN.txt") -Value $Readme -Encoding UTF8

Write-Host "[2/2] Compressing ZIP..."
if (Test-Path $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal -Force

Write-Host "Done"
Write-Host "Output: $ZipPath"
explorer.exe /select,"$ZipPath"
