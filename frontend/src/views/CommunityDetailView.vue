<template>
  <main class="detail" :class="{ wb: isWide }">
    <header v-if="!isWide" class="page-header">
      <!-- 返回优先回来源页（首页工作台/我的频道/发现），深链进入才兜底「发现」 -->
      <button type="button" class="back" @click="goBack">
        <ArrowLeftIcon class="back-icon" /> 返回
      </button>
      <h1 class="page-title">{{ community?.name || '频道' }}</h1>
      <span v-if="community?.is_member" class="tag tag-member">已加入</span>
    </header>

    <!-- 宽屏顶部条：三栏布局下没有底部 tabbar，必须自带返回/面包屑/站点导航，
         否则桌面用户（尤其游客从分享链接进入）页面上没有任何导航控件 -->
    <header v-if="isWide" class="wb-topbar">
      <button type="button" class="wb-back" @click="goBack">
        <ArrowLeftIcon class="back-icon" />返回
      </button>
      <!-- 面包屑从「发现」起：发现页是频道列表入口，与移动端返回目标一致 -->
      <nav class="wb-crumb">
        <router-link to="/discover" class="wb-crumb-link">发现</router-link>
        <template v-if="community">
          <span class="wb-crumb-sep">/</span>
          <span class="wb-crumb-cur">{{ community.name }}</span>
        </template>
      </nav>
      <div class="wb-top-links">
        <router-link to="/" class="wb-top-link">首页</router-link>
        <router-link to="/discover" class="wb-top-link">发现</router-link>
        <router-link v-if="tokenStore.access" to="/me" class="wb-top-link">我的</router-link>
        <router-link v-else to="/login" class="wb-top-link">登录</router-link>
      </div>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="community">
      <template v-if="!isWide">
      <section class="panel head-panel">
        <div v-if="community.cover_url" class="cover" :style="{ backgroundImage: `url('${community.cover_url}')` }"></div>
        <div class="head-title-row">
          <img v-if="community.avatar_url" :src="community.avatar_url" class="head-avatar" alt="" />
          <h1 class="head-name">{{ community.name }}</h1>
        </div>
        <p class="profile">{{ community.profile || '暂无简介' }}</p>
        <div class="meta">
          <!-- 成员数即花名册入口：点击查看按身份组排列的成员列表 -->
          <button type="button" class="meta-link" @click="rosterOpen = true">
            {{ community.member_count }} 成员<ChevronRightIcon class="meta-link-icon" />
          </button>
          <span>{{ community.boards.length }} 个版块</span>
          <span>#{{ community.number }}</span>
        </div>
        <div class="actions">
          <template v-if="community.is_member">
            <t-button v-if="community.my_member_type !== 0" variant="outline" @click="onLeave">退出频道</t-button>
            <!-- 频道主不能退出（须解散），不能让按钮无声消失（#53） -->
            <span v-else class="owner-exit-hint">频道主不可退出，如需关闭频道请使用下方「解散频道」</span>
          </template>
          <t-button v-else theme="primary" :loading="joining" @click="onJoin">
            {{ joining ? '处理中…' : '加入频道' }}
          </t-button>
        </div>
      </section>

      <section class="panel">
        <t-radio-group v-model="activeBoard" variant="default-filled" size="small" class="board-tabs">
          <t-radio-button v-for="b in community.boards" :key="b.id" :value="b.id">
            {{ b.name }}
          </t-radio-button>
        </t-radio-group>
        <p v-if="community.boards.length === 0" class="no-board">暂无版块</p>
        <div v-if="activeBoardInfo" class="board-desc">{{ activeBoardInfo.description || '暂无版块描述' }}</div>
      </section>

      <!-- 话题（P0） -->
      <section class="panel topic-panel">
        <div class="panel-title-row">
          <h3 class="panel-title">话题</h3>
          <div class="topic-toolbar">
            <t-radio-group v-model="topicSort" variant="default-filled" size="small">
              <t-radio-button value="hot">热度</t-radio-button>
              <t-radio-button value="latest">最新</t-radio-button>
            </t-radio-group>
            <t-button v-if="community.is_member" variant="outline" size="small" @click="openTopicDialog()">+ 新建</t-button>
          </div>
        </div>
        <div v-if="topics.length" class="topic-list">
          <div v-for="t in topics" :key="t.id" class="topic-item">
            <span class="topic-name">#{{ t.name }}</span>
            <span class="topic-count">{{ t.post_count }} 帖 · 热度 {{ t.heat_value }}</span>
            <div v-if="community.my_member_type === 0 || community.my_member_type === 1" class="topic-ops">
              <t-button variant="text" size="small" @click="openTopicDialog(t)">编辑</t-button>
              <t-button variant="text" size="small" theme="danger" @click="removeTopic(t)">删除</t-button>
            </div>
          </div>
        </div>
        <p v-else class="no-board">暂无话题</p>
      </section>

      <section v-if="activeBoardInfo" class="panel feed-panel">
        <QuickComposer
          v-if="community.is_member"
          :cid="cid"
          :bid="activeBoard ?? 0"
          @posted="onQuickPosted"
        />
        <div class="feed-toolbar">
          <t-radio-group v-model="feedSort" variant="default-filled" size="small">
            <t-radio-button value="latest">最新</t-radio-button>
            <t-radio-button value="hot">热门</t-radio-button>
          </t-radio-group>
          <t-button
            v-if="community.is_member"
            theme="primary"
            size="small"
            @click="router.push(`/c/${cid}/boards/${activeBoard}/post/new`)"
          >发帖</t-button>
        </div>

        <SkeletonFeed v-if="feedLoading && feedItems.length === 0" :count="2" />
        <EmptyState v-else-if="feedItems.length === 0" text="这里还没有任何讨论，成为第一个开帖分享的人吧！" />
        <div v-else class="feed-list">
          <FeedCard v-for="p in feedItems" :key="p.id" :post="p" />
        </div>
        <t-button v-if="feedHasMore" variant="outline" block class="load-more" :loading="feedLoading" @click="loadFeed()">
          {{ feedLoading ? '加载中…' : '加载更多' }}
        </t-button>
      </section>

      <section v-if="community.my_member_type === 0 || community.my_member_type === 1" class="panel owner-panel">
        <div class="panel-title-row">
          <h3 class="panel-title">频道管理</h3>
          <t-button variant="outline" size="small" @click="router.push(`/c/${cid}/admin`)">管理后台</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">头像 / 封面</span>
          <label class="btn-ghost btn-sm upload-label">
            上传图片
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onCoverUpload" hidden />
          </label>
          <span class="owner-hint">同时设为头像与封面</span>
        </div>

        <div class="owner-row">
          <span class="owner-label">频道状态</span>
          <t-select v-model="statusForm.status" class="status-select">
            <t-option :value="0" label="正常" />
            <t-option :value="1" label="关闭" />
          </t-select>
          <t-button variant="outline" size="small" @click="onStatusSave">保存</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">创建版块</span>
          <t-input v-model.trim="boardForm.name" class="board-input" placeholder="版块名称" maxlength="64" clearable />
          <t-input v-model.trim="boardForm.description" class="board-input" placeholder="简介（可选）" maxlength="255" clearable />
          <t-button variant="outline" size="small" :loading="boardCreating" @click="onCreateBoard">创建</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">成员列表</span>
          <t-button variant="outline" size="small" @click="toggleMembers">{{ membersOpen ? '收起' : `${community.member_count} 人` }}</t-button>
        </div>
        <div v-if="membersOpen" class="manage-list">
          <div v-for="m in members" :key="m.id" class="manage-item">
            <span class="manage-name">{{ m.user_nickname || m.nickname }}</span>
            <span class="manage-type">{{ memberTypeName(m.member_type) }}</span>
          </div>
          <p v-if="members.length === 0" class="manage-empty">暂无成员</p>
          <!-- 大频道成员 >50：不再静默截断，提供继续拉取（#52） -->
          <t-button
            v-if="members.length < membersTotal"
            variant="text"
            size="small"
            class="manage-more"
            @click="loadMoreMembers"
          >加载更多成员（{{ members.length }}/{{ membersTotal }}）</t-button>
        </div>

        <div v-if="community.join_setting === 1" class="owner-row">
          <span class="owner-label">加入审核</span>
          <!-- 待审数用接口 total（#52）：本地数组只拉了前 50 条，大频道会少报 -->
          <t-button variant="outline" size="small" @click="toggleRequests">{{ requestsOpen ? '收起' : `${requestsTotal || requests.length} 条待审` }}</t-button>
        </div>
        <div v-if="requestsOpen" class="manage-list">
          <div v-for="r in requests" :key="r.id" class="manage-item">
            <span class="manage-name">{{ r.user_nickname || r.username }}</span>
            <span class="manage-time">{{ formatTime(r.created_at) }}</span>
            <t-button variant="outline" size="small" @click="handleRequest(r, true)">通过</t-button>
            <t-button variant="outline" size="small" theme="danger" @click="handleRequest(r, false)">驳回</t-button>
          </div>
          <p v-if="requests.length === 0" class="manage-empty">暂无待审申请</p>
          <t-button
            v-if="requests.length < requestsTotal"
            variant="text"
            size="small"
            class="manage-more"
            @click="loadMoreRequests"
          >加载更多申请（{{ requests.length }}/{{ requestsTotal }}）</t-button>
        </div>

        <div class="owner-row">
          <span class="owner-label">AI 频道助手</span>
          <t-button variant="outline" size="small" :loading="aiEnsuring" @click="onEnsureAi">启用</t-button>
          <span class="owner-hint">创建虚拟助手成员，可在发帖评论中 @ 提问</span>
        </div>

        <div class="owner-row">
          <span class="owner-label">解散频道</span>
          <t-button variant="outline" size="small" theme="danger" @click="onDissolve">解散</t-button>
        </div>

        <p v-if="ownerMsg" class="msg" :class="{ 'msg-error': ownerMsgIsError }">{{ ownerMsg }}</p>
      </section>
      </template>

      <!-- 三栏宽屏工作台（桌面 ≥1024px） -->
      <template v-else>
        <div class="wb-grid">
          <!-- 左栏：社区切换 + 版块树 -->
          <aside class="wb-left">
            <div class="wb-rail-title">我的频道</div>
            <div class="wb-channels">
              <router-link v-for="c in myChannels" :key="c.id" :to="`/c/${c.id}`" class="wb-channel" :class="{ active: c.id === cid }">
                <UserAvatar :name="c.name" :src="c.avatar_url" :size="24" />
                <span class="wb-channel-name">{{ c.name }}</span>
              </router-link>
            </div>
            <p v-if="myChannels.length === 0" class="wb-empty wb-rail-empty">
              {{ tokenStore.access ? '还没有加入任何频道' : '登录后这里显示你的频道' }}
              <router-link :to="tokenStore.access ? '/discover' : '/login'" class="wb-empty-link">
                {{ tokenStore.access ? '去发现' : '去登录' }}
              </router-link>
            </p>
            <div class="wb-rail-title">版块</div>
            <nav class="wb-boards">
              <button v-for="b in community.boards" :key="b.id" class="wb-board" :class="{ active: b.id === activeBoard }" @click="activeBoard = b.id">
                <span class="wb-board-hash">#</span>{{ b.name }}
              </button>
              <p v-if="community.boards.length === 0" class="wb-empty">暂无版块</p>
            </nav>
          </aside>

          <!-- 中栏：频道头 + 内联发帖 + 信息流 + 管理入口 -->
          <section class="wb-main">
            <div class="wb-channel-head">
              <img v-if="community.avatar_url" :src="community.avatar_url" class="wb-avatar" alt="" />
              <div class="wb-head-main">
                <div class="wb-head-name">{{ community.name }}<span v-if="community.is_member" class="tag tag-member">已加入</span></div>
                <p class="wb-profile">{{ community.profile || '暂无简介' }}</p>
                <div class="wb-meta">{{ community.member_count }} 成员 · {{ community.boards.length }} 版块 · #{{ community.number }}</div>
              </div>
              <div class="wb-actions">
                <t-button v-if="community.is_member && community.my_member_type !== 0" variant="outline" size="small" @click="onLeave">退出</t-button>
                <t-button v-else-if="!community.is_member" theme="primary" size="small" :loading="joining" @click="onJoin">加入</t-button>
              </div>
            </div>

            <QuickComposer v-if="community.is_member && activeBoardInfo" :cid="cid" :bid="activeBoard ?? 0" @posted="onQuickPosted" />

            <div v-if="activeBoardInfo" class="wb-feed">
              <div class="feed-toolbar">
                <t-radio-group v-model="feedSort" variant="default-filled" size="small">
                  <t-radio-button value="latest">最新</t-radio-button>
                  <t-radio-button value="hot">热门</t-radio-button>
                </t-radio-group>
                <t-button
                  v-if="community.is_member"
                  theme="primary"
                  size="small"
                  @click="router.push(`/c/${cid}/boards/${activeBoard}/post/new`)"
                >发帖</t-button>
              </div>
              <SkeletonFeed v-if="feedLoading && feedItems.length === 0" :count="2" />
              <EmptyState v-else-if="feedItems.length === 0" text="这里还没有任何讨论，成为第一个开帖分享的人吧！" />
              <div v-else class="feed-list">
                <FeedCard v-for="p in feedItems" :key="p.id" :post="p" />
              </div>
              <t-button v-if="feedHasMore" variant="outline" block class="load-more" :loading="feedLoading" @click="loadFeed()">
                {{ feedLoading ? '加载中…' : '加载更多' }}
              </t-button>
            </div>

            <section v-if="community.my_member_type === 0 || community.my_member_type === 1" class="panel owner-panel">
              <div class="panel-title-row">
                <h3 class="panel-title">频道管理</h3>
                <t-button variant="outline" size="small" @click="router.push(`/c/${cid}/admin`)">管理后台</t-button>
              </div>
              <p class="owner-hint">头像/封面、频道状态、版块、成员与违规管理请前往管理后台。</p>
            </section>
          </section>

          <!-- 右栏：成员 + 话题 + 今日热议 -->
          <aside class="wb-right">
            <div class="wb-panel">
              <div class="wb-rail-title-row">
                <div class="wb-rail-title">成员</div>
                <t-button variant="text" size="small" @click="rosterOpen = true">
                  查看全部 {{ community.member_count }} 人
                </t-button>
              </div>
              <div v-if="rosterPreview.length" class="roster-preview">
                <UserAvatar
                  v-for="m in rosterPreview"
                  :key="m.id"
                  :name="m.user_nickname || m.nickname"
                  :src="m.avatar_url"
                  :size="32"
                />
              </div>
              <p v-else class="wb-empty">暂无成员</p>
            </div>

            <div class="wb-panel">
              <div class="wb-rail-title">话题</div>
              <div class="topic-toolbar">
                <t-radio-group v-model="topicSort" variant="default-filled" size="small">
                  <t-radio-button value="hot">热度</t-radio-button>
                  <t-radio-button value="latest">最新</t-radio-button>
                </t-radio-group>
                <t-button v-if="community.is_member" variant="outline" size="small" @click="openTopicDialog()">+ 新建</t-button>
              </div>
              <div v-if="topics.length" class="topic-list">
                <div v-for="t in topics" :key="t.id" class="topic-item">
                  <span class="topic-name">#{{ t.name }}</span>
                  <span class="topic-count">{{ t.post_count }} 帖 · 热度 {{ t.heat_value }}</span>
                  <div v-if="community.my_member_type === 0 || community.my_member_type === 1" class="topic-ops">
                    <t-button variant="text" size="small" @click="openTopicDialog(t)">编辑</t-button>
                    <t-button variant="text" size="small" theme="danger" @click="removeTopic(t)">删除</t-button>
                  </div>
                </div>
              </div>
              <p v-else class="wb-empty">暂无话题</p>
            </div>

            <div class="wb-panel">
              <div class="wb-rail-title">今日热议</div>
              <div v-if="hotPosts.length" class="hot-list">
                <button v-for="p in hotPosts" :key="p.id" class="hot-item" @click="openHotPost(p.id)">
                  <span class="hot-title">{{ p.title }}</span>
                  <span class="hot-meta">{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
                </button>
              </div>
              <p v-else class="wb-empty">暂无热门</p>
            </div>
          </aside>
        </div>
      </template>
    </div>
    <!-- 加载失败：区分「频道确实不存在」与「网络/服务端故障（可重试）」，不再一律报“不存在” -->
    <ErrorState
      v-else
      :text="loadError"
      :retryable="!notFound"
      @retry="loadAll"
    >
      <router-link v-if="notFound" to="/discover" class="state-link">去发现频道</router-link>
    </ErrorState>

    <!-- 话题编辑弹窗 -->
    <t-dialog
      v-model:visible="topicDialog"
      :header="topicForm.id ? '编辑话题' : '新建话题'"
      :confirm-btn="{ content: topicForm.id ? '保存' : '创建', theme: 'primary', loading: topicSaving }"
      cancel-btn="取消"
      @confirm="saveTopic"
    >
      <div class="topic-form">
        <t-input v-model="topicForm.name" placeholder="话题名称（不带 #）" maxlength="32" class="topic-input" />
        <t-input v-model="topicForm.description" placeholder="话题描述（选填）" maxlength="32" class="topic-input" />
        <t-textarea v-model="topicForm.rules" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="话题规则（选填）" maxlength="500" />
      </div>
    </t-dialog>

    <!-- 成员花名册：按身份组排列（头部成员数 / 宽屏右栏两个入口共用） -->
    <MemberRoster v-model:visible="rosterOpen" :cid="cid" />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon, ChevronRightIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Community, type JoinRequestItem, type Member, type TopicItem } from '@/api/community'
import { postApi, type PostItem } from '@/api/post'
import MemberRoster from '@/components/MemberRoster.vue'
import FeedCard from '@/components/FeedCard.vue'
import QuickComposer from '@/components/QuickComposer.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { usePostDrawer } from '@/stores/postDrawer'
import { request, tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { formatTime } from '@/utils/time'
import { loadErrorMessage } from '@/utils/error'
import ErrorState from '@/components/ErrorState.vue'

const route = useRoute()
const router = useRouter()
// cid 随路由参数实时响应：三栏左栏切换频道（/c/:id 复用组件）时必须重载
const cid = computed(() => Number(route.params.id))
const community = ref<Community | null>(null)
const loading = ref(true)
const loadError = ref('')
const notFound = ref(false)
const joining = ref(false)
const activeBoard = ref<number | null>(null)
const ownerMsg = ref('')
// 区分成功/失败提示：失败的 ownerMsg 不能用固定绿色（#24）
const ownerMsgIsError = ref(false)
function setOwnerMsg(text: string, isError = false) {
  ownerMsg.value = text
  ownerMsgIsError.value = isError
}
const statusForm = reactive({ status: 0 })

// 桌面三栏工作台判定（≥1024px）+ 社区切换器（我的频道）
const isWide = ref(window.innerWidth >= 1024)
function onResize() {
  isWide.value = window.innerWidth >= 1024
}

/** 宽屏顶部条返回：有历史记录就退回来源页，否则兜底到「发现」。 */
function goBack() {
  const back = window.history.state?.back
  if (typeof back === 'string' && back) router.back()
  else router.push('/discover')
}
const myChannels = ref<Community[]>([])
async function loadMyChannels() {
  if (!tokenStore.access) return
  try {
    const m = await communityApi.mine()
    const seen = new Set<number>()
    myChannels.value = [...m.owned, ...m.managed, ...m.joined].filter((c) => {
      if (seen.has(c.id)) return false
      seen.add(c.id)
      return true
    })
  } catch {
    /* ignore */
  }
}
// 右栏「今日热议」：取频道热门 Top5（带频道竞态保护，避免切换后旧结果覆盖）
const hotPosts = ref<PostItem[]>([])
async function loadHotPosts() {
  const id = cid.value
  try {
    const data = await postApi.feed(id, 'hot', null, 5)
    if (cid.value === id) hotPosts.value = data.items
  } catch {
    /* ignore */
  }
}

// 管理面板
const boardForm = reactive({ name: '', description: '' })
const boardCreating = ref(false)
const membersOpen = ref(false)
const members = ref<Member[]>([])

// ---------- 成员花名册（公开，按身份组排列） ----------
// 弹层开关：入口在头部「N 成员」与宽屏右栏「成员」面板
const rosterOpen = ref(false)
// 宽屏右栏头像预览（前 12 人，随频道加载）
const rosterPreview = ref<Member[]>([])
async function loadRosterPreview(id: number) {
  try {
    const data = await communityApi.members(id, 1, 12)
    if (cid.value === id) rosterPreview.value = data.items
  } catch {
    /* 预览失败静默：花名册弹层内有错误态与重试 */
  }
}
// 成员/待审分页：接口每页最多 50，大频道需续拉且总数用接口 total（#52）
const membersPage = ref(0)
const membersTotal = ref(0)
const requestsOpen = ref(false)
const requests = ref<JoinRequestItem[]>([])
const requestsPage = ref(0)
const requestsTotal = ref(0)

// 话题（P0）
const topics = ref<TopicItem[]>([])
const topicSort = ref<'hot' | 'latest'>('hot')
const topicDialog = ref(false)
const topicSaving = ref(false)
const topicForm = reactive({ id: 0, name: '', description: '', rules: '' })

async function loadTopics() {
  const id = cid.value
  try {
    const data = await communityApi.topics(id, topicSort.value)
    if (cid.value === id) topics.value = data
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载话题失败', 'error')
  }
}

watch(topicSort, () => loadTopics())

function openTopicDialog(t?: TopicItem) {
  topicForm.id = t?.id ?? 0
  topicForm.name = t?.name ?? ''
  topicForm.description = t?.description ?? ''
  topicForm.rules = t?.rules ?? ''
  topicDialog.value = true
}

async function saveTopic() {
  if (!topicForm.name.trim()) {
    toast('请填写话题名称', 'error')
    return
  }
  topicSaving.value = true
  try {
    if (topicForm.id) {
      await communityApi.updateTopic(cid.value, topicForm.id, {
        name: topicForm.name,
        description: topicForm.description,
        rules: topicForm.rules,
      })
      toast('话题已更新')
    } else {
      await communityApi.createTopic(cid.value, {
        name: topicForm.name,
        description: topicForm.description,
        rules: topicForm.rules,
      })
      toast('话题已创建')
    }
    topicDialog.value = false
    await loadTopics()
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    topicSaving.value = false
  }
}

async function removeTopic(t: TopicItem) {
  if (!(await confirmDialog('删除话题', `确定删除话题「${t.name}」？`))) return
  try {
    await communityApi.deleteTopic(cid.value, t.id)
    await loadTopics()
    toast('话题已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

const activeBoardInfo = computed(
  () => community.value?.boards.find((b) => b.id === activeBoard.value) ?? null,
)

// ---------- 帖子流 ----------
const feedItems = ref<PostItem[]>([])
const feedSort = ref<'latest' | 'hot'>('latest')
const feedCursor = ref<string | null>(null)
const feedHasMore = ref(false)
const feedLoading = ref(false)

async function loadFeed(reset = false) {
  if (!activeBoard.value || feedLoading.value) return
  const id = cid.value
  if (reset) {
    feedItems.value = []
    feedCursor.value = null
    feedHasMore.value = false
  }
  feedLoading.value = true
  try {
    // 置顶帖每页重复返回，去重后可能整页 0 新条目：自动续拉下一页（#55），
    // 上限 5 页防服务端异常时死循环
    for (let attempt = 0; attempt < 5; attempt++) {
      const data = await postApi.feed(id, feedSort.value, feedCursor.value, 20, activeBoard.value)
      if (cid.value !== id) return // 切换频道：丢弃过期结果
      // 按 id 去重：置顶帖每页都会返回，避免"加载更多"后重复
      const seen = new Set(feedItems.value.map((p) => p.id))
      const fresh = data.items.filter((p) => !seen.has(p.id))
      const merged = reset
        ? data.items
        : [...feedItems.value, ...fresh]
      feedItems.value = merged
      feedCursor.value = data.next_cursor
      feedHasMore.value = data.has_more
      // 有新条目或没有下一页则结束；整页重复/空页则续拉下一页（#55）
      if (fresh.length > 0 || !feedHasMore.value) break
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    feedLoading.value = false
  }
}

// Quick Composer 发布成功后重拉当前版块首屏
function onQuickPosted() {
  loadFeed(true)
}

// 右栏「今日热议」点击：桌面打开抽屉，移动端整页跳转
const postDrawer = usePostDrawer()
function openHotPost(id: number) {
  if (window.innerWidth >= 1024) postDrawer.open(id)
  else router.push(`/p/${id}`)
}

watch(feedSort, (s) => {
  loadFeed(true)
})

watch(activeBoard, (bid) => {
  if (bid) loadFeed(true)
})

// ---------- 频道加载：初次 + 路由参数变化（三栏左栏切换） ----------
/** 重置并加载指定频道：清空旧数据 → 拉频道/话题/热门 → 选定版块触发信息流。 */
async function loadAll() {
  const id = cid.value
  loading.value = true
  community.value = null
  activeBoard.value = null
  feedItems.value = []
  feedCursor.value = null
  feedHasMore.value = false
  topics.value = []
  hotPosts.value = []
  members.value = []
  requests.value = []
  membersPage.value = 0
  membersTotal.value = 0
  requestsPage.value = 0
  requestsTotal.value = 0
  membersOpen.value = false
  requestsOpen.value = false
  rosterPreview.value = []
  ownerMsg.value = ''
  ownerMsgIsError.value = false
  loadError.value = ''
  notFound.value = false
  try {
    const c = await communityApi.get(id)
    if (cid.value !== id) return // 已切走：丢弃过期响应
    community.value = c
    statusForm.status = c.status
    if (c.boards.length > 0) {
      activeBoard.value = c.boards[0].id // 触发 watch(activeBoard) → loadFeed
    }
    loadTopics()
    loadHotPosts()
    // 宽屏右栏成员预览：只拉首页 12 人（花名册弹层自己会重拉全量）
    loadRosterPreview(id)
  } catch (e) {
    if (cid.value === id) {
      community.value = null
      const r = loadErrorMessage(e, '频道', '频道不存在或已解散')
      notFound.value = r.notFound
      loadError.value = r.text
    }
  } finally {
    if (cid.value === id) loading.value = false
  }
}

// P1 ③：收到「新讨论」药丸的查看请求 → 重拉当前版块首屏
function onLiveRefresh() {
  if (activeBoard.value) loadFeed(true)
}

onMounted(() => {
  loadAll()
  window.addEventListener('live:refresh', onLiveRefresh)
  window.addEventListener('resize', onResize)
  loadMyChannels()
})
// 路由参数变化（如三栏左栏切频道）：组件复用，需重新加载
watch(cid, () => loadAll())
onBeforeUnmount(() => {
  window.removeEventListener('live:refresh', onLiveRefresh)
  window.removeEventListener('resize', onResize)
})

async function onJoin() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  if (joining.value) return
  joining.value = true
  try {
    await communityApi.join(cid.value)
    community.value = await communityApi.get(cid.value)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    joining.value = false
  }
}

async function onLeave() {
  if (!(await confirmDialog('退出频道', '确定退出该频道？'))) return
  try {
    await communityApi.leave(cid.value)
    community.value = await communityApi.get(cid.value)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onCoverUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  setOwnerMsg('上传中…')
  const fd = new FormData()
  fd.append('file', file)
  try {
    const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
    community.value = await communityApi.update(cid.value, { avatar_url: up.url, cover_url: up.url })
    setOwnerMsg('图片已更新')
  } catch (err) {
    setOwnerMsg(err instanceof Error ? err.message : '上传失败', true)
  }
}

async function onStatusSave() {
  ownerMsg.value = ''
  try {
    community.value = await communityApi.updateStatus(cid.value, statusForm.status)
    setOwnerMsg('状态已保存')
  } catch (err) {
    setOwnerMsg(err instanceof Error ? err.message : '保存失败', true)
  }
}

async function onCreateBoard() {
  if (!boardForm.name) {
    setOwnerMsg('请填写版块名称', true)
    return
  }
  boardCreating.value = true
  ownerMsg.value = ''
  try {
    await communityApi.createBoard(cid.value, { name: boardForm.name, description: boardForm.description })
    boardForm.name = ''
    boardForm.description = ''
    community.value = await communityApi.get(cid.value)
    if (activeBoard.value === null && community.value.boards.length > 0) {
      activeBoard.value = community.value.boards[0].id
    }
    setOwnerMsg('版块已创建')
  } catch (err) {
    setOwnerMsg(err instanceof Error ? err.message : '创建失败', true)
  } finally {
    boardCreating.value = false
  }
}

async function toggleMembers() {
  membersOpen.value = !membersOpen.value
  if (membersOpen.value && members.value.length === 0) {
    await loadMembers(1)
  }
}

async function loadMembers(page: number, append = false) {
  try {
    const data = await communityApi.members(cid.value, page, 50)
    members.value = append ? [...members.value, ...data.items] : data.items
    membersPage.value = page
    membersTotal.value = data.total
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载成员失败', 'error')
  }
}

function loadMoreMembers() {
  return loadMembers(membersPage.value + 1, true)
}

async function toggleRequests() {
  requestsOpen.value = !requestsOpen.value
  if (requestsOpen.value && requests.value.length === 0) {
    await loadRequests(1)
  }
}

async function loadRequests(page: number, append = false) {
  try {
    const data = await communityApi.joinRequests(cid.value, page, 50)
    requests.value = append ? [...requests.value, ...data.items] : data.items
    requestsPage.value = page
    requestsTotal.value = data.total
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载申请失败', 'error')
  }
}

function loadMoreRequests() {
  return loadRequests(requestsPage.value + 1, true)
}

/** 加入申请审核：驳回对申请人不可逆，先二次确认（#54）。 */
async function handleRequest(r: JoinRequestItem, approve: boolean) {
  if (!approve) {
    const ok = await confirmDialog(
      '驳回加入申请',
      `确定驳回 ${r.user_nickname || r.username} 的加入申请？申请人将收到「未通过」的系统通知。`,
    )
    if (!ok) return
  }
  try {
    await communityApi.handleJoinRequest(cid.value, r.id, approve)
    requests.value = requests.value.filter((x) => x.id !== r.id)
    requestsTotal.value = Math.max(0, requestsTotal.value - 1)
    community.value = await communityApi.get(cid.value)
    setOwnerMsg(approve ? '已通过申请' : '已驳回申请')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

function memberTypeName(t: number): string {
  return t === 0 ? '频道主' : t === 1 ? '管理员' : '成员'
}

async function onDissolve() {
  if (!(await confirmDialog('解散频道', '确定解散该频道？此操作不可撤销！'))) return
  try {
    await communityApi.dissolve(cid.value)
    router.push('/discover')
  } catch (e) {
    toast(e instanceof Error ? e.message : '解散失败', 'error')
  }
}

// AI 频道助手：幂等创建虚拟成员（已存在则直接返回），@ 助手即可触发问答
const aiEnsuring = ref(false)
async function onEnsureAi() {
  if (aiEnsuring.value) return
  aiEnsuring.value = true
  try {
    const r = await communityApi.ensureAiAssistant(cid.value)
    setOwnerMsg(`AI 助手「${r.nickname}」已就位，发帖时 @ 助手即可提问`)
  } catch (e) {
    setOwnerMsg(e instanceof Error ? e.message : 'AI 助手创建失败', true)
  } finally {
    aiEnsuring.value = false
  }
}
</script>

<style scoped>
.detail {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.page-header {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.back {
  color: var(--text-3);
  font-size: var(--fs-body);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  /* 返回改为 <button> 后需要重置默认样式 */
  border: none;
  background: none;
  padding: 6px 4px;
  cursor: pointer;
}
.back:hover {
  color: var(--brand);
}
.back-icon {
  width: 16px;
  height: 16px;
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.tag {
  font-size: var(--fs-caption);
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}
.tag-member {
  color: var(--brand);
  border-color: var(--brand-weak);
  background: var(--brand-weak);
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.head-panel .profile {
  margin: 0;
  color: var(--text-2);
}
.cover {
  height: 110px;
  border-radius: var(--radius-card);
  background-size: cover;
  background-position: center;
  margin: calc(-1 * var(--sp-4)) calc(-1 * var(--sp-4)) var(--sp-4);
}
.head-title-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-2);
}
.head-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  object-fit: cover;
  border: 1px solid var(--border);
}
.head-name {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 600;
}
.meta {
  margin-top: var(--sp-3);
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
/* 成员数即花名册入口：与 meta 文案同色，仅 hover 提示可点 */
.meta-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.meta-link:hover {
  color: var(--brand);
}
.meta-link-icon {
  width: 12px;
  height: 12px;
}
.actions {
  margin-top: var(--sp-4);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
/* 频道主退出解释（#53）：按钮位置换成说明文字而不是无声消失 */
.owner-exit-hint {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.manage-more {
  align-self: flex-start;
}
.board-tabs {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.no-board {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.board-desc {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.empty-block {
  margin-top: var(--sp-3);
}
.owner-panel .panel-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);
}
.owner-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  flex-wrap: wrap;
}
.owner-label {
  width: 72px;
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.owner-hint {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.status-select {
  width: 120px;
}
.msg {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--success);
}
/* 失败信息不能用成功色（固定绿色会误导用户以为操作成功） */
.msg-error {
  color: var(--danger);
}
.board-input {
  flex: 1;
  min-width: 120px;
}
.upload-label {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-default);
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.upload-label:hover {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
}
.manage-list {
  margin: var(--sp-1) 0 var(--sp-2) 96px;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.manage-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-1) 0;
  font-size: var(--fs-caption);
  border-bottom: 1px dashed var(--border);
}
.manage-item:last-child {
  border-bottom: none;
}
.manage-name {
  font-weight: 600;
}
.manage-type,
.manage-time {
  color: var(--text-3);
}
.manage-empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.feed-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.feed-list {
  margin: var(--sp-3) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.load-more {
  margin-top: var(--sp-3);
}
.topic-panel .panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.topic-panel .panel-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.topic-toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.topic-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.topic-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.topic-item:last-child {
  border-bottom: none;
}
.topic-name {
  color: #8a6d1a;
  background: #fff7e6;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: var(--fs-body);
}
.topic-count {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.topic-ops {
  margin-left: auto;
  display: flex;
  gap: var(--sp-1);
}
.topic-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
/* ===== 三栏宽屏工作台（桌面 ≥1024px） ===== */
.detail.wb {
  max-width: none;
  margin: 0;
  padding: 0;
}
/* 宽屏顶部条：自带返回 + 面包屑 + 站点导航（三栏页无底部 tabbar，必须提供导航） */
.wb-topbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  height: var(--nav-height);
  padding: 0 var(--sp-4);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.wb-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px 6px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--text-2);
  font-size: var(--fs-body);
  cursor: pointer;
}
.wb-back:hover {
  color: var(--brand);
  border-color: var(--brand);
}
.wb-crumb {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: var(--fs-caption);
}
.wb-crumb-link {
  color: var(--text-3);
}
.wb-crumb-link:hover {
  color: var(--brand);
}
.wb-crumb-sep {
  color: var(--text-3);
}
.wb-crumb-cur {
  color: var(--text-1);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wb-top-links {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-shrink: 0;
}
.wb-top-link {
  font-size: var(--fs-body);
  color: var(--text-2);
}
.wb-top-link:hover,
.wb-top-link.router-link-active {
  color: var(--brand);
}
.wb-rail-empty {
  margin: var(--sp-2) 0 0;
}
.wb-empty-link {
  margin-left: 4px;
  color: var(--brand);
}
.wb-grid {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  /* /c/:id 不是 tab 页（无底部 tabbar，app-shell 也不再垫 tabbar 高度），
   * 只需减去宽屏顶部条高度；多减 tabbar 会在底部留出 56px 空白 */
  height: calc(100vh - var(--nav-height));
  min-height: 0;
}
.wb-left {
  border-right: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.wb-main {
  overflow-y: auto;
  padding: var(--sp-4);
}
.wb-right {
  border-left: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.wb-rail-title {
  font-size: var(--fs-caption);
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 0.05em;
  margin: var(--sp-3) 0 var(--sp-2);
}
/* 右栏面板标题行：标题 + 右侧操作（成员「查看全部」） */
.wb-rail-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wb-rail-title-row .wb-rail-title {
  margin-bottom: var(--sp-2);
}
/* 成员头像预览：横排堆叠 */
.roster-preview {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}
.wb-rail-title:first-child {
  margin-top: 0;
}
.wb-channels {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wb-channel {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-control);
  color: var(--text-2);
  text-decoration: none;
}
.wb-channel:hover {
  background: var(--surface);
}
.wb-channel.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.wb-channel-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wb-boards {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wb-board {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  border: none;
  background: transparent;
  color: var(--text-2);
  border-radius: var(--radius-control);
  text-align: left;
  cursor: pointer;
}
.wb-board:hover {
  background: var(--surface);
}
.wb-board.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.wb-board-hash {
  opacity: 0.5;
}
.wb-channel-head {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.wb-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-control);
  object-fit: cover;
}
.wb-head-main {
  flex: 1;
  min-width: 0;
}
.wb-head-name {
  font-size: var(--fs-page);
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.wb-profile {
  margin: 4px 0 0;
  color: var(--text-2);
  line-height: 1.6;
}
.wb-meta {
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.wb-actions {
  display: flex;
  gap: var(--sp-2);
}
.wb-feed .feed-toolbar {
  margin-bottom: var(--sp-3);
}
.wb-panel {
  padding: var(--sp-2) 0;
}
.wb-empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.hot-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hot-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  padding: 8px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-control);
  background: var(--surface);
  cursor: pointer;
}
.hot-item:hover {
  border-color: var(--brand);
}
.hot-title {
  font-size: var(--fs-body);
  color: var(--text-1);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hot-meta {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
