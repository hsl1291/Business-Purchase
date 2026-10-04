# Install BizBuy on Windows.
#
# Easiest: double-click "Install BizBuy.cmd" (it runs this script).
# Or from PowerShell:  powershell -ExecutionPolicy Bypass -File install.ps1
#
# What it does:
#   1. Installs Python and Git with winget if they're missing (asks first).
#   2. Clones the app to %USERPROFILE%\.bizbuy\app and gives it a private
#      Python environment in %USERPROFILE%\.bizbuy\venv.
#   3. Adds a "BizBuy" shortcut to the Desktop and Start menu, and puts the
#      `bizbuy` command on your PATH.
# Re-running it is safe: an existing install is updated in place.
# Env overrides: BIZBUY_HOME, BIZBUY_BRANCH, BIZBUY_REPO.
param(
    [switch]$Launch,  # open the app when done
    [switch]$Yes      # don't ask before installing Python/Git
)
$ErrorActionPreference = "Stop"

$Repo    = if ($env:BIZBUY_REPO) { $env:BIZBUY_REPO } else { "https://github.com/hsl1291/Business-Purchase.git" }
$HomeDir = if ($env:BIZBUY_HOME) { $env:BIZBUY_HOME } else { Join-Path $env:USERPROFILE ".bizbuy" }
$App     = Join-Path $HomeDir "app"
$Venv    = Join-Path $HomeDir "venv"
$Scripts = Join-Path $Venv "Scripts"

function Die($msg) { Write-Host "`nerror: $msg" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Find-Python {
    # Prefer the py launcher; fall back to python on PATH. Require 3.10+.
    # (The Microsoft Store "python" stub fails this check, which is what we want.)
    $check = "import sys; sys.exit(sys.version_info < (3, 10))"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -c $check
        if ($LASTEXITCODE -eq 0) { return ,@("py", "-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c $check
        if ($LASTEXITCODE -eq 0) { return ,@("python") }
    }
    return $null
}

function Install-WithWinget($id, $name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }
    if (-not $Yes) {
        $answer = Read-Host "$name is required but not installed. Install it now? [Y/n]"
        if ($answer -match "^[nN]") { return $false }
    }
    Step "Installing $name (a Windows permission prompt may appear)"
    winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    return $true
}

# ---------------------------------------------------------------- prerequisites
Step "Checking for Git and Python"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Install-WithWinget "Git.Git" "Git" | Out-Null
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Die "Git is required. Install Git for Windows from https://git-scm.com/download/win, then run this again."
    }
}
$Py = Find-Python
if (-not $Py) {
    Install-WithWinget "Python.Python.3.12" "Python 3.12" | Out-Null
    $Py = Find-Python
    if (-not $Py) {
        Die "Python 3.10+ is required. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."
    }
}
$PyExe = $Py[0]; $PyArgs = @($Py | Select-Object -Skip 1)

# ---------------------------------------------------------------- app
New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
if (Test-Path (Join-Path $App ".git")) {
    Step "Existing install found; updating"
    git -C $App pull --ff-only
} else {
    Step "Downloading BizBuy (if GitHub asks you to sign in, do so)"
    if ($env:BIZBUY_BRANCH) { git clone --branch $env:BIZBUY_BRANCH $Repo $App } else { git clone $Repo $App }
}
if ($LASTEXITCODE -ne 0) { Die "git failed. If the repo is private, make sure you signed in to GitHub when asked." }

Step "Setting up BizBuy's Python environment (first time takes a few minutes)"
$VenvPy = Join-Path $Scripts "python.exe"
if (-not (Test-Path $VenvPy)) { & $PyExe @PyArgs -m venv $Venv }
& $VenvPy -m pip install --quiet --disable-pip-version-check --upgrade pip
& $VenvPy -m pip install --quiet --disable-pip-version-check -e $App
if ($LASTEXITCODE -ne 0) { Die "Installing BizBuy's dependencies failed (see messages above)." }

# ---------------------------------------------------------------- shortcuts + PATH
Step "Adding shortcuts"
$Exe = Join-Path $Scripts "bizbuy.exe"
$Shell = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
    if (-not $dir) { continue }
    $lnk = $Shell.CreateShortcut((Join-Path $dir "BizBuy.lnk"))
    $lnk.TargetPath = $Exe
    $lnk.Arguments = "gui"
    $lnk.WorkingDirectory = $env:USERPROFILE
    $lnk.Description = "BizBuy: find and value businesses to buy"
    $lnk.Save()
}

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (($UserPath -split ";") -contains $Scripts)) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$Scripts", "User")
}

Write-Host ""
& $Exe version
Write-Host "BizBuy is installed. Open it with the BizBuy shortcut on your Desktop or Start menu." -ForegroundColor Green
Write-Host "Updates: Settings & updates page in the app, or run 'bizbuy update' in a new terminal."

if ($Launch) {
    Step "Opening BizBuy"
    Start-Process -FilePath $Exe -ArgumentList "gui" -WorkingDirectory $env:USERPROFILE
}
