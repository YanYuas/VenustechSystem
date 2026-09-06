<script setup lang="ts">
// ============================================================
// 生活记录（二期开发中）
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
</script>

<template>
  <div class="dev-page">
    <BaseCard class="dev-hero">
      <div class="dev-hero-icon">💚</div>
      <h1 class="dev-hero-title">生活记录</h1>
      <p class="dev-hero-sub">该模块正在二期开发中，敬请期待</p>
      <span class="dev-badge">二期规划</span>
    </BaseCard>

    <div class="dev-features">
        <div class="dev-feature"><span class="dev-feature-icon">✅</span><div><p class="dev-feature-name">习惯打卡</p><p class="dev-feature-desc">自定义习惯，连续天数统计，打卡提醒</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">😊</span><div><p class="dev-feature-name">心情追踪</p><p class="dev-feature-desc">每日心情评分，标签记录，趋势分析</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">📖</span><div><p class="dev-feature-name">四维日记</p><p class="dev-feature-desc">家庭/健康/精力/成长四维，每日一句话</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">⚡</span><div><p class="dev-feature-name">精力管理</p><p class="dev-feature-desc">分时段精力记录，高效时段分析，作息建议</p></div></div>
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
