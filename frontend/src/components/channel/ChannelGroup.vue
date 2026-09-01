<template>
  <div class="ch-group">
    <t-skeleton v-if="loading" :row="4" />
    <EmptyState v-else-if="items.length === 0" :text="emptyText" :action-text="actionText" :to="actionTo" />
    <div v-else class="list">
      <!-- router-link：键盘可 Tab/Enter 打开，屏幕阅读器可导航（#38） -->
      <router-link
        v-for="c in items"
        :key="c.id"
        :to="`/c/${c.id}`"
        class="card"
      >
        <img v-if="c.avatar_url" :src="c.avatar_url" class="card-avatar" alt="" />
        <span v-else class="card-avatar card-avatar-fallback">{{ (c.name || '频').slice(0, 1) }}</span>
        <div class="card-main">
          <div class="card-head">
            <h4 class="card-name">{{ c.name }}</h4>
            <t-tag v-if="c.is_member" theme="primary" variant="light" size="small">已加入</t-tag>
            <t-tag v-else-if="c.join_setting === 1" variant="outline" size="small">审核制</t-tag>
            <t-tag v-else-if="c.join_setting === 2" variant="outline" size="small">邀请制</t-tag>
          </div>
          <p class="card-profile">{{ c.profile || '暂无简介' }}</p>
          <div class="card-meta">
            <span>{{ c.member_count }} 成员</span>
            <span>{{ c.post_count }} 帖</span>
            <span>#{{ c.number }}</span>
          </div>
        </div>
        <ChevronRightIcon class="card-arrow" />
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChevronRightIcon } from 'tdesign-icons-vue-next'
import type { Community } from '@/api/community'
import EmptyState from '@/components/EmptyState.vue'

withDefaults(
  defineProps<{
    loading: boolean
    items: Community[]
    emptyText?: string
    actionText?: string
    actionTo?: string
  }>(),
  { emptyText: '暂无频道', actionText: '', actionTo: '' },
)
</script>

<style scoped>
.ch-group {
  padding: var(--sp-3) 0;
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.card {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, box-shadow 0.2s;
}
.card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}
.card:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}
.card-avatar {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid var(--border);
  flex-shrink: 0;
}
.card-avatar-fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  background: var(--brand);
}
.card-main {
  flex: 1;
  min-width: 0;
}
.card-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.card-name {
  margin: 0;
  font-size: var(--fs-body);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-profile {
  margin: 4px 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-meta {
  margin-top: 4px;
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.card-arrow {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  color: var(--text-3);
}
</style>