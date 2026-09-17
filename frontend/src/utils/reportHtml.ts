// ============================================================
// 人生报告 → 单文件 HTML（S6-5）
//
// 产出原则（数据主权）：内联全部样式、零外部依赖、零脚本请求 ——
// 报告归用户自己所有，可存档、可带走、可用任何浏览器打开。
// 颜色为报告专属固化色板（导出物脱离应用主题，属合理例外）。
// ============================================================
import type { ReportData } from '@/types'

const DOT: Record<string, string> = {
  primary: '#FF8FA3', mint: '#7BD3B2', butter: '#FFD97A', sky: '#8FC1F0',
  lilac: '#C9AEE8', strawberry: '#FF6B7D', gold: '#F5C842',
}
const dotColor = (token: string | null | undefined) => DOT[token ?? ''] ?? DOT.primary

function esc(s: string | null | undefined): string {
  return (s ?? '').replace(/[<>&"]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' })[c]!)
}

function size(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}

function identityCard(r: ReportData['identity_axis']['identities'][number]): string {
  const stats = [
    `待办 ${r.tasks_open}`, `完成 ${r.tasks_completed}`, `文档 ${r.documents}`,
    `日记 ${r.diaries}`, `复盘 ${r.reviews}`, `记忆 ${r.memories}`,
  ].map((s) => `<span class="pill">${s}</span>`).join('')
  return `
  <div class="card">
    <div class="card-head">
      <span class="dot" style="background:${dotColor(r.color_token)}"></span>
      <b>${esc(r.name)}</b>
      ${r.is_archived ? '<span class="archived">已归档</span>' : ''}
    </div>
    <div class="pills">${stats}</div>
  </div>`
}

export function buildReportHtml(d: ReportData): string {
  const generated = d.generated_at.slice(0, 19).replace('T', ' ')
  const identities = d.identity_axis.identities.map(identityCard).join('')
  const un = d.identity_axis.unassigned
  const skills = d.growth_axis.skills.length
    ? d.growth_axis.skills.map((s) => `
      <div class="skill">
        <span>${esc(s.name)}</span>
        <div class="track"><span class="fill" style="width:${Math.min(100, (s.count / Math.max(...d.growth_axis.skills.map((x) => x.count))) * 100)}%"></span></div>
        <em>${s.count}</em>
      </div>`).join('')
    : '<p class="muted">还没有点亮技能 —— 去写复盘、沉淀记忆、完成任务</p>'
  const roots = d.archive_axis.roots.length
    ? d.archive_axis.roots.map((r) => `
      <div class="root"><span class="mono">${esc(r.path)}</span>
      <em>${r.file_count} 项 · ${size(r.total_size)}</em></div>`).join('')
    : ''
  const exp = d.recent_experience.length
    ? d.recent_experience.map((e) => `
      <li><span class="tag">${esc(e.source_label)}</span>
      <b>${esc(e.title)}</b>
      <span class="muted">${e.identity_name ? `· ${esc(e.identity_name)}` : ''} · ${e.occurred_at.slice(0, 10)}</span></li>`).join('')
    : '<p class="muted">近期还没有经历记录</p>'

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(d.nickname)} 的人生报告 · ${generated.slice(0, 10)}</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; background:#FFFBF5; color:#5C4A45; padding:40px 20px; max-width:860px; margin:0 auto; }
  h1 { font-size:26px; margin-bottom:4px; }
  h2 { font-size:17px; margin:36px 0 14px; padding-bottom:8px; border-bottom:2px solid #F2E4D8; }
  .muted { color:#9B7E72; font-weight:400; }
  .hero { margin-bottom:8px; }
  .hero p { color:#9B7E72; font-size:13px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px; }
  .card, .panel { background:#fff; border:1px solid #F2E4D8; border-radius:14px; padding:16px; }
  .card-head { display:flex; align-items:center; gap:8px; }
  .dot { width:10px; height:10px; border-radius:99px; display:inline-block; }
  .archived { font-size:11px; background:#FBF1E7; border-radius:99px; padding:2px 8px; color:#9B7E72; }
  .pills { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
  .pill { font-size:12px; background:#FBF1E7; border-radius:99px; padding:3px 10px; color:#9B7E72; }
  .unassigned { margin-top:12px; font-size:13px; color:#9B7E72; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .big { font-size:30px; font-weight:700; }
  .skill { display:flex; align-items:center; gap:10px; padding:6px 0; font-size:13px; }
  .skill span { width:90px; }
  .skill em { font-style:normal; color:#9B7E72; }
  .track { flex:1; height:8px; background:#FBF1E7; border-radius:99px; overflow:hidden; }
  .fill { display:block; height:100%; background:#FF8FA3; border-radius:99px; }
  .root { display:flex; justify-content:space-between; padding:6px 0; font-size:13px; gap:10px; }
  .mono { font-family:Consolas, monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  ul.exp { list-style:none; padding:0; }
  ul.exp li { padding:8px 0; border-bottom:1px solid #F2E4D8; font-size:13px; display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; }
  ul.exp li:last-child { border-bottom:none; }
  .tag { background:#C9AEE833; border-radius:99px; padding:2px 8px; font-size:11px; color:#9A7BB8; }
  footer { margin-top:40px; font-size:12px; color:#C0A89B; text-align:center; }
</style>
</head>
<body>
  <div class="hero">
    <h1>${esc(d.nickname)} 的人生报告</h1>
    <p>生成于 ${generated} · 启明星 Personal OS · 身份 × 成长 × 档案</p>
  </div>

  <h2>🧭 身份轴 —— 我在推进哪几条线</h2>
  ${identities || '<p class="muted">还没有建立身份</p>'}
  <p class="unassigned">另有未归类：待办 ${un.tasks_open} · 文档 ${un.documents} · 日记 ${un.diaries} · 复盘 ${un.reviews} · 记忆 ${un.memories}</p>

  <h2>🌱 成长轴 —— 我积累了多少</h2>
  <div class="grid2">
    <div class="panel">
      <div class="big">LV${d.growth_axis.level}</div>
      <p class="muted">${d.growth_axis.exp} EXP · 升级进度 ${d.growth_axis.percent}%</p>
      <p class="muted" style="margin-top:8px">完成 ${d.growth_axis.tasks_completed_total} 个任务 · 日记 ${d.growth_axis.diaries_total} 篇 · 复盘 ${d.growth_axis.reviews_total} 次</p>
    </div>
    <div class="panel">${skills}</div>
  </div>

  <h2>📁 档案轴 —— 我沉淀了什么</h2>
  <div class="cards">
    <div class="card"><div class="card-head"><b>文档</b></div><div class="big" style="margin-top:6px">${d.archive_axis.documents_total}</div></div>
    <div class="card"><div class="card-head"><b>资产</b></div><p class="muted" style="margin-top:6px">SOP ${d.archive_axis.sops_total} · 提示词 ${d.archive_axis.prompts_total} · 技能 ${d.archive_axis.skills_total} · 项目记忆 ${d.archive_axis.project_memories_total} · 分身记忆 ${d.archive_axis.avatar_memories_total}</p></div>
  </div>
  ${d.archive_axis.workspace_enabled && roots ? `<div class="panel" style="margin-top:12px"><b style="font-size:13px">工作区索引</b>${roots}</div>` : ''}

  <h2>📜 近期经历</h2>
  <div class="panel"><ul class="exp">${exp}</ul></div>

  <footer>本报告由启明星本地生成，数据来自你自己的记录 —— 归你所有，可存档带走。</footer>
</body>
</html>`
}

/** 触发浏览器下载单文件 HTML */
export function downloadReport(d: ReportData): void {
  const html = buildReportHtml(d)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `人生报告-${d.generated_at.slice(0, 10)}.html`
  a.click()
  URL.revokeObjectURL(url)
}
