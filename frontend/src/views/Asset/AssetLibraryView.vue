<script setup lang="ts">
// ============================================================
// 长期资产库（二期开发中）
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
</script>

<template>
  <div class="dev-page">
    <BaseCard class="dev-hero">
      <div class="dev-hero-icon">💎</div>
      <h1 class="dev-hero-title">长期资产库</h1>
      <p class="dev-hero-sub">该模块正在二期开发中，敬请期待</p>
      <span class="dev-badge">二期规划</span>
    </BaseCard>

    <div class="dev-features">
        <div class="dev-feature"><span class="dev-feature-icon">📝</span><div><p class="dev-feature-name">SOP流程库</p><p class="dev-feature-desc">步骤+检查清单，一键执行生成任务，版本管理</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">💬</span><div><p class="dev-feature-name">Prompt模板库</p><p class="dev-feature-desc">角色+任务+约束+变量，与第二分身联动</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">🏆</span><div><p class="dev-feature-name">Skill技能库</p><p class="dev-feature-desc">方法论文档化，熟练度评级，关联资源</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">🧠</span><div><p class="dev-feature-name">项目记忆</p><p class="dev-feature-desc">项目完成自动生成，经验教训沉淀，可复用资产提取</p></div></div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dev-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.dev-hero {
  text-align: center;
  padding: var(--space-8) var(--space-4);
}
.dev-hero-icon {
  font-size: 48px;
  margin-bottom: var(--space-3);
}
.dev-hero-title {
  font-size: var(--text-2xl);
  font-weight: 800;
  color: var(--text-hi);
  font-family: var(--font-cute);
}
.dev-hero-sub {
  margin-top: var(--space-2);
  color: var(--text-mid);
  font-size: var(--text-sm);
}
.dev-badge {
  display: inline-block;
  margin-top: var(--space-3);
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  background: var(--primary-soft);
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
}
.dev-features {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}
.dev-feature {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
}
.dev-feature-icon {
  font-size: 24px;
  flex-shrink: 0;
}
.dev-feature-name {
  font-weight: 600;
  color: var(--text-hi);
  font-size: var(--text-sm);
}
.dev-feature-desc {
  margin-top: 2px;
  color: var(--text-mid);
  font-size: var(--text-xs);
  line-height: 1.5;
}
</style>
