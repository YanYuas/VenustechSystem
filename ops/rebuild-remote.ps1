# ============================================================
# 远端仓库重建（P0-2 彻底处置）
#
# 为什么需要"重建"而不是只 force-push：
#   git 历史里提交过 backend/data/app.db（提交 6b5c2dd）。
#   filter-repo/force-push 只能让 refs 不再指向它，但 GitHub 仍会
#   按旧 commit/blob SHA 提供对象（实测 HTTP 200），等于泄漏仍在。
#   唯一彻底的 API 级做法是**删除仓库 → 重建 → 推送干净历史**。
#
# 前置条件（必须由使用者本人完成，脚本无法代办）：
#   gh auth refresh -s delete_repo
#   （浏览器授权一次；之后 gh 才拥有删仓库权限）
#
# 用法：
#   pwsh -ExecutionPolicy Bypass -File ops\rebuild-remote.ps1 -Confirm
#   pwsh ... -File ops\rebuild-remote.ps1 -Repo YanYuas/VenustechSystem -Confirm
#
# 风险（脚本会先打印并再次确认）：
#   - 仓库的 star/fork/watch/issue/PR/Actions secrets 全部丢失；
#   - 需要重新配置仓库描述/主页/分支保护；
#   - 删除后若网络中断，可用 var/backups 里的 bundle 恢复工作区与历史。
# ============================================================
param(
    [string]$Repo = "YanYuas/VenustechSystem",
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$env:GIT_TERMINAL_PROMPT = "0"

function Fail([string]$msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }
function Step([string]$msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }

# ---------- 0. 前置检查 ----------
Step "0/7 前置检查"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail "找不到 gh CLI" }
& gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "gh 未登录，请先 gh auth login" }

$dirty = & git status --porcelain
if ($dirty) { Fail "工作树不干净（$($dirty.Count) 个变更），先提交再重建" }

$scopes = (& gh api -i /user 2>&1 | Select-String -Pattern "x-oauth-scopes" | Select-Object -First 1)
if (-not $scopes -or $scopes -notmatch "delete_repo") {
    Write-Host ""
    Write-Host "缺少 delete_repo 权限（当前 scopes: $($scopes -replace '.*: ', '')）" -ForegroundColor Yellow
    Write-Host "请先在你自己的终端执行一次（会打开浏览器授权）：" -ForegroundColor Yellow
    Write-Host "    gh auth refresh -s delete_repo" -ForegroundColor White
    Write-Host "然后重新运行本脚本。" -ForegroundColor Yellow
    exit 2
}

$head = & git rev-parse HEAD
$tree = & git rev-parse "HEAD^{tree}"
$desc = (& gh repo view $Repo --json description --jq .description 2>$null)
$vis = (& gh repo view $Repo --json visibility --jq .visibility 2>$null)

Step "1/7 全量备份（bundle + 关键信息）"
& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "ops\backup-git.ps1") -Keep 10 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "git bundle 备份失败，停止" }
Write-Host "  备份完成：var/backups/（gitignored）"
Write-Host "  HEAD=$head"
Write-Host "  TREE=$tree"
Write-Host "  repo=$Repo visibility=$vis"
Write-Host "  description=$desc"

Step "2/7 待执行的破坏性操作"
Write-Host "  gh repo delete $Repo --yes"
Write-Host "  gh repo create $Repo --$($vis.ToLower()) --description '<原描述>'"
Write-Host "  git push -u origin main && git push origin --tags"
Write-Host "  ⚠ star/fork/issue/PR/Actions secrets 将丢失" -ForegroundColor Yellow
if (-not $Confirm) {
    Write-Host "`n未指定 -Confirm，仅做预演，未执行任何删除。" -ForegroundColor Yellow
    exit 0
}

Step "3/7 删除远端仓库"
& gh repo delete $Repo --yes
if ($LASTEXITCODE -ne 0) { Fail "删除失败（权限不足或网络问题），仓库未受影响；可改用网页删除" }
Write-Host "  已删除 $Repo"

Step "4/7 重建空仓库"
$createArgs = @("repo", "create", $Repo, "--public")
if ($vis -eq "PRIVATE") { $createArgs = @("repo", "create", $Repo, "--private") }
if ($desc) { $createArgs += @("--description", $desc) }
& gh @createArgs
if ($LASTEXITCODE -ne 0) { Fail "重建失败！本地历史未丢，恢复：git bundle 在 var/backups/" }
Start-Sleep -Seconds 3

Step "5/7 推送干净历史（main + tags）"
& git push -u origin main
if ($LASTEXITCODE -ne 0) { Fail "推送 main 失败；本地历史完好，可重试 git push -u origin main" }
& git push origin --tags 2>$null
Write-Host "  推送完成"

Step "6/7 验证远端"
$refs = & git ls-remote --heads --tags origin
$refs | ForEach-Object { Write-Host "  $_" }
$branches = (& gh api "repos/$Repo/branches" --jq "length")
Write-Host "  分支数: $branches（应为 1）"
$leaked = @("6b5c2dd4605a4024d9819eb5a3bdb67db503a709", "dd0fcb09034fcac584725b78d15a3c3019abb125")
foreach ($sha in $leaked) {
    $code = & curl.exe -s -o NUL -w "%{http_code}" "https://api.github.com/repos/$Repo/commits/$sha"
    if ($code -eq "404") { Write-Host "  ✅ 旧 commit $($sha.Substring(0,8)) 已不可访问 (404)" -ForegroundColor Green }
    else { Write-Host "  ⚠ 旧 commit $($sha.Substring(0,8)) 仍返回 HTTP $code（可能需等 GitHub GC）" -ForegroundColor Yellow }
}
Write-Host "`n完成。请重新配置：仓库描述/主页/分支保护/Actions secrets。" -ForegroundColor Green
