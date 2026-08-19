<template>
  <main class="ntf">
    <header class="ntf-header">
      <h1 class="ntf-title">通知中心</h1>
      <div class="ntf-actions">
        <t-button variant="text" theme="primary" size="small" :disabled="!store.items.length" @click="onReadAll">
          全部已读
        </t-button>
        <t-button variant="text" theme="default" size="small" @click="onOpenSettings">设置</t-button>
      </div>
    </header>

    <!-- 列表 -->
    <section v-if="store.items.length" class="ntf-list">
      <div
        v-for="n in store.items"
        :key="n.id"
        class="ntf-item"
        :class="{ unread: !n.is_read }"
        @click="goto(n)"
      >
        <t-avatar :image="n.actor_avatar || undefined" size="40px" class="ntf-avatar">
          <template #icon>{{ n.actor_nickname.slice(0, 1) || '系' }}</template>
        </t-avatar>
        <div class="ntf-body">
          <div class="ntf-row1">
            <span class="ntf-actor">{{ n.actor_nickname }}</span>
            <span class="ntf-type">{{ typeLabel(n.type) }}</span>
            <span class="ntf-time">{{ fmtTime(n.created_at) }}</span>
          </div>
          <p class="ntf-title-text">{{ n.title }}</p>
          <p v-if="n.summary" class="ntf-summary">{{ n.summary }}</p>
          <p v-if="n.community_name" class="ntf-community">来自频道《{{ n.community_name }}》</p>
        </div>
        <span v-if="!n.is_read" class="ntf-dot" />
      </div>
      <div v-if="store.items.length < store.total" class="ntf-more">
        <t-button variant="text" theme="primary" :loading="store.loading" @click="loadMore">
          {{ store.loading ? '加载中…' : '加载更多' }}
        </t-button>
      </div>
    </section>

    <section v-else-if="store.loaded" class="ntf-empty">
      <t-empty description="暂无通知" />
    </section>
    <section v-else class="ntf-empty">
      <t-skeleton v-for="i in 3" :key="i" :rows="2" />
    </section>

    <!-- 通知设置 -->
    <t-dialog
      v-model:visible="settingsVisible"
      header="通知设置"
      :footer="false"
      width="320px"
    >
      <div class="ntf-settings">
        <div v-for="s in settingRows" :key="s.key" class="ntf-setting-row">
          <span>{{ s.label }}</span>
          <t-switch
            :value="!!(store.settings && store.settings[s.key])"
            @change="(v: boolean) => onToggleSetting(s.key, v)"
          />
        </div>
      </div>
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { useNotificationStore } from '@/stores/notification'
import type { NotificationItem, NotifySettings } from '@/api/notification'

const router = useRouter()
const store = useNotificationStore()
const settingsVisible = ref(false)

const typeLabels: Record<string, string> = {
  mention: '@提及',
  like: '点赞',
  comment: '评论',
  follow: '关注',
  system: '系统',
  review_result: '审核',
  report_feedback: '举报',
}

const settingRows: Array<{ key: keyof NotifySettings; label: string }> = [
  { key: 'mention', label: '@提及我' },
  { key: 'like', label: '收到的赞' },
  { key: 'comment', label: '评论与回复' },
  { key: 'follow', label: '新关注' },
  { key: 'system', label: '系统通知' },
  { key: 'review', label: '审核结果' },
  { key: 'report', label: '举报反馈' },
]

function typeLabel(t: string) {
  return typeLabels[t] || t
}

function fmtTime(t: string | null) {
  if (!t) return ''
  const s = t.replace('T', ' ').slice(0, 16)
  const d = new Date(t.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return s
  const now = Date.now()
  const diff = now - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return s
}

function goto(n: NotificationItem) {
  if (!n.is_read) store.markRead(n.id).catch(() => {})
  // ref_id 跳转约定：评论/赞/@ → 帖子；关注/审核 → 频道；系统通知按 ref_id 是否等于频道 id 区分
  let path = ''
  if (n.type === 'comment' || n.type === 'like' || n.type === 'mention') {
    if (n.ref_id) path = `/p/${n.ref_id}`
  } else if (n.type === 'system') {
    if (n.ref_id && n.ref_id === n.community_id) path = `/c/${n.ref_id}`
    else if (n.ref_id) path = `/p/${n.ref_id}`
  } else {
    if (n.ref_id) path = `/c/${n.ref_id}`
  }
  if (path) router.push(path)
}

function loadMore() {
  store.page += 1
  store.fetchList()
}

async function onReadAll() {
  try {
    await store.markAllRead()
    MessagePlugin.success('已全部标记为已读')
  } catch (e) {
    MessagePlugin.error((e as Error).message || '操作失败')
  }
}

async function onOpenSettings() {
  settingsVisible.value = true
  if (!store.settings) {
    store.loadSettings().catch(() => {})
  }
}

async function onToggleSetting(key: keyof NotifySettings, v: boolean) {
  try {
    await store.saveSettings({ [key]: v } as Partial<NotifySettings>)
    MessagePlugin.success('设置已保存')
  } catch (e) {
    MessagePlugin.error((e as Error).message || '保存失败')
  }
}

onMounted(() => {
  store.fetchList(true)
})
</script>

<style scoped>
.ntf {
  max-width: var(--page-max);
  margin: 0 auto;
  padding-bottom: var(--tabbar-height);
}
.ntf-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}
.ntf-title {
  flex: 1;
  margin: 0;
  font-size: var(--fs-title);
  text-align: center;
}
.ntf-actions {
  display: flex;
  gap: 4px;
  white-space: nowrap;
}
.ntf-list {
  background: var(--bg-card);
}
.ntf-item {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  position: relative;
}
.ntf-item:active {
  background: var(--bg-secondary);
}
.ntf-avatar {
  flex-shrink: 0;
  background: var(--brand-weak);
  color: var(--brand);
}
.ntf-body {
  flex: 1;
  min-width: 0;
}
.ntf-row1 {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.ntf-actor {
  font-size: var(--fs-body);
  font-weight: 600;
}
.ntf-type {
  font-size: var(--fs-caption);
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 0 6px;
  line-height: 1.6;
}
.ntf-time {
  margin-left: auto;
  font-size: var(--fs-caption);
  color: var(--text-3);
  white-space: nowrap;
}
.ntf-title-text {
  margin: 2px 0 0;
  font-size: var(--fs-body);
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ntf-summary {
  margin: 2px 0 0;
  font-size: var(--fs-caption);
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ntf-community {
  margin: 2px 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.ntf-dot {
  position: absolute;
  top: 16px;
  right: 10px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
}
.ntf-item.unread .ntf-title-text {
  font-weight: 600;
}
.ntf-more {
  padding: 12px;
  text-align: center;
}
.ntf-empty {
  padding: 48px 16px;
}
.ntf-settings .ntf-setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: var(--fs-body);
}
.ntf-settings .ntf-setting-row:last-child {
  border-bottom: none;
}
</style>
