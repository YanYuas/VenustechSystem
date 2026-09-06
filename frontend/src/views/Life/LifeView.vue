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
