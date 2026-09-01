<template>
  <main class="console">
    <header class="console-header">
      <h1 class="console-title">平台控制台</h1>
      <span class="console-sub">平台级视角：巡视全部频道与用户，执行封禁/解封等系统级操作</span>
    </header>

    <!-- 全局统计概览（reuse /admin/stats） -->
    <section v-if="statsLoading" class="state"><t-skeleton :row="2" animation="gradient" /></section>
    <section v-else-if="stats" class="stats-cards">
      <div class="stat-card"><span class="stat-num">{{ stats.users_total }}</span><span class="stat-label">用户</span></div>
      <div class="stat-card"><span class="stat-num">{{ stats.communities_total }}</span><span class="stat-label">频道</span></div>
      <div class="stat-card"><span class="stat-num">{{ stats.posts_total }}</span><span class="stat-label">帖子</span></div>
      <div class="stat-card"><span class="stat-num">{{ stats.comments_total }}</span><span class="stat-label">评论</span></div>
      <div class="stat-card hot"><span class="stat-num">{{ stats.posts_today }}</span><span class="stat-label">今日发帖</span></div>
    </section>

    <t-tabs v-model="tab" class="console-tabs">
      <!-- 频道管理 -->
      <t-tab-panel value="channels" label="频道管理">
        <div class="toolbar">
          <t-input v-model.trim="chKeyword" placeholder="搜索频道名" clearable class="tb-search" @enter="onChSearch" @clear="onChSearch" />
          <t-select v-model="chStatus" class="tb-filter" @change="onChSearch">
            <t-option :value="undefined" label="全部状态" />
            <t-option :value="0" label="正常" />
            <t-option :value="1" label="已关闭" />
            <t-option :value="2" label="已封禁" />
          </t-select>
          <t-button theme="primary" variant="outline" @click="onChSearch">查询</t-button>
        </div>

        <div v-if="chLoading && channels.length === 0" class="state"><t-skeleton :row="4" animation="gradient" /></div>
        <ErrorState v-else-if="chError" :text="chError" @retry="loadChannels(1)" />

        <template v-else>
          <div v-if="channels.length" class="tbl">
            <div class="tbl-head tbl-row">
              <span class="col-name">频道</span>
              <span class="col-num">成员</span>
              <span class="col-num">帖子</span>
              <span class="col-owner">归属者</span>
              <span class="col-status">状态</span>
              <span class="col-op">操作</span>
            </div>
            <div v-for="c in channels" :key="c.id" class="tbl-row">
              <span class="col-name">
                <UserAvatar :name="c.name" :src="c.avatar_url" :size="28" />
                <span class="ch-name">{{ c.name }}</span>
                <span class="ch-num">#{{ c.number }}</span>
              </span>
              <span class="col-num">{{ c.member_count }}</span>
              <span class="col-num">{{ c.post_count }}</span>
              <span class="col-owner">{{ c.owner_name || `#${c.owner_id}` }}</span>
              <span class="col-status">
                <t-tag v-if="c.status === 0" variant="light" theme="success">正常</t-tag>
                <t-tag v-else-if="c.status === 1" variant="light" theme="warning">已关闭</t-tag>
                <t-tag v-else variant="light" theme="danger">已封禁</t-tag>
              </span>
              <span class="col-op">
                <t-button v-if="c.status !== 2" variant="outline" size="small" theme="danger" :loading="c._busy" @click="onBanChannel(c, true)">封禁</t-button>
                <t-button v-else variant="outline" size="small" :loading="c._busy" @click="onBanChannel(c, false)">解封</t-button>
              </span>
            </div>
          </div>
          <t-empty v-else description="没有匹配的频道" />
          <t-button v-if="channels.length < chTotal" variant="outline" block class="load-more" :loading="chLoading" @click="loadChannels(chPage + 1, true)">
            {{ chLoading ? '加载中…' : `加载更多（${channels.length}/${chTotal}）` }}
          </t-button>
        </template>
      </t-tab-panel>

      <!-- 用户管理 -->
      <t-tab-panel value="users" label="用户管理">
        <div class="toolbar">
          <t-input v-model.trim="uKeyword" placeholder="搜索用户名/昵称/邮箱" clearable class="tb-search" @enter="onUSearch" @clear="onUSearch" />
          <t-select v-model="uStatus" class="tb-filter" @change="onUSearch">
            <t-option :value="undefined" label="全部状态" />
            <t-option :value="0" label="正常" />
            <t-option :value="1" label="已封禁" />
            <t-option :value="2" label="已注销" />
          </t-select>
          <t-button theme="primary" variant="outline" @click="onUSearch">查询</t-button>
        </div>

        <div v-if="uLoading && users.length === 0" class="state"><t-skeleton :row="4" animation="gradient" /></div>
        <ErrorState v-else-if="uError" :text="uError" @retry="loadUsers(1)" />

        <template v-else>
          <div v-if="users.length" class="tbl">
            <div class="tbl-head tbl-row tbl-row-users">
              <span class="col-name">用户</span>
              <span class="col-num">频道</span>
              <span class="col-type">身份</span>
              <span class="col-status">状态</span>
              <span class="col-op">操作</span>
            </div>
            <div v-for="u in users" :key="u.id" class="tbl-row tbl-row-users">
              <span class="col-name">
                <UserAvatar :name="u.nickname || u.username" :src="u.avatar_url" :size="28" />
                <span class="u-nick">{{ u.nickname || u.username }}</span>
                <span class="u-username">@{{ u.username }}</span>
              </span>
              <span class="col-num">{{ u.joined_communities }}</span>
              <span class="col-type">
                <t-tag v-if="u.user_type === 1" variant="light" theme="primary">平台管理员</t-tag>
                <t-tag v-else-if="u.user_type === 2" variant="light">AI 账号</t-tag>
                <span v-else class="type-plain">普通</span>
              </span>
              <span class="col-status">
                <t-tag v-if="u.status === 0" variant="light" theme="success">正常</t-tag>
                <t-tag v-else-if="u.status === 1" variant="light" theme="danger">已封禁</t-tag>
                <t-tag v-else variant="light" theme="warning">已注销</t-tag>
              </span>
              <span class="col-op">
                <template v-if="u.user_type !== 1">
                  <t-button v-if="u.status === 0" variant="outline" size="small" theme="danger" :loading="u._busy" @click="onBanUser(u, true)">封禁</t-button>
                  <t-button v-else-if="u.status === 1" variant="outline" size="small" :loading="u._busy" @click="onBanUser(u, false)">解封</t-button>
                </template>
                <span v-else class="op-disabled">—</span>
              </span>
            </div>
          </div>
          <t-empty v-else description="没有匹配的用户" />
          <t-button v-if="users.length < uTotal" variant="outline" block class="load-more" :loading="uLoading" @click="loadUsers(uPage + 1, true)">
            {{ uLoading ? '加载中…' : `加载更多（${users.length}/${uTotal}）` }}
          </t-button>
        </template>
      </t-tab-panel>
    </t-tabs>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { adminApi, type AdminCommunityItem, type AdminUserItem } from '@/api/admin'
import UserAvatar from '@/components/UserAvatar.vue'
import ErrorState from '@/components/ErrorState.vue'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'
import { request } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { errMessage } from '@/utils/error'

defineOptions({ name: 'PlatformConsole' })

const tab = ref<'channels' | 'users'>('channels')

// ---------- 全局统计 ----------
const statsLoading = ref(true)
const stats = ref<Record<string, number> | null>(null)
async function loadStats() {
  statsLoading.value = true
  try {
    stats.value = await request<Record<string, number>>({ url: '/admin/stats' })
  } catch (e) {
    toast(errMessage(e, '加载统计失败'), 'error')
  } finally {
    statsLoading.value = false
  }
}

// ---------- 频道管理 ----------
interface ChRow extends AdminCommunityItem {
  _busy?: boolean
}
const channels = ref<ChRow[]>([])
const chPage = ref(0)
const chTotal = ref(0)
const chLoading = ref(false)
const chError = ref('')
const chKeyword = ref('')
const chStatus = ref<number | undefined>(undefined)

async function loadChannels(page: number, append = false) {
  if (chLoading.value) return
  chLoading.value = true
  chError.value = ''
  try {
    const data = await adminApi.adminCommunities(chKeyword.value || undefined, chStatus.value, page, 20)
    channels.value = append ? [...channels.value, ...data.items] : data.items
    chPage.value = page
    chTotal.value = data.total
  } catch (e) {
    if (!append) chError.value = errMessage(e, '加载频道失败')
    else toast(errMessage(e, '加载频道失败'), 'error')
  } finally {
    chLoading.value = false
  }
}
function onChSearch() {
  loadChannels(1)
}

// 频道列表滚动到底自动加载下一页
const chScrollEnabled = computed(() => tab.value === 'channels' && channels.value.length < chTotal.value && !chLoading.value)
useInfiniteScroll({ enabled: chScrollEnabled, load: () => loadChannels(chPage.value + 1, true) })

async function onBanChannel(c: ChRow, ban: boolean) {
  const action = ban ? '封禁频道' : '解除封禁'
  const tip = ban
    ? `封禁后全体用户无法访问频道「${c.name}」（内容保留），仅平台管理员可解封。确定继续？`
    : `解封后频道「${c.name}」立即恢复对外可见。确定继续？`
  if (!(await confirmDialog(action, tip))) return
  c._busy = true
  try {
    await request<unknown>({ url: `/communities/${c.id}/status`, method: 'PUT', data: { status: ban ? 2 : 0 } })
    c.status = ban ? 2 : 0
    toast(ban ? '频道已封禁' : '频道已解封', 'success')
  } catch (e) {
    toast(errMessage(e, '操作失败'), 'error')
  } finally {
    c._busy = false
  }
}

// ---------- 用户管理 ----------
interface URow extends AdminUserItem {
  _busy?: boolean
}
const users = ref<URow[]>([])
const uPage = ref(0)
const uTotal = ref(0)
const uLoading = ref(false)
const uError = ref('')
const uKeyword = ref('')
const uStatus = ref<number | undefined>(undefined)

async function loadUsers(page: number, append = false) {
  if (uLoading.value) return
  uLoading.value = true
  uError.value = ''
  try {
    const data = await adminApi.adminUsers(uKeyword.value || undefined, uStatus.value, page, 20)
    users.value = append ? [...users.value, ...data.items] : data.items
    uPage.value = page
    uTotal.value = data.total
  } catch (e) {
    if (!append) uError.value = errMessage(e, '加载用户失败')
    else toast(errMessage(e, '加载用户失败'), 'error')
  } finally {
    uLoading.value = false
  }
}
function onUSearch() {
  loadUsers(1)
}

// 用户列表滚动到底自动加载下一页
const uScrollEnabled = computed(() => tab.value === 'users' && users.value.length < uTotal.value && !uLoading.value)
useInfiniteScroll({ enabled: uScrollEnabled, load: () => loadUsers(uPage.value + 1, true) })

async function onBanUser(u: URow, ban: boolean) {
  const name = u.nickname || u.username
  const action = ban ? '封禁用户' : '解除封禁'
  const tip = ban
    ? `封禁后用户「${name}」将无法登录与访问任何频道。确定继续？`
    : `解封后用户「${name}」恢复正常访问。确定继续？`
  if (!(await confirmDialog(action, tip))) return
  u._busy = true
  try {
    await adminApi.setUserStatus(u.id, ban ? 1 : 0)
    u.status = ban ? 1 : 0
    toast(ban ? '用户已封禁' : '用户已解封', 'success')
  } catch (e) {
    toast(errMessage(e, '操作失败'), 'error')
  } finally {
    u._busy = false
  }
}

onMounted(async () => {
  await loadStats()
  loadChannels(1)
})
</script>

<style scoped>
.console {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.console-header {
  padding: var(--sp-4) 0 var(--sp-3);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
}
.console-title {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 700;
  color: var(--text-1);
}
.console-sub {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.state {
  padding: 48px 0;
  text-align: center;
  color: var(--text-3);
}
.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-card.hot {
  background: var(--brand);
  color: #fff;
  border-color: var(--brand);
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
}
.stat-label {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.stat-card.hot .stat-label {
  color: rgba(255, 255, 255, 0.8);
}
.console-tabs {
  margin-top: var(--sp-3);
}
.toolbar {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
  flex-wrap: wrap;
}
.tb-search {
  flex: 1;
  min-width: 180px;
}
.tb-filter {
  width: 140px;
}
.tbl-head {
  font-weight: 600;
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.tbl-row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) 70px 70px minmax(0, 1fr) 90px 90px;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.tbl-row-users {
  grid-template-columns: minmax(0, 1fr) 70px 110px 90px 90px;
}
.tbl-head.tbl-row {
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--sp-2);
}
/* 用户表只有 5 列：隐藏第 3 列（频道数前移到类型后）undefined，改用另行网格 */
.col-name {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.ch-name,
.u-nick {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.ch-num,
.u-username {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.col-num {
  text-align: center;
  color: var(--text-2);
}
.col-owner,
.col-type {
  color: var(--text-2);
  font-size: var(--fs-caption);
}
.type-plain {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.col-status {
  display: flex;
  align-items: center;
}
.col-op {
  display: flex;
  justify-content: flex-end;
}
.op-disabled {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.load-more {
  margin-top: var(--sp-2);
}
@media (max-width: 720px) {
  .stats-cards {
    grid-template-columns: repeat(3, 1fr);
  }
  .col-num,
  .col-owner,
  .col-type {
    display: none;
  }
  .tbl-row,
  .tbl-row-users {
    grid-template-columns: minmax(0, 1fr) 90px;
  }
}
</style>