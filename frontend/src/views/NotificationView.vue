<template>
  <main class="ntf">
    <header class="ntf-header">
      <router-link to="/" class="ntf-home" title="返回主页" aria-label="返回主页">
        <HomeIcon class="ntf-home-icon" />
      </router-link>
      <h1 class="ntf-title">系统通知</h1>
      <div class="ntf-actions">
        <t-button variant="text" theme="primary" size="small" :disabled="!store.items.length" @click="onReadAll">
          全部已读
        </t-button>
        <router-link to="/me/notification-settings" class="ntf-settings-link">设置</router-link>
      </div>
    </header>

    <!-- 列表：仅系统通知（账号封禁/解封、频道封禁/解封、平台更新公告）；互动通知在频道内查看 -->
    <section v-if="store.items.length" class="ntf-list">
      <div
        v-for="n in store.items"
        :key="n.id"
        class="ntf-item"
        :class="{ unread: !n.is_read }"
        @click="goto(n)"
      >
        <!-- 未读红点挂在头像右上角（#47）：原定位在条目右侧，与「删除」按钮区域重叠易误触 -->
        <span class="ntf-avatar-wrap">
          <t-avatar :image="n.actor_avatar || undefined" size="40px" class="ntf-avatar">
            <template #icon>{{ n.actor_nickname.slice(0, 1) || '系' }}</template>
          </t-avatar>
          <span v-if="!n.is_read" class="ntf-dot" />
        </span>
        <div class="ntf-body">
          <div class="ntf-row1">
            <t-tag v-if="isSystem(n)" theme="primary" variant="light" size="small" class="ntf-type">系统</t-tag>
            <span class="ntf-actor">{{ n.actor_nickname }}</span>
            <span class="ntf-time">{{ timeAgo(n.created_at) }}</span>
          </div>
          <p class="ntf-title-text">{{ n.title }}</p>
          <p v-if="n.summary" class="ntf-summary">{{ n.summary }}</p>
          <p v-if="n.community_name" class="ntf-community">来自频道《{{ n.community_name }}》</p>
        </div>
        <t-button
          variant="text"
          size="small"
          theme="danger"
          class="ntf-del"
          @click.stop="onRemove(n)"
        >删除</t-button>
      </div>
      <div v-if="store.items.length < store.total" class="ntf-more">
        <t-button variant="text" theme="primary" :loading="store.loading" @click="loadMore">
          {{ store.loading ? '加载中…' : '加载更多' }}
        </t-button>
      </div>
    </section>

    <section v-else-if="store.error" class="ntf-empty">
      <ErrorState :text="store.error" @retry="onRetry" />
    </section>
    <section v-else-if="store.loaded" class="ntf-empty">
      <t-empty description="暂无通知" />
    </section>
    <section v-else class="ntf-empty">
      <t-skeleton v-for="i in 3" :key="i" :rows="2" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { HomeIcon } from 'tdesign-icons-vue-next'
import { MessagePlugin } from 'tdesign-vue-next'
import { useNotificationStore } from '@/stores/notification'
import ErrorState from '@/components/ErrorState.vue'
import { timeAgo } from '@/utils/time'
import type { NotificationItem } from '@/api/notification'

const router = useRouter()
const store = useNotificationStore()

const typeLabels: Record<string, string> = {
  mention: '@提及',
  like: '点赞',
  comment: '评论',
  follow: '关注',
  system: '系统',
  review_result: '审核',
  report_feedback: '举报',
}

function typeLabel(t: string) {
  return typeLabels[t] || t
}

/** 系统通知判定：/notifications 仅展示 system 类型，用标签强化识别。 */
function isSystem(n: NotificationItem) {
  return n.type === 'system'
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
  else MessagePlugin.info('该通知没有可跳转的内容')
}

function loadMore() {
  store.page += 1
  store.fetchList().catch((e: unknown) => {
    MessagePlugin.error((e as Error)?.message || '加载失败，请重试')
  })
}

/** 首屏加载失败后的重试入口（避免页面停在骨架屏/错误态无任何出路）。 */
function onRetry() {
  store.fetchList(true).catch(() => {})
}

async function onReadAll() {
  try {
    await store.markAllRead()
    MessagePlugin.success('已全部标记为已读')
  } catch (e) {
    MessagePlugin.error((e as Error).message || '操作失败')
  }
}

async function onRemove(n: NotificationItem) {
  try {
    await store.removeItem(n.id)
    MessagePlugin.success('已删除')
  } catch (e) {
    MessagePlugin.error((e as Error).message || '删除失败')
  }
}

onMounted(() => {
  store.fetchList(true, { scope: 'system' }).catch(() => {})
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
.ntf-home {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-control);
  color: var(--text-2);
  flex-shrink: 0;
}
.ntf-home:hover {
  background: var(--surface);
  color: var(--brand);
}
.ntf-home-icon {
  width: 18px;
  height: 18px;
}
.ntf-title {
  flex: 1;
  margin: 0;
  font-size: var(--fs-title);
  text-align: left;
}
.ntf-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
/* 「设置」链接与左侧「全部已读」t-button(small) 同高同行，避免文字错行不在一条线 */
.ntf-actions :deep(.t-button) {
  height: 24px;
}
.ntf-actions .ntf-settings-link {
  height: 24px;
  font-size: 12px;
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
.ntf-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}
.ntf-avatar {
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
  flex-shrink: 0;
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
/* 未读红点：头像右上角，不再与右侧删除按钮争位（#47） */
.ntf-dot {
  position: absolute;
  top: 0;
  right: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--danger);
  box-shadow: 0 0 0 2px var(--bg-card);
}
.ntf-del {
  align-self: flex-start;
  flex-shrink: 0;
  margin-left: -4px;
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
.ntf-settings-link {
  font-size: var(--fs-caption);
  color: var(--brand);
  text-decoration: none;
  white-space: nowrap;
  padding: 6px 4px;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
}
.ntf-settings-link:active {
  opacity: 0.7;
}
</style>
