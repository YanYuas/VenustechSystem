# ADR-0006 文档信息架构：五分区 + 索引 + 链接守护

- 状态：**已采纳并落地**（2026-10-26）
- 相关：[docs/README.md](../../README.md)、`scripts/audit_docs_links.py`

## 背景

`docs/` 有 65 个文件、3.7MB，但**没有索引**（`docs/README.md` 长期"待建"）。实测问题：

- 架构、产品需求、开发指南、带日期的过程报告混在 `design/` 与 `management/`；
- 21 个带日期的过程文档与长期文档同层，读者无法判断"哪份还有效"；
- 5 组同主题多版本并存：技术架构 v1/v2、PRD v1/v2、模块 PRD 两代、mod-platform 三份报告；
- 正文承诺的 10 个路径不存在（例如曾承诺过的 onboarding 指南）；
- 同一批数字在 README / PROJECT_STRUCTURE / DEVELOPMENT 三处互相矛盾（路由 22/34/实际 33）。

## 决策

文档按**用途与生命周期**分五区，而不是按"写得早晚"：

```
docs/
├── README.md            文档总索引（唯一入口，按"我要做什么"组织）
├── architecture/        现行架构：ARCHITECTURE.md（仓库根）、domains.json、ADR/、legacy/
├── product/             产品与需求：requirements / prd/{v1-archived,v2-current} / ui
├── guides/              可执行的开发指南（开发/后端/前端/分支/协作）
├── process/archive/     带日期的过程记录（只读历史，不再更新）
├── design/              UI 画廊与参考图（素材，非规范）
└── assets/              截图
```

规则：

1. **现行 vs 归档必须显式**：archived 文档在索引里标注"仅供追溯，不代表现状"。
2. **一主题一现行版本**：旧版本移入 archive，不删除。
3. **链接由机器守**：`scripts/audit_docs_links.py` 全量校验 md 相对链接与正文内联路径，
   纳入 `check_all.py` 与 CI。
4. **数字不写死**：文档中的计数（路由数/服务数/测试数）要么删掉，要么说明"由
   `scripts/audit_architecture.py` 输出为准"，避免再次出现三处矛盾。

## 后果

- ✅ 新人从 `README.md → docs/README.md → ARCHITECTURE.md` 三步建立全貌。
- ✅ 历史过程记录保留可追溯性，但不再污染现行文档。
- ⚠️ 移动文件会让旧的外部链接失效（个人项目可接受）；仓库内链接由守护保证。

## 替代方案

- 引入静态站点（VitePress/Docusaurus）：在 65 个文件的规模上是过度工程，先解决 IA 与索引。否决。
- 删除过期文档：丢失决策历史，且部分报告是审计证据。否决，改为归档。
