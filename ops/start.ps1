#Requires -Version 5.1
<#
.SYNOPSIS
  启明星系统 · 唯一启动实现（D-11 启动器单一实现）

.DESCRIPTION
  根目录的 start-dev.bat / start-demo.bat / start-mobile.bat 与 scripts/dev.ps1
  都只是本脚本的薄转发壳（3-5 行），不再各自复刻 venv 解析 / 依赖探活 /
  端口检查 / 令牌生成 / 数据目录逻辑。

  三种模式：
    dev    后端 FastAPI 127.0.0.1:8765（--reload）+ 前端 Vite 5173 + 开浏览器
    demo   同 dev，但数据目录指向 var\demo（缺库先 seed_demo.py）
    mobile 后端仅回环 8765 + 统一边缘服务 ops/server/server.js 0.0.0.0:3000
           （静态 + /api 代理 + 访问令牌）

  运行期数据统一放仓库根 var/（见 ARCHITECTURE.md §7 / ADR-0004）：
    var\data 真实库 · var\demo 演示库 · var\legacy 历史副本。
  数据目录可由 -DataDir 覆盖；相对路径一律按**仓库根**解析。

  所有校验（venv 是否存在 / 依赖能否 import / node_modules / 端口占用 /
  前端 dist 是否需要构建 / 演示库是否需要 seed）都只在这里实现一次；
  错误提示与退出码沿用原三个启动器与 dev.ps1 的含义。

.PARAMETER Mode
  dev | demo | mobile

.PARAMETER DataDir
  覆盖后端数据目录。默认 dev/mobile 用 var\data、demo 用 var\demo（相对仓库根）；
  传入的相对路径同样按**仓库根**解析（2026-10-27 var/ 迁移后统一基准），
  实际传给后端时一律转成绝对 Windows 路径（Git-Bash 风格 /d/... 会丢盘符）。

.PARAMETER WhatIf
  只打印将要执行的命令 / 环境变量 / 前置检查结果，不启动任何进程。
  （幂等、可重复执行，供 CI 与人工核对。）

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode dev
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File ops\start.ps1 -Mode demo -WhatIf
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -DataDir .\var\data-branch
#>

param(
    [ValidateSet('dev', 'demo', 'mobile')]
    [string]$Mode = 'dev',

    [string]$DataDir = '',

    [switch]$WhatIf
)

# ------------------------------------------------------------------
# 固定路径与状态（全部绝对路径，不依赖调用者的 CWD）
# ------------------------------------------------------------------
$script:Root = Split-Path -Parent $PSScriptRoot
$script:Backend = Join-Path $Root 'backend'
$script:Frontend = Join-Path $Root 'frontend'
$script:VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$script:BackendPort = 8765
$script:FrontendPort = 5173
$script:ServerPort = 3000
$script:IsWhatIf = [bool]$WhatIf
$script:Launched = New-Object System.Collections.ArrayList
$script:StopHint = 'Press Enter to stop the services started by this launcher...'

# ------------------------------------------------------------------
# 输出与错误处理（错误路径保留"窗口不闪退"——历史 bug：start-demo.bat 一闪而过）
# ------------------------------------------------------------------
function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host '========================================' -ForegroundColor Cyan
}

function Write-Info([string]$Text) { Write-Host "  $Text" }
function Write-Ok([string]$Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "  [HINT] $Text" -ForegroundColor Yellow }
function Write-Plan([string]$Text) { Write-Host "  [WHATIF] $Text" -ForegroundColor Magenta }
function Write-Step([string]$Text) { Write-Host "[$Text]" -ForegroundColor Yellow }

function Test-ConsoleInteractive {
    # -WhatIf 永不暂停；被重定向（CI / 管道）时不暂停
    if ($script:IsWhatIf) { return $false }
    try { return (-not [Console]::IsInputRedirected) } catch { return $false }
}

function Stop-Launcher {
    if (Test-ConsoleInteractive) {
        Write-Host ''
        Write-Host 'Press Enter to exit...' -ForegroundColor Yellow
        Read-Host | Out-Null
    }
}

function Fail([string]$Message, [string]$Hint = '') {
    Write-Host ''
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    if ($Hint -ne '') { Write-Host "        $Hint" -ForegroundColor Red }
    Stop-Launcher
    exit 1
}

# ------------------------------------------------------------------
# 前置检查（只读。WhatIf 下同样执行，用于展示真实前提；但不 spawn 进程）
# ------------------------------------------------------------------
function Test-PortListening([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]$conn
    } catch {
        return $false
    }
}

function Get-NodePath {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    return $cmd.Source
}

function Resolve-Python([string]$ModeName) {
    if (Test-Path -LiteralPath $VenvPython) {
        return @{ Path = $VenvPython; IsVenv = $true }
    }
    if ($ModeName -eq 'dev') {
        # 沿用原 start-dev.bat / dev.ps1 的回退语义：允许 PATH python，但明确警告
        Write-Host '  [WARN] project venv not found: backend\.venv' -ForegroundColor Yellow
        Write-Host '         Falling back to `python` on PATH - it may lack backend deps.' -ForegroundColor Yellow
        Write-Host '         Run setup.bat once to create the venv properly.' -ForegroundColor Yellow
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $cmd) {
            Fail 'python not found. Install Python 3.11+ first.'
        }
        return @{ Path = $cmd.Source; IsVenv = $false }
    }
    # demo / mobile：原实现要求 venv 必须存在（不允许回退）
    Fail "project venv not found: backend\.venv" 'Run setup.bat first.'
}

function Test-BackendDeps([string]$PythonPath, [string]$ProbeExpr, [string]$ModeName) {
    if ($script:IsWhatIf) {
        Write-Plan "would verify: `"$PythonPath`" -c `"$ProbeExpr`"  (not executed in -WhatIf)"
        return
    }
    & $PythonPath -c $ProbeExpr 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        switch ($ModeName) {
            'dev' { Fail "backend dependencies missing for: $PythonPath" 'Run setup.bat to install them, then retry.' }
            'demo' { Fail 'backend dependencies missing. Run setup.bat, then retry.' }
            default { Fail 'backend deps missing in the venv. Run setup.bat.' }
        }
    }
}

function Assert-Node {
    $node = Get-NodePath
    if ($null -eq $node) { Fail 'node not found. Install Node.js 18+ first.' }
    return $node
}

function Assert-FrontendDeps {
    if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'node_modules'))) {
        Fail 'frontend deps missing. Run setup.bat, or: cd frontend && npm install'
    }
}

function Get-EffectiveDataDir([string]$DefaultDir) {
    $chosen = $DefaultDir
    if (-not [string]::IsNullOrEmpty($DataDir)) { $chosen = $DataDir }
    if ([System.IO.Path]::IsPathRooted($chosen)) {
        return [System.IO.Path]::GetFullPath($chosen)
    }
    # 相对路径以仓库根为基准（2026-10-27 var/ 迁移后的统一约定，旧约定是 backend\）
    return [System.IO.Path]::GetFullPath((Join-Path $Root $chosen))
}

# ------------------------------------------------------------------
# 进程启动（统一入口，便于 -WhatIf 打印、便于停止整棵进程树）
# ------------------------------------------------------------------
function Show-PlannedCommand([string]$Exe, [string[]]$ArgList, [string]$WorkingDirectory, [string]$Label) {
    $quoted = @()
    foreach ($a in $ArgList) {
        if ($a -match '\s') { $quoted += '"' + $a + '"' } else { $quoted += $a }
    }
    Write-Plan ("would start {0}: `"{1}`" {2}   (cwd={3})" -f $Label, $Exe, ($quoted -join ' '), $WorkingDirectory)
}

function Start-ServiceProcess([string]$Exe, [string[]]$ArgList, [string]$WorkingDirectory, [string]$Label) {
    if ($script:IsWhatIf) {
        Show-PlannedCommand $Exe $ArgList $WorkingDirectory $Label
        return $null
    }
    $proc = Start-Process -FilePath $Exe -ArgumentList $ArgList -WorkingDirectory $WorkingDirectory -PassThru
    [void]$script:Launched.Add($proc)
    Write-Ok ("{0} started (PID {1})" -f $Label, $proc.Id)
    return $proc
}

function Stop-Launched {
    if ($script:IsWhatIf) { return }
    foreach ($proc in $script:Launched) {
        if ($null -eq $proc) { continue }
        # /T 连子进程一起结束（uvicorn --reload 会派生 reloader 子进程）
        & taskkill.exe /T /F /PID $proc.Id 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    $script:Launched.Clear()
    Write-Ok 'services stopped'
}

function Wait-ForServices([int]$Seconds, [int]$Port, [string]$Label) {
    if ($script:IsWhatIf) {
        Write-Plan ("would sleep {0}s, then check port {1} ({2})" -f $Seconds, $Port, $Label)
        return
    }
    Write-Info ("waiting {0}s for {1} ..." -f $Seconds, $Label)
    Start-Sleep -Seconds $Seconds
    if (-not (Test-PortListening $Port)) {
        Write-Note ("port {0} is not listening yet - check the {1} window for errors" -f $Port, $Label)
    } else {
        Write-Ok ("{0} listening on port {1}" -f $Label, $Port)
    }
}

function Open-Browser([string]$Url) {
    if ($script:IsWhatIf) {
        Write-Plan "would open browser: $Url"
        return
    }
    Start-Process $Url
}

function Wait-ForEnterThenStop {
    if ($script:IsWhatIf) { return }
    if (Test-ConsoleInteractive) {
        Write-Host ''
        Write-Host $script:StopHint -ForegroundColor Yellow
        Read-Host | Out-Null
    }
    Stop-Launched
}

# ==================================================================
# dev 模式
# ==================================================================
function Start-DevMode {
    Write-Section 'Qimingxing - DEV start (single implementation)'

    $py = Resolve-Python 'dev'
    Write-Info "Python : $($py.Path)"
    Test-BackendDeps $py.Path 'import uvicorn, fastapi' 'dev'

    $node = Assert-Node
    Write-Info "Node   : $node"
    Assert-FrontendDeps

    if (Test-PortListening $BackendPort) { Write-Note "port $BackendPort in use (backend may already be running)" }
    if (Test-PortListening $FrontendPort) { Write-Note "port $FrontendPort in use (frontend may already be running)" }

    # 数据目录：默认 var\data；-DataDir 覆盖（相对路径按仓库根解析）
    $effectiveDataDir = Get-EffectiveDataDir (Join-Path $Root 'var\data')
    if (-not [string]::IsNullOrEmpty($DataDir)) {
        Write-Info "Data dir: $effectiveDataDir (override; VENUSTECH_DATA_DIR)"
    } else {
        Write-Info "Data dir: $effectiveDataDir (default; VENUSTECH_DATA_DIR)"
    }
    if ($script:IsWhatIf) {
        Write-Plan "would set env VENUSTECH_DATA_DIR=$effectiveDataDir for the backend window"
    }
    $env:VENUSTECH_DATA_DIR = $effectiveDataDir

    Write-Step '1/3'
    $backendArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort", '--reload')
    [void](Start-ServiceProcess $py.Path $backendArgs $Backend 'backend FastAPI')

    Write-Step '2/3'
    [void](Start-ServiceProcess 'npm.cmd' @('run', 'dev') $Frontend 'frontend Vite')

    if ($null -ne $effectiveDataDir) { Remove-Item Env:\VENUSTECH_DATA_DIR -ErrorAction SilentlyContinue }

    Write-Step '3/3'
    [void](Wait-ForServices 8 $BackendPort 'backend FastAPI')
    Open-Browser "http://localhost:$FrontendPort"
    Write-Section 'DEV started'
    Write-Info "Backend : http://127.0.0.1:$BackendPort"
    Write-Info "Frontend: http://localhost:$FrontendPort"
    Wait-ForEnterThenStop
}

# ==================================================================
# demo 模式
# ==================================================================
function Start-DemoMode {
    Write-Section 'Qimingxing - DEMO start (sample data, single implementation)'

    $py = Resolve-Python 'demo'
    Write-Info "Python : $($py.Path)"
    Test-BackendDeps $py.Path 'import uvicorn, fastapi' 'demo'

    [void](Assert-Node)

    $demoDir = Get-EffectiveDataDir (Join-Path $Root 'var\demo')
    Write-Info "Data dir: $demoDir"
    Write-Info '  (your real database - var\data - is NOT touched)'

    $dbFile = Join-Path $demoDir 'app.db'
    if (-not (Test-Path -LiteralPath $dbFile)) {
        Write-Step '1/3'
        Write-Info 'demo database not found - generating it now ...'
        $seedArgs = @('scripts\seed_demo.py', '--reset', '--yes')
        if (-not [string]::IsNullOrEmpty($DataDir)) { $seedArgs += @('--data-dir', $demoDir) }
        if ($script:IsWhatIf) {
            Write-Plan ("would seed: `"{0}`" {1}   (cwd={2})" -f $py.Path, ($seedArgs -join ' '), $Backend)
        } else {
            Push-Location $Backend
            try {
                & $py.Path @seedArgs
                $seedRc = $LASTEXITCODE
            } finally {
                Pop-Location
            }
            if ($seedRc -ne 0) { Fail 'demo data generation failed (exit code >= 1).' }
            if (-not (Test-Path -LiteralPath $dbFile)) {
                Fail "seed finished but $dbFile is missing."
            }
            Write-Ok 'demo data generated'
        }
    } else {
        Write-Step '1/3'
        Write-Info "demo database found: $dbFile"
    }

    Assert-FrontendDeps

    if (Test-PortListening $BackendPort) {
        Fail "port $BackendPort is already in use - another backend is running." 'Close the start-dev.bat / start-mobile.bat window first, then run this file again.'
    }
    if (Test-PortListening $FrontendPort) {
        Fail "port $FrontendPort is already in use - another frontend is running." 'Close it first, then run this file again.'
    }

    Write-Step '2/3'
    Write-Info "Data dir : $demoDir"
    Write-Info "Backend  : 127.0.0.1:$BackendPort"
    Write-Info "Frontend : http://localhost:$FrontendPort"

    $env:VENUSTECH_DATA_DIR = $demoDir
    if ($script:IsWhatIf) { Write-Plan "would set env VENUSTECH_DATA_DIR=$demoDir for the backend window" }
    $backendArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort")
    [void](Start-ServiceProcess $py.Path $backendArgs $Backend 'demo backend FastAPI')
    Remove-Item Env:\VENUSTECH_DATA_DIR -ErrorAction SilentlyContinue

    [void](Start-ServiceProcess 'npm.cmd' @('run', 'dev') $Frontend 'frontend Vite')

    Write-Step '3/3'
    [void](Wait-ForServices 10 $BackendPort 'demo backend')
    Open-Browser "http://localhost:$FrontendPort"

    Write-Section 'DEMO started'
    Write-Info 'If a page shows no data: the backend window must print the data dir and'
    Write-Info 'must NOT contain a ModuleNotFoundError.'
    Wait-ForEnterThenStop
}

# ==================================================================
# mobile 模式（生产/局域网/手机：后端回环 + 统一边缘服务 :3000）
# ==================================================================
function Get-AccessToken([string]$TokenFile) {
    if ($env:QM_TOKEN -ne '' -and $null -ne $env:QM_TOKEN) { return @{ Token = $env:QM_TOKEN.Trim(); Source = 'env QM_TOKEN' } }
    if (Test-Path -LiteralPath $TokenFile) {
        $existing = (Get-Content -LiteralPath $TokenFile -Raw -ErrorAction SilentlyContinue)
        if ($null -ne $existing) {
            $existing = $existing.Trim()
            if ($existing -ne '') { return @{ Token = $existing; Source = '.qm-token' } }
        }
    }
    if ($script:IsWhatIf) { return @{ Token = $null; Source = 'would generate via ops/server/lib/access-token.mjs' } }
    # 单一实现原则：复用边缘服务自己的令牌模块，而不是在启动脚本里再写一份随机数逻辑
    $js = "import { loadAccessTokens } from './ops/server/lib/access-token.mjs'; const r = loadAccessTokens({ tokenFile: './.qm-token' }); process.stdout.write(r.tokens[0] || '');"
    Push-Location $Root
    try {
        $generated = (& node --input-type=module -e $js) -join ''
    } finally {
        Pop-Location
    }
    $generated = "$generated".Trim()
    if ($generated -eq '') { Fail 'failed to generate the access token. Check the python above.' }
    return @{ Token = $generated; Source = '.qm-token (newly generated)' }
}

function Format-TokenMask([string]$Token) {
    if ([string]::IsNullOrEmpty($Token)) { return '(unknown in -WhatIf)' }
    if ($Token.Length -le 8) { return '********' }
    return $Token.Substring(0, 4) + '...' + $Token.Substring($Token.Length - 4)
}

function Start-MobileMode {
    Write-Section 'Qimingxing - MOBILE service start (single implementation)'

    $py = Resolve-Python 'mobile'
    Write-Info "Python : $($py.Path)"
    Test-BackendDeps $py.Path 'import uvicorn' 'mobile'

    $node = Assert-Node
    Write-Info "Node   : $node"

    $tokenFile = Join-Path $Root '.qm-token'
    $token = Get-AccessToken $tokenFile
    Write-Info "Token  : $($token.Source)"
    Write-Info "         $((Format-TokenMask $token.Token))  (enter once on the phone: Settings -> server address)"

    # 前端 dist 不存在则现场构建（原 start-mobile.bat 语义）
    $distIndex = Join-Path $Frontend 'dist\index.html'
    if (-not (Test-Path -LiteralPath $distIndex)) {
        Assert-FrontendDeps
        if ($script:IsWhatIf) {
            Write-Plan ("would build frontend: npm run build   (cwd={0})" -f $Frontend)
        } else {
            Write-Step 'build'
            Write-Info 'frontend\dist not found - building (may take a minute) ...'
            Push-Location $Frontend
            try {
                & npm.cmd run build
                $buildRc = $LASTEXITCODE
            } finally {
                Pop-Location
            }
            if ($buildRc -ne 0) { Fail 'frontend build failed. See output above.' }
            Write-Ok 'frontend built'
        }
    } else {
        Write-Info 'frontend dist: present'
    }

    if (Test-PortListening $BackendPort) { Write-Note "port $BackendPort in use (backend may already be running)" }
    if (Test-PortListening $ServerPort) { Write-Note "port $ServerPort in use (edge server may already be running)" }

    $effectiveDataDir = $null
    if (-not [string]::IsNullOrEmpty($DataDir)) {
        $effectiveDataDir = Get-EffectiveDataDir (Join-Path $Root 'var\data')
        if ($script:IsWhatIf) { Write-Plan "would set env VENUSTECH_DATA_DIR=$effectiveDataDir for the backend window" }
        $env:VENUSTECH_DATA_DIR = $effectiveDataDir
    }

    Write-Step '1/2'
    $backendArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort")
    [void](Start-ServiceProcess $py.Path $backendArgs $Backend 'backend FastAPI (loopback)')
    if ($null -ne $effectiveDataDir) { Remove-Item Env:\VENUSTECH_DATA_DIR -ErrorAction SilentlyContinue }

    [void](Wait-ForServices 5 $BackendPort 'backend FastAPI')

    Write-Step '2/2'
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Green
    Write-Host '  NOW OPEN ON YOUR PHONE:' -ForegroundColor Green
    Write-Host "  http://YOUR-PC-IP:$ServerPort" -ForegroundColor Green
    Write-Host '  (Tailscale IP, or the LAN IP on the same WiFi)' -ForegroundColor Green
    if (-not $script:IsWhatIf) {
        Write-Host "  ACCESS TOKEN: $($token.Token)" -ForegroundColor Green
    }
    Write-Host '========================================' -ForegroundColor Green
    Write-Host ''

    $serverJs = Join-Path $Root 'ops\server\server.js'
    if ($null -ne $token.Token) { $env:QM_TOKEN = $token.Token }
    Write-Info 'Keep this window open. Press Ctrl+C to stop the unified server.'
    Push-Location $Root
    try {
        if ($script:IsWhatIf) {
            Write-Plan ("would start edge server: `"$node`" $serverJs   (cwd=$Root, PORT=$ServerPort, QM_TOKEN=<token>)")
        } else {
            & node $serverJs
            $serverRc = $LASTEXITCODE
        }
    } finally {
        Pop-Location
        Remove-Item Env:\QM_TOKEN -ErrorAction SilentlyContinue
    }

    if (-not $script:IsWhatIf) {
        Stop-Launched
        if ($serverRc -ne 0) {
            Write-Note "edge server exited with code $serverRc"
        }
        Write-Info 'mobile mode stopped.'
    }
    if (Test-ConsoleInteractive) {
        Write-Host ''
        Write-Host 'Press Enter to exit...' -ForegroundColor Yellow
        Read-Host | Out-Null
    }
}

# ==================================================================
# 入口
# ==================================================================
Write-Host ''
Write-Host "Qimingxing launcher (single implementation) - mode=$Mode" -ForegroundColor Cyan
if ($script:IsWhatIf) { Write-Host '  -WhatIf: no process will be started (plan only).' -ForegroundColor Magenta }
Write-Info "repo    : $Root"

switch ($Mode) {
    'dev' { Start-DevMode }
    'demo' { Start-DemoMode }
    'mobile' { Start-MobileMode }
}

if ($script:IsWhatIf) {
    Write-Host ''
    Write-Plan 'plan complete - nothing was started.'
    exit 0
}
exit 0
