# 安全事件 Runbook：真实数据库被提交进 Git 历史

> 事件等级：**P0（个人数据泄露）**
> 发现时间：2026-10-26（架构审计）
> 状态：**已评估，处置待执行**（处置涉及远端仓库与历史重写，必须由仓库所有者决策）

---

## 1. 事实（已核实，非推测）

| 项目 | 事实 |
|---|---|
| 泄漏内容 | `backend/data/app.db`（606,208 B）+ `app.db-shm` + `app.db-wal` + `backend/data_test/*.db` |
| 引入提交 | `6b5c2dd4605a4024d9819eb5a3bdb67db503a709`（2026-09-05，「add main v0.1.71」） |
| 可达 ref | **仅** `origin/feature/phase2-development` |
| 是否已合并 main | **否**（与 main 分叉：main 独有 40 提交 / 该分支独有 64 提交） |
| 是否含 `.encryption_key` | **否**（已用 `git ls-tree` 确认分支里没有密钥文件） |
| 是否含 `.env` / 令牌 | 否 |

**影响判定**

- 数据库里的**明文业务数据**（任务、文档、对话、日记、复盘、身份等）已进入 Git 历史 →
  凡能访问该仓库（及任何 fork / GitHub 缓存 / 曾 clone 的机器）的人都能提取。
- 加密字段（`users.api_key_encrypted`、`vault_items`)是密文，且 **AES 主密钥
  `.encryption_key` 未随分支泄漏** → 在没有钥匙的前提下不可解。这是不幸中的万幸。
- 结论：**按"个人数据已泄露"处置**（不是按"可能泄露"）。密钥侧风险较低，但仍建议轮换
  任何曾以明文形式出现在该库里的外部凭据（例如你在别处记录过的 API Key）。

---

## 2. 处置步骤（按顺序执行）

> ⚠️ 本仓库的 `.git` 是 Junction 指向 `C:\Users\21722\qimingxing-git-repo`。
> 涉及历史重写的命令（`git filter-repo`）会**替换 `.git` 目录**，在 Junction 上执行可能
> 破坏链接。务必先读第 2.0 步，不要直接跑 filter-repo。

### 2.0 冷备（先做，不可跳过）

```powershell
# 备份到仓库外（含全部 refs 与对象）
git bundle create "D:\Backups\venustech-pre-purge-$(Get-Date -Format yyyyMMdd).bundle" --all
# 验证 bundle 可用
git bundle verify "D:\Backups\venustech-pre-purge-YYYYMMDD.bundle"
```

### 2.1 删除远端分支（消除"可发现性"，非彻底清除）

```powershell
git push origin --delete feature/phase2-development
# 本地也删掉指向它的远端跟踪引用
git branch -dr origin/feature/phase2-development
```

> 注意：**删分支 ≠ 删数据**。GitHub 仍可能通过提交 SHA 直接访问对象，直到其 GC；
> 若仓库存在 fork 或被他人 clone，副本永远收不回。所以这只能降低发现概率，不能"修复"。

### 2.2 彻底清除（二选一，需你决策）

**方案 A（推荐，最可靠）：删除并重建远端仓库**
1. 在本地用干净的 main 历史重建（先 bundle 备份）；
2. GitHub 上删除仓库 → 重新创建（同名）→ `git push origin main --tags`；
3. 代价：Issue/PR/Star 等元数据丢失；收益：历史里不再有该对象。
4. 若仓库是 **private 且从未公开/fork**，风险显著降低，可只做 2.1 + 2.3。

**方案 B：历史重写 + 强制推送**
```powershell
# 需要 git-filter-repo（pip install git-filter-repo）
# 先复制整个项目到新目录（避开 Junction），在新目录里操作：
git clone --no-local "D:\YanYuas\PersonalDevelopmentPortfolio\VenustechSystem" D:\Temp\venustech-rewrite
cd D:\Temp\venustech-rewrite
git filter-repo --invert-paths --path backend/data/ --path backend/data_test/
git push --force --all
git push --force --tags
# 然后在本机重新指向重写后的远端（或重新 clone 覆盖本地）
```
> 该方案会改写所有提交 SHA；其他机器/分支必须重新 clone。对个人项目通常不值得，
> 方案 A 更干净。若只做 2.1，也可以接受（记录为"残余风险"）。

### 2.3 凭据与密钥复核

1. 确认 `.encryption_key` **从未**进入任何提交：
   ```powershell
   git log --all --full-history -- "*.encryption_key" "backend/data/.encryption_key"
   ```
   输出为空 = 安全。
2. 若数据库里存在其它**明文**凭据（个别设置项），立即轮换对应服务商 Key。
3. 应用内可用「设置 → 安全 → 轮换密钥」重加密（注意：先读 CHANGELOG 中"假轮换"修复记录，
   确认当前版本真的会重写三张表）。

### 2.4 验证

```powershell
# 分支已删除（应报错）
git ls-tree -r --name-only origin/feature/phase2-development
# 历史守护：当前索引必须为 0 违规
python scripts/audit_repo_secrets.py
# 若做了历史重写，历史泄漏应为 0
python scripts/audit_repo_secrets.py --strict
```

---

## 3. 预防（已落地）

- `.gitignore`：`var/`、`data*/`、`*.db`、`*.db-wal`、`*.db-shm`、`.qm-token`、`.encryption_key`。
- `scripts/audit_repo_secrets.py`：检查当前索引 + 扫描全部 refs 的历史新增文件；
  已接入 CI（`repo-guard.yml`）。
- 提交前自检：`git status` 里出现任何 `*.db` / `.env` / `.qm-token` 就不要提交。
- 分支策略：功能分支合并后删除（另有 8 个已合并的 `mod-*` 分支可一并清理）。

---

## 4. 顺带清理（安全，可先做）

以下远端分支已合并进 main（领先 0 提交），删除不影响代码：

```powershell
git push origin --delete feature-mobile-deepseek-assistant
git push origin --delete mod-asset mod-companion mod-dashboard mod-execution `
  mod-knowledge mod-life mod-platform mod-tools
```

> 执行前用 `git branch -r --merged main` 复核；`feature/phase2-development` **未合并**，
> 删它前先确认其独有提交里没有你还需要的功能。
