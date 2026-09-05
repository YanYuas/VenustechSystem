# ============================================================
# 启明星系统 - 前后端一键启动（开发模式 · PowerShell 增强版）
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# 功能：依赖/端口检查、并行启动后端(reload)+前端、自动开浏览器、一键停止
# ============================================================
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启明星系统 - 前后端一键启动（开发）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 依赖检查 ---
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 python，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 node，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "[提示] 前端依赖未安装，请先执行：cd frontend && npm install" -ForegroundColor Yellow
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
$backend = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8765","--reload" -WorkingDirectory "$root\backend" -PassThru
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
