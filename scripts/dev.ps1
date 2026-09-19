# ============================================================
# 启明星系统 - 前后端一键启动（开发模式 · PowerShell 增强版）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -DataDir .\data-fusion
# 功能：依赖/端口检查、并行启动后端(reload)+前端、自动开浏览器、一键停止
#
# -DataDir：把后端数据目录指到独立位置（相对 backend/）。
#   分支开发时用它隔离数据库，避免分支上新增的 Alembic 迁移污染主库、
#   导致切回 main 后报 "Can't locate revision"。详见 docs/management/分支开发指南.md
# ============================================================
param(
    [string]$DataDir = ""
)

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启明星系统 - 前后端一键启动（开发）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 数据目录隔离（可选） ---
if ($DataDir -ne "") {
    $env:VENUSTECH_DATA_DIR = $DataDir
    Write-Host "[配置] 数据目录 → $DataDir（相对 backend/，与主库隔离）" -ForegroundColor Cyan
    Write-Host ""
}

# --- Python 解析：必须用项目 venv ---
# 后端依赖装在 backend\.venv。PATH 上的 python 通常是另一个解释器，
# 缺 fastapi/uvicorn，后端会立刻 ModuleNotFoundError 退出 —— 必须优先用 venv。
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $pythonExe = $venvPy
} else {
    Write-Host "[警告] 未找到项目 venv：backend\.venv" -ForegroundColor Yellow
    Write-Host "        将回退到 PATH 上的 python —— 它可能缺少后端依赖。" -ForegroundColor Yellow
    Write-Host "        建议先运行一次 setup.bat 创建 venv 并安装依赖。" -ForegroundColor Yellow
    $pythonExe = "python"
}
$pyCheck = & $pythonExe -c "import uvicorn, fastapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 所选 Python 缺少后端依赖（fastapi/uvicorn）：$pythonExe" -ForegroundColor Red
    Write-Host "       请运行 setup.bat 安装依赖后重试。" -ForegroundColor Red
    exit 1
}
Write-Host "[环境] Python: $pythonExe" -ForegroundColor Cyan

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 node，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "[错误] 前端依赖未安装，请先运行 setup.bat（或 cd frontend && npm install）" -ForegroundColor Red
    exit 1
}

# --- 端口检查 ---
if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "[提示] 端口 8765 已被占用（可能已有后端在运行）" -ForegroundColor Yellow
}
if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "[提示] 端口 5173 已被占用（可能已有前端在运行）" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[1/3] 启动后端 FastAPI (127.0.0.1:8765, --reload) ..." -ForegroundColor Yellow
$backend = Start-Process -FilePath $pythonExe -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8765","--reload" -WorkingDirectory "$root\backend" -PassThru
Write-Host "[2/3] 启动前端 Vite (http://localhost:5173) ..." -ForegroundColor Yellow
$frontend = Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory "$root\frontend" -PassThru
Write-Host "[3/3] 等待服务就绪，打开浏览器 ..." -ForegroundColor Yellow
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "✅ 已启动：后端 PID=$($backend.Id) / 前端 PID=$($frontend.Id)" -ForegroundColor Green
Write-Host "   后端 127.0.0.1:8765（首次自动灌演示数据） | 前端 http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "按 Enter 停止全部服务..." -ForegroundColor Yellow
Read-Host | Out-Null
Stop-Process -Id $backend.Id, $frontend.Id -Force -ErrorAction SilentlyContinue
Write-Host "已停止" -ForegroundColor Green
