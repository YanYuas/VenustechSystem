# ============================================================
# Git 历史备份（D-12）
#
# 背景：本机 `.git` 是一个指向工作区外部的 Junction
#   （例如 C:\Users\<user>\qimingxing-git-repo）。
#   —— 直接复制项目目录**不会**备份提交历史；换机 = 历史全丢。
#   —— `git bundle` 是官方支持的"单文件全历史备份"，可离线 clone 恢复。
#
# 用法：
#   pwsh -ExecutionPolicy Bypass -File ops\backup-git.ps1
#   pwsh ... -File ops\backup-git.ps1 -Destination D:\Backups -Keep 10
#   pwsh ... -File ops\backup-git.ps1 -WhatIf        # 只打印计划，不写文件
#
# 退出码：0 成功；1 失败（git 不可用 / bundle 校验失败）
# ============================================================
param(
    [string]$Destination = "",
    [int]$Keep = 5,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
if (-not $Destination) { $Destination = Join-Path $repo "var\backups" }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundle = Join-Path $Destination "venustech-$stamp.bundle"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启明星 - Git 历史备份（git bundle）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- 0. 环境与 .git 位置检查 ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 找不到 git" -ForegroundColor Red
    exit 1
}
$gitDir = (& git -C $repo rev-parse --absolute-git-dir 2>$null)
if (-not $gitDir) {
    Write-Host "[ERROR] $repo 不是 git 仓库" -ForegroundColor Red
    exit 1
}
Write-Host "[信息] 仓库: $repo"
Write-Host "[信息] git 数据目录: $gitDir"

$dotGit = Get-Item (Join-Path $repo ".git") -Force -ErrorAction SilentlyContinue
if ($dotGit -and $dotGit.LinkType) {
    Write-Host "[警告] .git 是 $($dotGit.LinkType) → $($dotGit.Target)" -ForegroundColor Yellow
    Write-Host "       因此备份项目目录不会包含历史；本脚本生成的 bundle 才是完整备份。" -ForegroundColor Yellow
}

# --- 1. 预检 ---
$heads = (& git -C $repo rev-list --count --all 2>$null)
if (-not $heads) {
    Write-Host "[ERROR] 无法读取提交历史" -ForegroundColor Red
    exit 1
}
Write-Host "[信息] 提交总数: $heads"
Write-Host "[信息] 目标 bundle: $bundle"

if ($WhatIf) {
    Write-Host ""
    Write-Host "[WhatIf] 将执行:" -ForegroundColor Yellow
    Write-Host "  1) 创建目录: $Destination"
    Write-Host "  2) git bundle create `"$bundle`" --all"
    Write-Host "  3) git bundle verify `"$bundle`""
    Write-Host "  4) 仅保留最近 $Keep 个 bundle"
    exit 0
}

try {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null

    # --- 2. 创建 bundle（--all = 所有分支 + tag） ---
    & git -C $repo bundle create $bundle --all
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] git bundle create 失败（退出码 $LASTEXITCODE）" -ForegroundColor Red
        exit 1
    }
    $size = (Get-Item -LiteralPath $bundle).Length
    Write-Host ("[完成] bundle 已生成: {0:N0} 字节" -f $size) -ForegroundColor Green

    # --- 3. 校验（必须真的能读，否则备份是幻觉） ---
    & git -C $repo bundle verify $bundle 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] bundle 校验失败，备份不可用" -ForegroundColor Red
        exit 1
    }
    Write-Host "[完成] bundle 校验通过（可离线 clone 恢复）" -ForegroundColor Green
    Write-Host "        恢复：git clone `"$bundle`" <目标目录>"

    # --- 4. 轮转：只保留最近 N 个 ---
    $old = Get-ChildItem -LiteralPath $Destination -Filter "venustech-*.bundle" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $Keep
    if ($old) {
        $old | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Write-Host "[清理] 删除旧备份: $($_.Name)"
        }
    }
    Write-Host ""
    Write-Host "[提醒] 请把最新 bundle 复制到仓库外（移动硬盘/网盘），" -ForegroundColor Yellow
    Write-Host "       var/ 已被 gitignore，bundle 本身不会进仓库。" -ForegroundColor Yellow
    exit 0
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
