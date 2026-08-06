# Install / repair app dependencies into the selected Python
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,

    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Continue"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

$PipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"
$PipHost = "pypi.tuna.tsinghua.edu.cn"

function Write-Info([string]$Message) { Write-Host "[INFO] $Message" }
function Write-Warn([string]$Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red }

function Get-PythonVersion {
    $out = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
    return "$out".Trim()
}

function Test-PythonImport {
    param([string]$Code)
    $p = Start-Process -FilePath $PythonExe -ArgumentList @("-c", $Code) -Wait -PassThru -WindowStyle Hidden
    return ($p.ExitCode -eq 0)
}

function Invoke-PipForeground {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$PipArguments,

        [string]$Label = ""
    )
    if ($Label) { Write-Info $Label }
    Write-Info ("Command: `"$PythonExe`" -u -m pip " + ($PipArguments -join " "))
    Write-Host "---------- pip output begin ----------" -ForegroundColor DarkGray

    $allArgs = @("-u", "-m", "pip") + $PipArguments + @(
        "-i", $PipIndex,
        "--trusted-host", $PipHost,
        "--no-warn-script-location",
        "--progress-bar", "on"
    )

    # Call pip in-process so logs appear immediately in this window
    & $PythonExe @allArgs
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }

    Write-Host "---------- pip output end (exit $code) ----------" -ForegroundColor DarkGray
    Write-Host ""
    return $code
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Err "Python not found: $PythonExe"
    exit 1
}

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path $PSScriptRoot -Parent
}
$ProjectRoot = $ProjectRoot.TrimEnd('\', '/')

$ReqFile = Join-Path $ProjectRoot "requirements.txt"
if (-not (Test-Path -LiteralPath $ReqFile)) {
    Write-Err "requirements file not found: $ReqFile"
    exit 1
}

$pyVer = Get-PythonVersion
Write-Info "Python version: $pyVer"
if ($pyVer -match '^3\.(1[4-9]|[2-9]\d)\.') {
    Write-Warn "Python $pyVer may not have cadquery-ocp wheels."
    Write-Warn "Recommended: install Python 3.12 and recreate venv."
    Write-Warn "Download: https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
}

Write-Info "Checking dependencies..."
if (Test-PythonImport "import flask, openpyxl, cadquery; from OCP.StlAPI import StlAPI_Reader") {
    Write-Info "Dependencies already installed."
    exit 0
}

Write-Info "Dependencies missing. Installing now..."
Write-Info "Pip mirror: $PipIndex"
Write-Info "Using: $ReqFile"
Write-Warn "cadquery-ocp is large; download may take several minutes."
Write-Host ""

$code = Invoke-PipForeground -Label "[1/2] Upgrade pip..." -PipArguments @("install", "--upgrade", "pip")
if ($code -ne 0) {
    Write-Warn "pip upgrade failed, continue installing packages..."
}

$code = Invoke-PipForeground -Label "[2/2] Install requirements..." -PipArguments @("install", "-r", $ReqFile)
if ($code -ne 0) {
    Write-Err "requirements install failed (exit $code)"
    Write-Host ""
    Write-Err "Common fixes:"
    Write-Err "1) Use Python 3.11 or 3.12 (not 3.14)"
    Write-Err "2) Delete the local venv folder and reinstall dependencies"
    Write-Err "3) Check network access to $PipIndex"
    exit 1
}

Write-Info "Verifying imports..."
if (-not (Test-PythonImport "import flask, openpyxl, cadquery; from OCP.StlAPI import StlAPI_Reader")) {
    Write-Err "dependency verification failed"
    exit 1
}

Write-Info "Dependencies installed successfully."
exit 0
