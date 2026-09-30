# Install bizbuy on Windows (PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Clones the repo to %USERPROFILE%\.bizbuy\app, creates a private Python
# environment in %USERPROFILE%\.bizbuy\venv, and adds its Scripts folder to
# your user PATH so `bizbuy` works in any new terminal.
# Re-running it is safe: an existing install is updated instead.
# Env overrides: BIZBUY_HOME, BIZBUY_BRANCH, BIZBUY_REPO.
$ErrorActionPreference = "Stop"

$Repo    = if ($env:BIZBUY_REPO) { $env:BIZBUY_REPO } else { "https://github.com/hsl1291/Business-Purchase.git" }
$HomeDir = if ($env:BIZBUY_HOME) { $env:BIZBUY_HOME } else { Join-Path $env:USERPROFILE ".bizbuy" }
$App     = Join-Path $HomeDir "app"
$Venv    = Join-Path $HomeDir "venv"
$Scripts = Join-Path $Venv "Scripts"

function Die($msg) { Write-Host "error: $msg" -ForegroundColor Red; exit 1 }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Die "git is required. Install Git for Windows from https://git-scm.com/download/win and re-run."
}

# Prefer the py launcher; fall back to python on PATH. Require 3.10+.
$PyExe = $null; $PyArgs = @()
$VersionCheck = "import sys; sys.exit(sys.version_info < (3, 10))"
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c $VersionCheck
    if ($LASTEXITCODE -eq 0) { $PyExe = "py"; $PyArgs = @("-3") }
}
if (-not $PyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c $VersionCheck
    if ($LASTEXITCODE -eq 0) { $PyExe = "python" }
}
if (-not $PyExe) { Die "Python 3.10+ is required. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and re-run." }

New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
if (Test-Path (Join-Path $App ".git")) {
    Write-Host "Existing install found; updating..."
    git -C $App pull --ff-only
} elseif ($env:BIZBUY_BRANCH) {
    git clone --branch $env:BIZBUY_BRANCH $Repo $App
} else {
    git clone $Repo $App
}
if ($LASTEXITCODE -ne 0) { Die "git failed (if the repo is private, sign in when Git prompts you)." }

$VenvPy = Join-Path $Scripts "python.exe"
if (-not (Test-Path $VenvPy)) { & $PyExe @PyArgs -m venv $Venv }
& $VenvPy -m pip install --quiet --upgrade pip
& $VenvPy -m pip install --quiet -e $App
if ($LASTEXITCODE -ne 0) { Die "pip install failed." }

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($UserPath -split ";") -contains $Scripts)) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$Scripts", "User")
    Write-Host "Added $Scripts to your PATH (open a new terminal for it to take effect)."
}

Write-Host ""
& (Join-Path $Scripts "bizbuy.exe") version
Write-Host "Get started (new terminal):  bizbuy init $env:USERPROFILE\BizBuy; cd $env:USERPROFILE\BizBuy; bizbuy run samples\sample_raw_licenses.csv"
Write-Host "Update later: bizbuy update"
