<!--
  DocumentGraph —— 文档关系图谱（M03 P2）
  纯 SVG 力导向图：节点=文档，边=双向链接
-->
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { documentApi, type GraphData, type GraphNode } from '@/api/document'
import { useToast } from '@/composables/useToast'

const emit = defineEmits<{
  (e: 'open-doc', id: string): void
}>()

const toast = useToast()
const loading = ref(true)
const graphData = ref<GraphData | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const width = ref(800)
const height = ref(500)
const hoveredNode = ref<GraphNode | null>(null)
const hoverPos = ref({ x: 0, y: 0 })

interface SimNode extends GraphNode {
  x: number; y: number; vx: number; vy: number; radius: number
}
const simNodes = ref<SimNode[]>([])
const simEdges = ref<Array<{ source: string; target: string }>>([])
let rafId = 0
let dragging: string | null = null

const nodeMap = computed(() => {
  const m = new Map<string, SimNode>()
  simNodes.value.forEach(n => m.set(n.id, n))
  return m
})

function initSimulation(data: GraphData) {
  const cx = width.value / 2, cy = height.value / 2
  simNodes.value = data.nodes.map((n, i) => {
    const angle = (i / Math.max(data.nodes.length, 1)) * Math.PI * 2
    const r = 120 + Math.random() * 80
    return { ...n, x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r, vx: 0, vy: 0, radius: 8 + Math.min(n.word_count / 500, 12) }
  })
  simEdges.value = data.edges
}

function tick() {
  const nodes = simNodes.value
  const cx = width.value / 2, cy = height.value / 2
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j]
      let dx = b.x - a.x, dy = b.y - a.y
      let dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = 2000 / (dist * dist)
      a.vx -= (dx / dist) * force; a.vy -= (dy / dist) * force
      b.vx += (dx / dist) * force; b.vy += (dy / dist) * force
    }
  }
  for (const e of simEdges.value) {
    const a = nodeMap.value.get(e.source), b = nodeMap.value.get(e.target)
    if (!a || !b) continue
    const dx = b.x - a.x, dy = b.y - a.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const force = (dist - 120) * 0.02
    a.vx += (dx / dist) * force; a.vy += (dy / dist) * force
    b.vx -= (dx / dist) * force; b.vy -= (dy / dist) * force
  }
  for (const n of nodes) {
    n.vx += (cx - n.x) * 0.005; n.vy += (cy - n.y) * 0.005
  }
  for (const n of nodes) {
    if (n.id === dragging) continue
    n.vx *= 0.85; n.vy *= 0.85
    n.x += n.vx; n.y += n.vy
    n.x = Math.max(30, Math.min(width.value - 30, n.x))
    n.y = Math.max(30, Math.min(height.value - 30, n.y))
  }
  rafId = requestAnimationFrame(tick)
}

function onNodeMouseDown(e: MouseEvent, node: SimNode) {
  dragging = node.id; e.preventDefault()
}
function onMouseMove(e: MouseEvent) {
  if (!dragging || !svgRef.value) return
  const rect = svgRef.value.getBoundingClientRect()
  const node = nodeMap.value.get(dragging)
  if (node) { node.x = e.clientX - rect.left; node.y = e.clientY - rect.top; node.vx = 0; node.vy = 0 }
}
function onMouseUp() { dragging = null }
function onNodeClick(id: string) { emit('open-doc', id) }
function onNodeHover(e: MouseEvent, node: SimNode) {
  hoveredNode.value = node
  if (svgRef.value) {
    const rect = svgRef.value.getBoundingClientRect()
    hoverPos.value = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }
}

async function loadGraph() {
  loading.value = true
  try {
    const data = await documentApi.graph()
    graphData.value = data
    if (data.nodes.length) { initSimulation(data); rafId = requestAnimationFrame(tick) }
  } catch { toast.error('图谱加载失败') } finally { loading.value = false }
}

function resize() {
  if (svgRef.value?.parentElement) {
    width.value = svgRef.value.parentElement.clientWidth
    height.value = Math.max(400, svgRef.value.parentElement.clientHeight)
  }
}

onMounted(() => {
  resize()
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  window.addEventListener('resize', resize)
  loadGraph()
})
onUnmounted(() => {
  cancelAnimationFrame(rafId)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  window.removeEventListener('resize', resize)
})
</script>

<template>
  <div class="doc-graph">
    <div v-if="loading" class="doc-graph__loading"><div class="doc-graph__spinner" /><span>正在构建知识图谱…</span></div>
    <div v-else-if="!graphData?.nodes.length" class="doc-graph__empty">
      <p>暂无文档链接关系</p>
      <p class="doc-graph__hint">在文档中使用 [[文档标题]] 创建双向链接后，这里会显示关系图谱</p>
    </div>
    <svg v-else ref="svgRef" class="doc-graph__svg" :viewBox="`0 0 ${width} ${height}`">
      <g class="doc-graph__edges">
        <line v-for="(e, i) in simEdges" :key="i" :x1="nodeMap.get(e.source)?.x || 0" :y1="nodeMap.get(e.source)?.y || 0" :x2="nodeMap.get(e.target)?.x || 0" :y2="nodeMap.get(e.target)?.y || 0" class="doc-graph__edge" />
      </g>
      <g class="doc-graph__nodes">
        <g v-for="n in simNodes" :key="n.id" class="doc-graph__node" :transform="`translate(${n.x}, ${n.y})`" @mousedown="onNodeMouseDown($event, n)" @mouseenter="onNodeHover($event, n)" @mouseleave="hoveredNode = null" @click="onNodeClick(n.id)">
          <circle :r="n.radius" class="doc-graph__node-circle" />
          <text class="doc-graph__node-label" y="4" text-anchor="middle">{{ n.title }}</text>
        </g>
      </g>
    </svg>
    <Transition name="fade">
      <div v-if="hoveredNode" class="doc-graph__tooltip" :style="{ left: hoverPos.x + 12 + 'px', top: hoverPos.y + 12 + 'px' }">
        <div class="doc-graph__tooltip-title">{{ hoveredNode.title }}</div>
        <div class="doc-graph__tooltip-meta"><span>{{ hoveredNode.folder_name }}</span><span>{{ hoveredNode.word_count }} 字</span></div>
      </div>
    </Transition>
    <div v-if="graphData" class="doc-graph__stats">
      <span>{{ graphData.nodes.length }} 篇文档</span>
      <span>{{ graphData.edges.length }} 条链接</span>
    </div>
  </div>
</template>

<style scoped>
.doc-graph {
  position: relative; width: 100%; height: 100%; min-height: 400px;
  background: var(--bg-inset, #f8f9fa); border-radius: var(--radius-md, 12px); overflow: hidden;
  &__loading { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 12px; color: var(--text-mid, #888); font-size: var(--text-sm, 13px); }
  &__spinner { width: 32px; height: 32px; border: 3px solid var(--line, #e5e7eb); border-top-color: var(--primary, #7c5cff); border-radius: 50%; animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  &__empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; color: var(--text-mid, #888); p { margin: 0; } }
  &__hint { font-size: var(--text-xs, 11px); color: var(--text-low, #aaa); }
  &__svg { width: 100%; height: 100%; cursor: grab; &:active { cursor: grabbing; } }
  &__edge { stroke: var(--primary, #7c5cff); stroke-opacity: 0.2; stroke-width: 1.5; }
  &__node { cursor: pointer; &:hover .doc-graph__node-circle { fill: var(--primary, #7c5cff); } }
  &__node-circle { fill: var(--primary-soft, rgba(124,92,255,0.2)); stroke: var(--primary, #7c5cff); stroke-width: 2; transition: fill 0.15s; }
  &__node-label { font-size: 10px; fill: var(--text-hi, #333); pointer-events: none; font-weight: 500; }
  &__tooltip { position: absolute; z-index: 10; background: var(--bg-panel, #fff); border: 1px solid var(--line, #e5e7eb); border-radius: var(--radius-sm, 8px); padding: 8px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); pointer-events: none; min-width: 120px; }
  &__tooltip-title { font-size: var(--text-sm, 13px); font-weight: 600; color: var(--text-hi, #333); margin-bottom: 4px; }
  &__tooltip-meta { display: flex; gap: 12px; font-size: var(--text-xs, 11px); color: var(--text-low, #999); }
  &__stats { position: absolute; bottom: 12px; right: 12px; display: flex; gap: 16px; font-size: var(--text-xs, 11px); color: var(--text-low, #999); background: var(--bg-panel, #fff); padding: 6px 12px; border-radius: 20px; border: 1px solid var(--line, #e5e7eb); }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
