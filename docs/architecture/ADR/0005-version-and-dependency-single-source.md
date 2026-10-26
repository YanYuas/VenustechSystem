# ADR-0005 版本与依赖的单一事实来源

- 状态：**已采纳并落地**（2026-10-26）
- 相关：[ARCHITECTURE.md](../../../ARCHITECTURE.md) §6、§7；`VERSION`、`scripts/check_versions.py`

## 背景

审计实测同一应用存在**四个互不相同的版本号**：

| 位置 | 原值 |
|---|---|
| `backend/app/config.py` | 0.7.0 |
| `frontend/package.json` | 0.7.0 |
| `backend/pyproject.toml` | **0.1.0** |
| `frontend/android/app/build.gradle` | **1.0** |

依赖侧同样分裂：

- `requirements.txt` 是实际安装来源（已锁定精确版本）；
- `pyproject.toml` **没有** `[project.dependencies]`，与 requirements 完全脱节；
- `uv.lock` 只有 7 行（空壳），但 `docs/guides/development.md` 教人 `uv sync --all-extras`（装不出任何依赖）；
- `pytest` 被注释在 requirements 里，但开发机已装 → 换机器就"测试跑不了"。

## 决策

1. **版本唯一事实来源 = 仓库根 `VERSION`**（语义化版本）。
   `scripts/check_versions.py` 校验并支持 `--sync` 同步 5 处：后端 config、pyproject、
   前端 package.json、`ops/server/package.json`、Android `versionName`。
   Android `versionCode` 是整数发布序号，独立人工递增，不参与语义版本校验。
2. **依赖唯一事实来源 = 后端 `requirements.txt`**（运行时）+ `requirements-dev.txt`（测试/工具）。
   `pyproject.toml` 仅保留工具配置，并在文件头明确写"不是依赖清单"，避免再次分裂。
3. 版本校验纳入 `check_all.py` 与 CI（repo-guard）。
4. 若要迁移到 uv/pyproject 管理依赖，必须**一步到位**：删除 requirements、改 setup.bat、
   改 CI、改开发指南四处同改（写在 pyproject 注释里）。

## 后果

- ✅ "应用显示 v0.7 / APK 是 v1.0" 这类漂移由机器守住。
- ✅ 新机器 `setup.bat` 装得全，`requirements-dev.txt` 让 pytest 不再是"可选幽灵依赖"。
- ⚠️ 发布 APK 时仍需人工递增 `versionCode`（Android 强制要求整数单调递增）。

## 替代方案

- 以 `frontend/package.json` 为版本源：后端/Android 仍需同步，没有本质改善。
- 每个包独立版本（monorepo 语义化发布）：本项目是单一交付物，版本必须一致，否决。
