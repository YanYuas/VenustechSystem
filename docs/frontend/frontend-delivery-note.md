# frontend/ 工程说明（正式前端骨架 v1.0）

> ✅ 本工程为**正式交付**，非早期标注的「可回退误解产物」。

## 状态沿革

- **2026-08-28 早**：初版提交 `feat(frontend): 第一批 UI 组件（可回退标注）` — 当时被误标为可回退产物。
- **2026-08-28 后续**：七轮优化扩展为完整前端骨架 v1.0（API 层/类型/composables/三套主题/基建），
  成为既定交付。权威说明见 `docs/frontend/前端开发说明.md` 与 `docs/management/项目计划.md` 进度表。

## 骨架组成（v1.0）

- **分层**：Views → Components → Composables → API 单向数据流
- **API 层**：7 模块 + `http.ts`（超时/重试/SSE/错误归一化），后端唯一入口
- **类型**：8 文件，字段与后端 snake_case 一致
- **Composables**：useAsync / useTask / useDocument / useConversation / useReview / useDashboard / useAutoSave / useOnline + toast/modal/theme/shortcuts
- **主题**：三套×明暗（奶油糖果默认 / 国风雅集 / 深渊档案），CSS 变量 + data-theme
- **基建**：constants / directives / errorHandler / 路由恢复 / 全局快捷键

## 运行

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173（/api 代理到 127.0.0.1:8765）
```

## Git 历史回退

早期「可回退」标注仅指初版提交历史；当前骨架如需整体重置仍可：

```bash
git rm -r frontend/
```

但请先确认不需要保留骨架成果（详见 `docs/frontend/前端开发说明.md`）。

## 相关文件

- 权威说明：`docs/frontend/前端开发说明.md`
- 设计基准：`docs/design/03-UI组件index.md` · 技术架构 `docs/design/02-技术架构-v2.0.md`
- 进度：`docs/management/项目计划.md`（当前进度表）
