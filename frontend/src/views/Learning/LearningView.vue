<script setup lang="ts">
// ============================================================
// 学习成长（二期开发中）
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
</script>

<template>
  <div class="dev-page">
    <BaseCard class="dev-hero">
      <div class="dev-hero-icon">📚</div>
      <h1 class="dev-hero-title">学习成长</h1>
      <p class="dev-hero-sub">该模块正在二期开发中，敬请期待</p>
      <span class="dev-badge">二期规划</span>
    </BaseCard>

    <div class="dev-features">
        <div class="dev-feature"><span class="dev-feature-icon">🎯</span><div><p class="dev-feature-name">学习计划</p><p class="dev-feature-desc">目标拆解为学习任务，进度追踪，计划模板</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">🃏</span><div><p class="dev-feature-name">知识卡片</p><p class="dev-feature-desc">问答/概念/填空卡，Markdown/图片/代码支持</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">🔄</span><div><p class="dev-feature-name">间隔重复</p><p class="dev-feature-desc">SM-2算法，每日复习队列，记忆曲线可视化</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">⏱️</span><div><p class="dev-feature-name">学习时长</p><p class="dev-feature-desc">番茄钟/手动记录，学习热力图，趋势统计</p></div></div>
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
