<template>
  <div class="sparkline">
    <svg
      class="sparkline-svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      :style="{ height: height + 'px' }"
      role="img"
      :aria-label="`${title || '趋势'}`"
    >
      <!-- 横向网格线（25% 步进） -->
      <line
        v-for="g in grid"
        :key="g.y"
        :x1="0"
        :x2="W"
        :y1="g.y"
        :y2="g.y"
        class="sparkline-grid"
        stroke="#eee"
        stroke-width="1"
      />
      <!-- 面积填充（柔和渐变） -->
      <polygon
        v-if="hasData"
        :points="areaPoints"
        fill="url(#sparkline-grad)"
        opacity="0.25"
      />
      <!-- 折线 -->
      <polyline
        v-if="hasData"
        :points="linePoints"
        fill="none"
        :stroke="color"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <!-- 数据点（native tooltip 显示值） -->
      <g v-if="hasData">
        <circle
          v-for="(p, i) in dots"
          :key="i"
          :cx="p.x"
          :cy="p.y"
          r="2.5"
          :fill="color"
        >
          <title>{{ p.label }}</title>
        </circle>
      </g>
      <!-- 渐变定义 -->
      <defs>
        <linearGradient id="sparkline-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" />
          <stop offset="100%" :stop-color="color" stop-opacity="0" />
        </linearGradient>
      </defs>
    </svg>
    <div v-if="!hasData" class="sparkline-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ data: number[]; height?: number; color?: string; title?: string }>(),
  { height: 120, color: '#0052d9', title: '' },
)

// 固定逻辑画布，横向拉伸自适应容器宽度
const W = 300
const H = 100
const PAD = 6

const hasData = computed(() => (props.data?.length ?? 0) >= 1)
const values = computed(() => (props.data ?? []).map((v) => Number(v) || 0))

const max = computed(() => Math.max(...values.value, 1))
const step = computed(() => (values.value.length > 1 ? W / (values.value.length - 1) : W))

function xy(i: number) {
  const x = values.value.length > 1 ? i * step.value : W / 2
  const y = H - PAD - (values.value[i] / max.value) * (H - PAD * 2)
  return { x, y }
}

const dots = computed(() =>
  values.value.map((v, i) => ({ ...xy(i), label: `${v}` })),
)

const linePoints = computed(() => dots.value.map((p) => `${p.x},${p.y}`).join(' '))
const areaPoints = computed(() => {
  if (!dots.value.length) return ''
  const first = dots.value[0]
  const last = dots.value[dots.value.length - 1]
  return `${first.x},${H} ${linePoints.value} ${last.x},${H}`
})

// 25% 步进的网格线
const grid = computed(() => [0.25, 0.5, 0.75].map((r) => ({ y: r * H })))
</script>

<style scoped>
.sparkline {
  position: relative;
  width: 100%;
}
.sparkline-svg {
  width: 100%;
  display: block;
}
.sparkline-empty {
  padding: var(--sp-4) 0;
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
