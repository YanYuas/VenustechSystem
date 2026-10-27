#Requires -Version 5.1
<#
.SYNOPSIS
  启明星系统 · 开发一键启动（兼容转发壳）

.DESCRIPTION
  D-11 启动器单一实现后，真正的启动逻辑只在 ops\start.ps1。
  本文件保留旧入口名（scripts\dev.ps1），只为兼容既有文档与肌肉记忆：
  它等价于 ops\start.ps1 -Mode dev，并继续支持 -DataDir。

.PARAMETER DataDir
  后端数据目录（相对 backend\）。分支开发用它隔离数据库，避免分支上
  新增的 Alembic 迁移污染主库、切回 main 时报 "Can't locate revision"。
  详见 docs/guides/branch-development.md。

.PARAMETER WhatIf
  只打印启动计划，不启动进程（原样转发给 ops\start.ps1）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -DataDir .\data-fusion
.EXAMPLE
  scripts\dev.ps1 -WhatIf
#>
param(
    [string]$DataDir = '',

    [switch]$WhatIf
)

$root = Split-Path -Parent $PSScriptRoot
$startScript = Join-Path $root 'ops\start.ps1'

if (-not (Test-Path -LiteralPath $startScript)) {
    Write-Host "[ERROR] missing single implementation: $startScript" -ForegroundColor Red
    exit 1
}

$forward = @{ Mode = 'dev' }
if (-not [string]::IsNullOrEmpty($DataDir)) { $forward['DataDir'] = $DataDir }
if ($WhatIf) { $forward['WhatIf'] = $true }

& $startScript @forward
$rc = $LASTEXITCODE
exit $rc
