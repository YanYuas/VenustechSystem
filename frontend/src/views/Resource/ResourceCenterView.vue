<script setup lang="ts">
// ============================================================
// 资源中心（二期开发中）
// ============================================================
import BaseCard from '@/components/common/BaseCard.vue'
</script>

<template>
  <div class="dev-page">
    <BaseCard class="dev-hero">
      <div class="dev-hero-icon">🗂️</div>
      <h1 class="dev-hero-title">资源中心</h1>
      <p class="dev-hero-sub">该模块正在二期开发中，敬请期待</p>
      <span class="dev-badge">二期规划</span>
    </BaseCard>

    <div class="dev-features">
        <div class="dev-feature"><span class="dev-feature-icon">📥</span><div><p class="dev-feature-name">收集箱</p><p class="dev-feature-desc">全局快捷键快速捕获文字/链接/图片/文件，批量处理分类</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">📚</span><div><p class="dev-feature-name">领域库</p><p class="dev-feature-desc">自定义领域分类，资源聚合，领域知识图谱</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">📋</span><div><p class="dev-feature-name">模板库</p><p class="dev-feature-desc">文档/表格/配置/项目模板，变量替换一键调用</p></div></div>
        <div class="dev-feature"><span class="dev-feature-icon">🗂️</span><div><p class="dev-feature-name">项目库</p><p class="dev-feature-desc">项目资料自动归集，版本管理，完成后归档</p></div></div>
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
