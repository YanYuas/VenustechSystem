#Requires -Version 5.1
<#
.SYNOPSIS
  启明星系统 · 环境初始化（唯一安装实现，D-11）

.DESCRIPTION
  根目录的 setup.bat 只是本脚本的薄转发壳（3-5 行）。

  它只准备依赖，**从不碰 git**（历史事故：旧初始化脚本会执行
  `git add -A` + `git commit`）。

  步骤：
    1/5 工具检查（Python 3.11+ / Node.js 18+；uv 可选，装了就用它加速）
    2/5 创建后端 venv（backend\.venv）
    3/5 安装后端依赖（requirements-dev.txt，它 -r 了 requirements.txt；
        与 ADR-0005「新机器 setup 装得全、pytest 不再是幽灵依赖」一致）
    4/5 安装前端依赖（npm install）
    5/5 完成提示

.PARAMETER WhatIf
  只打印将要执行的命令，不创建 venv、不装依赖。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File ops\setup.ps1
.EXAMPLE
  setup.bat -WhatIf
#>
param(
    [switch]$WhatIf
)

$script:Root = Split-Path -Parent $PSScriptRoot
$script:Backend = Join-Path $Root 'backend'
$script:Frontend = Join-Path $Root 'frontend'
$script:VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$script:IsWhatIf = [bool]$WhatIf

function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host '========================================' -ForegroundColor Cyan
}

function Write-Info([string]$Text) { Write-Host "  $Text" }
function Write-Ok([string]$Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Plan([string]$Text) { Write-Host "  [WHATIF] $Text" -ForegroundColor Magenta }
function Write-Step([string]$Text) { Write-Host "[$Text]" -ForegroundColor Yellow }

function Test-ConsoleInteractive {
    if ($script:IsWhatIf) { return $false }
    try { return (-not [Console]::IsInputRedirected) } catch { return $false }
}

function Fail([string]$Message, [string]$Hint = '') {
    Write-Host ''
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    if ($Hint -ne '') { Write-Host "        $Hint" -ForegroundColor Red }
    if (Test-ConsoleInteractive) {
        Write-Host ''
        Write-Host 'Press Enter to exit...' -ForegroundColor Yellow
        Read-Host | Out-Null
    }
    exit 1
}

function Write-CommandPlan([string]$Exe, [string[]]$ArgList, [string]$WorkingDirectory) {
    $quoted = @()
    foreach ($a in $ArgList) {
        if ($a -match '\s') { $quoted += '"' + $a + '"' } else { $quoted += $a }
    }
    Write-Plan ("would run: `"{0}`" {1}   (cwd={2})" -f $Exe, ($quoted -join ' '), $WorkingDirectory)
}

# ------------------------------------------------------------------
Write-Host ''
Write-Host 'Qimingxing - environment setup (single implementation)' -ForegroundColor Cyan
if ($script:IsWhatIf) { Write-Host '  -WhatIf: nothing will be installed (plan only).' -ForegroundColor Magenta }
Write-Info "repo    : $Root"

Write-Section 'Environment setup'

# --- 1/5 tools ---
Write-Step '1/5'
Write-Info 'checking tools ...'
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCmd) {
    Fail 'python not found. Install Python 3.11+ first.'
}
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $nodeCmd) {
    Fail 'node not found. Install Node.js 18+ first.'
}
$uvExe = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($null -ne $uvExe) {
    Write-Info 'uv: found - will be used for backend deps'
} else {
    Write-Info 'uv: not found - falling back to pip'
}
Write-Info "python: $($pythonCmd.Source)"
Write-Info "node  : $($nodeCmd.Source)"

# --- 2/5 venv ---
Write-Step '2/5'
Write-Info 'preparing backend venv (backend\.venv) ...'
if (Test-Path -LiteralPath $VenvPython) {
    Write-Info 'venv already exists - reusing'
    if ($script:IsWhatIf) { Write-Plan 'would verify: test -f backend\.venv\Scripts\python.exe' }
} else {
    if ($null -ne $uvExe) {
        $venvArgs = @('venv', (Join-Path $Backend '.venv'))
        $venvExe = $uvExe
    } else {
        $venvArgs = @('-m', 'venv', (Join-Path $Backend '.venv'))
        $venvExe = $pythonCmd.Source
    }
    if ($script:IsWhatIf) {
        Write-CommandPlan $venvExe $venvArgs $Root
        Write-Plan 'would then verify backend\.venv\Scripts\python.exe exists'
    } else {
        Write-Info "creating venv: $venvExe $($venvArgs -join ' ')"
        & $venvExe @venvArgs
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
            Fail 'failed to create venv. Check the python/uv output above.'
        }
        Write-Ok 'venv created'
    }
}

# --- 3/5 backend deps ---
Write-Step '3/5'
$reqFile = Join-Path $Backend 'requirements-dev.txt'
if (-not (Test-Path -LiteralPath $reqFile)) {
    $reqFile = Join-Path $Backend 'requirements.txt'
}
Write-Info "installing backend dependencies ($([System.IO.Path]::GetFileName($reqFile))) ..."
if ($script:IsWhatIf) {
    if ($null -ne $uvExe) {
        $pipArgs = @('pip', 'install', '-r', $reqFile, '--python', $VenvPython)
        Write-CommandPlan $uvExe $pipArgs $Root
    } else {
        $pipArgs = @('-m', 'pip', 'install', '-r', $reqFile)
        Write-CommandPlan $VenvPython $pipArgs $Backend
    }
    Write-Plan 'would then verify: "import fastapi, uvicorn"'
} else {
    if ($null -ne $uvExe) {
        & $uvExe pip install -r $reqFile --python $VenvPython
    } else {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $reqFile
    }
    if ($LASTEXITCODE -ne 0) { Fail 'backend deps install failed. See output above.' }
    & $VenvPython -c 'import fastapi, uvicorn' 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail 'backend deps still missing after install. See output above.'
    }
    Write-Ok 'backend deps OK'
}

# --- 4/5 frontend deps ---
Write-Step '4/5'
Write-Info 'installing frontend dependencies (npm install) ...'
if ($script:IsWhatIf) {
    Write-CommandPlan 'npm.cmd' @('install') $Frontend
} else {
    Push-Location $Frontend
    try {
        & npm.cmd install
        $npmRc = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($npmRc -ne 0) { Fail 'npm install failed. See output above.' }
    Write-Ok 'frontend deps OK'
}

# --- 5/5 done ---
Write-Step '5/5'
if ($script:IsWhatIf) {
    Write-Plan 'setup plan complete - nothing was installed.'
    exit 0
}

Write-Section 'Setup complete'
Write-Info 'Next: double-click start-dev.bat'
Write-Host ''
Write-Info '  Backend : 127.0.0.1:8765 (migrations + seed run on first start)'
Write-Info '  Frontend: http://localhost:5173'
Write-Host ''
Write-Info 'For phone access instead: start-mobile.bat'
Write-Host ''
Write-Info 'All launchers delegate to ops\start.ps1 (single implementation, D-11).'
Write-Host ''
Write-Host 'Press Enter to exit...' -ForegroundColor Yellow
if (Test-ConsoleInteractive) { Read-Host | Out-Null }
exit 0
