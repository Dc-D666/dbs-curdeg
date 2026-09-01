<template>
  <main class="workspace" :class="{ wide: isWide, 'with-tab': embeddedInTab }">
    <div v-if="loading && !community" class="state">加载中…</div>

    <template v-else-if="community">
      <!-- 桌面三栏（≥1024px） -->
      <template v-if="isWide">
        <div class="ws-grid">
          <aside class="ws-left">
            <!-- 发现：选中后在中间栏展示发现帖子流 -->
            <div class="ws-rail-title">导航</div>
            <nav class="ws-nav">
              <button
                class="ws-nav-item"
                :class="{ active: leftMode === 'discover' }"
                @click="selectDiscover"
              >
                <BrowseIcon class="ws-nav-icon" />发现
              </button>
            </nav>

            <!-- 我的频道：选中频道才展开其版块 -->
            <div class="ws-rail-title">我的频道</div>
            <div class="ws-channels">
              <template v-for="c in myChannels" :key="c.id">
                <button
                  class="ws-channel"
                  :class="{ active: leftMode === 'channel' && c.id === cid }"
                  @click="selectChannel(c.id)"
                >
                  <ChevronRightIcon class="ws-channel-arrow" :class="{ expanded: leftMode === 'channel' && c.id === cid }" />
                  <UserAvatar :name="c.name" :src="c.avatar_url" :size="22" />
                  <span class="ws-channel-name">{{ c.name }}</span>
                </button>
                <!-- 仅选中频道展开板块 -->
                <div v-if="leftMode === 'channel' && c.id === cid" class="ws-boards">
                  <button
                    v-for="b in community?.boards ?? []"
                    :key="b.id"
                    class="ws-board"
                    :class="{ active: b.id === activeBoard }"
                    @click="activeBoard = b.id"
                  >
                    <span class="ws-board-hash">#</span>{{ b.name }}
                  </button>
                  <p v-if="(community?.boards ?? []).length === 0" class="ws-empty">暂无版块</p>
                </div>
              </template>
              <p v-if="myChannels.length === 0" class="ws-empty">去发现页加入频道</p>
            </div>
          </aside>

          <section class="ws-main">
            <!-- 发现模式：中间栏显示发现帖子流（热门/已加入 + 搜索） -->
            <template v-if="leftMode === 'discover'">
              <div class="ws-discover">
                <div class="ws-discover-tabs">
                  <t-radio-group v-model="discoverTab" variant="default-filled" size="small">
                    <t-radio-button value="hot">全站热门</t-radio-button>
                    <t-radio-button value="joined">已加入的最新</t-radio-button>
                  </t-radio-group>
                  <div class="ws-discover-search">
                    <t-input v-model.trim="discoverQ" size="small" placeholder="搜索帖子…" clearable @enter="doDiscoverSearch" />
                    <t-button size="small" variant="outline" :disabled="!discoverQ" @click="doDiscoverSearch">搜索</t-button>
                  </div>
                </div>
                <!-- 搜索结果 -->
                <div v-if="discoverSearching" class="ws-discover-results">
                  <div class="ws-discover-meta">
                    <span v-if="discoverTotal" class="ws-discover-count">“{{ discoverLastQ }}” 共 {{ discoverTotal }} 条</span>
                    <t-button variant="text" size="small" @click="clearDiscoverSearch">返回帖子流</t-button>
                  </div>
                  <div v-if="discoverLoading" class="state">搜索中…</div>
                  <EmptyState v-else-if="discoverResults.length === 0" text="没有找到相关帖子" />
                  <div v-else class="feed-list">
                    <router-link v-for="p in discoverResults" :key="p.id" :to="`/p/${p.id}`" class="ws-search-card">
                      <div class="ws-search-head">
                        <h3 class="ws-search-title" v-html="p.highlight_title || p.title"></h3>
                        <span v-if="p.is_top" class="tag tag-top">置顶</span>
                      </div>
                      <p class="ws-search-snippet" v-html="p.snippet"></p>
                      <div class="ws-search-meta">
                        <span>{{ p.community_name }} · {{ p.board_name }}</span>
                        <span>{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
                        <span class="ws-search-time">{{ timeAgo(p.created_at) }}</span>
                      </div>
                    </router-link>
                  </div>
                  <t-button v-if="discoverHasMore" variant="outline" block class="load-more" :loading="discoverLoading" @click="loadMoreDiscover">
                    {{ discoverLoading ? '加载中…' : '加载更多' }}
                  </t-button>
                </div>
                <!-- 帖子流 -->
                <div v-else class="ws-discover-feed">
                  <template v-if="discoverTab === 'joined'">
                    <FeedStreamList v-if="tokenStore.access" view="joined" empty-text="你还没有加入频道，去发现频道吧" />
                    <EmptyState v-else text="登录后查看你加入频道的动态" action-text="去登录" to="/login" />
                  </template>
                  <FeedStreamList v-else view="hot" />
                </div>
              </div>
            </template>

            <!-- 频道模式：频道头 + 内联发帖 + 信息流 -->
            <template v-else>
              <div class="ws-channel-head">
                <img v-if="community.avatar_url" :src="community.avatar_url" class="ws-avatar" alt="" />
                <div class="ws-head-main">
                  <div class="ws-head-name">
                    <router-link :to="`/c/${community.id}`" class="ws-head-link">{{ community.name }}</router-link>
                    <span v-if="community.is_member" class="tag tag-member">已加入</span>
                  </div>
                  <p class="ws-profile">{{ community.profile || '暂无简介' }}</p>
                  <div class="ws-meta">{{ community.member_count }} 成员 · {{ community.boards.length }} 版块 · #{{ community.number }}</div>
                </div>
                <div class="ws-actions">
                  <router-link v-if="community.is_member && (community.my_member_type === 0 || community.my_member_type === 1)" :to="`/c/${community.id}/admin`" class="ws-manage-link">管理</router-link>
                  <t-button v-if="community.is_member && community.my_member_type !== 0" variant="outline" size="small" @click="onLeave">退出</t-button>
                  <t-button v-else-if="!community.is_member" theme="primary" size="small" :loading="joining" @click="onJoin">加入</t-button>
                </div>
              </div>

              <!-- 发帖容器：贴到中间栏底部（符合"下方发帖"操作习惯），信息流在其上方滚动 -->
              <div class="ws-composer-anchor">
                <QuickComposer v-if="community.is_member && activeBoardInfo" :cid="community.id" :bid="activeBoard ?? 0" @posted="onQuickPosted" />
              </div>

              <div v-if="activeBoardInfo" class="ws-feed">
                <div class="feed-toolbar">
                  <t-radio-group v-model="feedSort" variant="default-filled" size="small">
                    <t-radio-button value="latest">最新</t-radio-button>
                    <t-radio-button value="hot">热门</t-radio-button>
                  </t-radio-group>
                  <t-button
                    v-if="community.is_member"
                    theme="primary"
                    size="small"
                    @click="router.push(`/c/${community.id}/boards/${activeBoard}/post/new`)"
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
            </template>
          </section>

          <aside class="ws-right">
            <!-- 管理中心 / 运营中心入口（频道主/有权限管理员） -->
            <div v-if="showMgmtEntries" class="ws-panel">
              <div class="ws-rail-title">频道管理</div>
              <div class="ws-mgmt">
                <router-link :to="`/c/${cid}/admin`" class="ws-mgmt-item">
                  <SettingIcon class="ws-mgmt-icon" />管理中心
                </router-link>
                <router-link :to="`/c/${cid}/ops`" class="ws-mgmt-item">
                  <ChartIcon class="ws-mgmt-icon" />运营中心
                </router-link>
              </div>
            </div>

            <div class="ws-panel">
              <div class="ws-rail-title">话题</div>
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
              <p v-else class="ws-empty">暂无话题</p>
            </div>

            <div class="ws-panel">
              <div class="ws-rail-title">今日热议</div>
              <div v-if="hotPosts.length" class="hot-list">
                <button v-for="p in hotPosts" :key="p.id" class="hot-item" @click="openHotPost(p.id)">
                  <span class="hot-title">{{ p.title }}</span>
                  <span class="hot-meta">{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
                </button>
              </div>
              <p v-else class="ws-empty">暂无热门</p>
            </div>
          </aside>
        </div>
      </template>

      <!-- 移动端纵向：上（频道切换）→ 中（内联发帖+信息流）→ 下（话题+热议） -->
      <template v-else>
        <div class="ws-top">
          <div class="ws-channel-head">
            <img v-if="community.avatar_url" :src="community.avatar_url" class="ws-avatar" alt="" />
            <div class="ws-head-main">
              <div class="ws-head-name">
                <router-link :to="`/c/${community.id}`" class="ws-head-link">{{ community.name }}</router-link>
                <span v-if="community.is_member" class="tag tag-member">已加入</span>
              </div>
              <p class="ws-profile">{{ community.profile || '暂无简介' }}</p>
              <div class="ws-meta">{{ community.member_count }} 成员 · {{ community.boards.length }} 版块 · #{{ community.number }}</div>
            </div>
            <div class="ws-actions">
              <t-button v-if="community.is_member && community.my_member_type !== 0" variant="outline" size="small" @click="onLeave">退出</t-button>
              <t-button v-else-if="!community.is_member" theme="primary" size="small" :loading="joining" @click="onJoin">加入</t-button>
            </div>
          </div>

          <div v-if="myChannels.length" class="ws-chips">
            <button
              v-for="c in myChannels"
              :key="c.id"
              class="ws-chip"
              :class="{ active: c.id === cid }"
              :title="c.name"
              @click="switchChannel(c.id)"
            >
              <UserAvatar :name="c.name" :src="c.avatar_url" :size="30" />
              <span class="ws-chip-name">{{ c.name }}</span>
            </button>
          </div>

          <div class="ws-boards-row">
            <t-radio-group v-model="activeBoard" variant="default-filled" size="small" class="ws-board-tabs">
              <t-radio-button v-for="b in community.boards" :key="b.id" :value="b.id">{{ b.name }}</t-radio-button>
            </t-radio-group>
            <p v-if="community.boards.length === 0" class="ws-empty">暂无版块</p>
          </div>
        </div>

        <div class="ws-middle">
          <QuickComposer v-if="community.is_member && activeBoardInfo" :cid="community.id" :bid="activeBoard ?? 0" @posted="onQuickPosted" />
          <div v-if="activeBoardInfo" class="ws-feed">
            <div class="feed-toolbar">
              <t-radio-group v-model="feedSort" variant="default-filled" size="small">
                <t-radio-button value="latest">最新</t-radio-button>
                <t-radio-button value="hot">热门</t-radio-button>
              </t-radio-group>
              <t-button
                v-if="community.is_member"
                theme="primary"
                size="small"
                @click="router.push(`/c/${community.id}/boards/${activeBoard}/post/new`)"
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
        </div>

        <div class="ws-bottom">
          <section class="ws-panel">
            <div class="ws-rail-title">话题</div>
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
              </div>
            </div>
            <p v-else class="ws-empty">暂无话题</p>
          </section>

          <section class="ws-panel">
            <div class="ws-rail-title">今日热议</div>
            <div v-if="hotPosts.length" class="hot-list">
              <button v-for="p in hotPosts" :key="p.id" class="hot-item" @click="openHotPost(p.id)">
                <span class="hot-title">{{ p.title }}</span>
                <span class="hot-meta">{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
              </button>
            </div>
            <p v-else class="ws-empty">暂无热门</p>
          </section>
        </div>
      </template>
    </template>

    <!-- 加载失败：区分「频道确实不存在」与「网络/服务端故障（可重试）」 -->
    <ErrorState
      v-else-if="!loading"
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
        <t-input v-model="topicForm.description" placeholder="话题描述（选填）" maxlength="255" class="topic-input" />
        <t-textarea v-model="topicForm.rules" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="话题规则（选填）" maxlength="500" />
      </div>
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BrowseIcon, ChartIcon, ChevronRightIcon, SettingIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Community, type TopicItem } from '@/api/community'
import { postApi, type PostItem } from '@/api/post'
import FeedCard from '@/components/FeedCard.vue'
import FeedStreamList from '@/components/FeedStreamList.vue'
import QuickComposer from '@/components/QuickComposer.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import SkeletonFeed from '@/components/SkeletonFeed.vue'
import EmptyState from '@/components/EmptyState.vue'
import { searchApi, type SearchResult } from '@/api/search'
import { usePostDrawer } from '@/stores/postDrawer'
import { useLiveStore } from '@/stores/live'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'
import { confirmDialog } from '@/utils/confirm'
import { loadErrorMessage } from '@/utils/error'
import { timeAgo } from '@/utils/time'
import ErrorState from '@/components/ErrorState.vue'

const props = withDefaults(
  defineProps<{ cid: number; embeddedInTab?: boolean }>(),
  { embeddedInTab: false },
)
const emit = defineEmits<{
  (e: 'change', cid: number): void
  /** 频道加载失败（notFound=true 表示记忆/传入的频道已不存在，供首页回退处理） */
  (e: 'load-error', notFound: boolean): void
}>()

const router = useRouter()
const live = useLiveStore()
const community = ref<Community | null>(null)
const loading = ref(true)
const loadError = ref('')
const notFound = ref(false)
const joining = ref(false)
const activeBoard = ref<number | null>(null)

// 桌面三栏判定（≥1024px）
const isWide = ref(window.innerWidth >= 1024)
function onResize() {
  isWide.value = window.innerWidth >= 1024
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

/** 就地切换频道（首页工作台不跳路由，仅换内容）。 */
function switchChannel(id: number) {
  if (id === props.cid) return
  emit('change', id)
}

// ========== 左栏导航：发现 / 频道树 ==========
// 'discover'：左栏选中「发现」，中间栏显示发现帖子流；'channel'：频道模式
const leftMode = ref<'discover' | 'channel'>('channel')

/** 选中「发现」：中间栏切换为发现帖子流。 */
function selectDiscover() {
  leftMode.value = 'discover'
}

/** 选中某频道：切到频道模式（左栏展开其版块），并就地切换频道。 */
function selectChannel(id: number) {
  leftMode.value = 'channel'
  if (id !== props.cid) emit('change', id)
}

// ========== 发现帖子流（中间栏） ==========
const discoverTab = ref<'hot' | 'joined'>('hot')
const discoverQ = ref('')
const discoverSearching = ref(false)
const discoverLoading = ref(false)
const discoverResults = ref<SearchResult[]>([])
const discoverTotal = ref(0)
const discoverPage = ref(0)
const discoverHasMore = ref(false)
const discoverLastQ = ref('')

async function doDiscoverSearch() {
  const q = discoverQ.value.trim()
  if (!q || discoverLoading.value) return
  discoverSearching.value = true
  discoverLastQ.value = q
  discoverResults.value = []
  discoverPage.value = 0
  discoverHasMore.value = false
  await loadMoreDiscover()
}

async function loadMoreDiscover() {
  if (discoverLoading.value) return
  discoverLoading.value = true
  try {
    const page = discoverResults.value.length === 0 ? 1 : discoverPage.value + 1
    const data = await searchApi.posts(discoverLastQ.value, { page, page_size: 20 })
    const seen = new Set(discoverResults.value.map((p) => p.id))
    discoverResults.value = discoverResults.value.length === 0
      ? data.items
      : [...discoverResults.value, ...data.items.filter((p) => !seen.has(p.id))]
    discoverTotal.value = data.total
    discoverPage.value = page
    discoverHasMore.value = data.has_more
  } catch (e) {
    toast(e instanceof Error ? e.message : '搜索失败', 'error')
  } finally {
    discoverLoading.value = false
  }
}

function clearDiscoverSearch() {
  discoverSearching.value = false
  discoverResults.value = []
  discoverTotal.value = 0
  discoverPage.value = 0
  discoverHasMore.value = false
  discoverQ.value = ''
}

// 频道管理入口可见：频道主 或 拥有成员管理/内容管理权限（运营中心后端已校验）
const showMgmtEntries = computed(() => {
  const c = community.value
  if (!c || !c.is_member) return false
  if (c.is_owner) return true
  return c.my_perms.includes('member_manage') || c.my_perms.includes('moderate')
})

// 今日热议
const hotPosts = ref<PostItem[]>([])
async function loadHotPosts() {
  const id = props.cid
  try {
    const data = await postApi.feed(id, 'hot', null, 5)
    if (props.cid === id) hotPosts.value = data.items
  } catch {
    /* ignore */
  }
}

/**
 * 默认版块选择：优先挑"第一个当前用户能看到帖子的版块"，
 * 避免落点撞上无内容的空版块（空态），造成信息流空白但「今日热议」有帖的割裂体验。
 * 仅在频道已切换、且首次加载时探测一次，探测失败回退第一个版块。
 */
async function pickDefaultBoard(c: Community): Promise<number> {
  const boards = c.boards
  const probeN = Math.min(boards.length, 6)
  const orders = boards
    .slice(0, probeN)
    .filter((b) => b.status !== 1) // 跳过已下架版块
  for (const b of orders) {
    try {
      const data = await postApi.feed(c.id, 'latest', null, 1, b.id)
      if (data.items.length > 0) return b.id
    } catch {
      /* ignore，继续探测下一个 */
    }
  }
  return orders[0]?.id ?? boards[0].id
}

// 话题
const topics = ref<TopicItem[]>([])
const topicSort = ref<'hot' | 'latest'>('hot')
const topicDialog = ref(false)
const topicSaving = ref(false)
const topicForm = reactive({ id: 0, name: '', description: '', rules: '' })

async function loadTopics() {
  const id = props.cid
  try {
    const data = await communityApi.topics(id, topicSort.value)
    if (props.cid === id) topics.value = data
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
      await communityApi.updateTopic(props.cid, topicForm.id, {
        name: topicForm.name,
        description: topicForm.description,
        rules: topicForm.rules,
      })
      toast('话题已更新')
    } else {
      await communityApi.createTopic(props.cid, {
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
    await communityApi.deleteTopic(props.cid, t.id)
    await loadTopics()
    toast('话题已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

const activeBoardInfo = computed(
  () => community.value?.boards.find((b) => b.id === activeBoard.value) ?? null,
)

// 信息流
const feedItems = ref<PostItem[]>([])
const feedSort = ref<'latest' | 'hot'>('latest')
const feedCursor = ref<string | null>(null)
const feedHasMore = ref(false)
const feedLoading = ref(false)

async function loadFeed(reset = false) {
  if (!activeBoard.value || feedLoading.value) return
  const id = props.cid
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
      if (props.cid !== id) return // 已切频道：丢弃过期结果
      // 按 id 去重：置顶帖每页都会返回，避免"加载更多"后重复
      const seen = new Set(feedItems.value.map((p) => p.id))
      const fresh = data.items.filter((p) => !seen.has(p.id))
      const merged = reset
        ? data.items
        : [...feedItems.value, ...fresh]
      feedItems.value = merged
      feedCursor.value = data.next_cursor
      feedHasMore.value = data.has_more
      // 有新条目或没有下一页则结束；整页重复/空页则续拉下一页
      if (fresh.length > 0 || !feedHasMore.value) break
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    feedLoading.value = false
  }
}

function onQuickPosted() {
  loadFeed(true)
}

const postDrawer = usePostDrawer()
function openHotPost(id: number) {
  if (window.innerWidth >= 1024) postDrawer.open(id)
  else router.push(`/p/${id}`)
}

watch(feedSort, () => loadFeed(true))
watch(activeBoard, (bid) => {
  if (bid) loadFeed(true)
})

// 频道加载：初次 + cid 变化（首页就地切换）
async function loadAll() {
  const id = props.cid
  loading.value = true
  community.value = null
  activeBoard.value = null
  feedItems.value = []
  feedCursor.value = null
  feedHasMore.value = false
  topics.value = []
  hotPosts.value = []
  loadError.value = ''
  notFound.value = false
  try {
    const c = await communityApi.get(id)
    if (props.cid !== id) return
    community.value = c
    // 访问打点：供运营中心统计访问人数/次数（失败静默，不影响浏览）
    if (tokenStore.access) communityApi.visit(id).catch(() => {})
    if (c.boards.length > 0) activeBoard.value = await pickDefaultBoard(c)
    loadTopics()
    loadHotPosts()
  } catch (e) {
    if (props.cid === id) {
      community.value = null
      const r = loadErrorMessage(e, '频道', '频道不存在或已解散')
      notFound.value = r.notFound
      loadError.value = r.text
      emit('load-error', r.notFound)
    }
  } finally {
    if (props.cid === id) loading.value = false
  }
}

watch(
  () => props.cid,
  (id) => {
    leftMode.value = 'channel' // 切换频道时回到频道模式（左栏展开其版块）
    loadAll()
    live.setActive(id)
  },
)

// 首页被 <keep-alive> 缓存：切走时组件不卸载，需用 deactivated 释放频道上下文
onActivated(() => live.setActive(props.cid))
onDeactivated(() => live.setActive(null))

// P1 ③：收到「新讨论」药丸的查看请求 → 重拉当前版块首屏
function onLiveRefresh() {
  if (activeBoard.value) loadFeed(true)
}

onMounted(() => {
  loadAll()
  loadMyChannels()
  // 声明当前频道上下文：新内容药丸只统计该频道的新帖（#31）
  live.setActive(props.cid)
  window.addEventListener('live:refresh', onLiveRefresh)
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  live.setActive(null)
  window.removeEventListener('live:refresh', onLiveRefresh)
  window.removeEventListener('resize', onResize)
})

async function onJoin() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(router.currentRoute.value.fullPath)}`)
    return
  }
  if (joining.value) return
  joining.value = true
  try {
    await communityApi.join(props.cid)
    community.value = await communityApi.get(props.cid)
    loadMyChannels() // 刷新左栏/顶部我的频道列表
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    joining.value = false
  }
}

async function onLeave() {
  if (!(await confirmDialog('退出频道', '确定退出该频道？'))) return
  try {
    await communityApi.leave(props.cid)
    community.value = await communityApi.get(props.cid)
    loadMyChannels() // 退出后从我的频道列表移除
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}
</script>

<style scoped>
.workspace {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.workspace.wide {
  max-width: none;
  margin: 0;
  padding: 0;
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
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

/* ===== 桌面三栏网格 ===== */
.ws-grid {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 300px;
  height: calc(100vh - var(--nav-height));
  min-height: 0;
  border-top: 1px solid var(--border);
}
.ws-left {
  border-right: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.ws-main {
  overflow-y: auto;
  padding: var(--sp-4);
}
.ws-right {
  border-left: 1px solid var(--border);
  background: var(--surface-2);
  overflow-y: auto;
  padding: var(--sp-3);
}
.ws-rail-title {
  font-size: var(--fs-caption);
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 0.05em;
  margin: var(--sp-3) 0 var(--sp-2);
}
.ws-rail-title:first-child {
  margin-top: 0;
}
/* 左栏「发现」导航项 */
.ws-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ws-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-control);
  color: var(--text-2);
  text-align: left;
  cursor: pointer;
  font-size: var(--fs-body);
}
.ws-nav-item:hover {
  background: var(--surface);
}
.ws-nav-item.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.ws-nav-icon {
  width: 18px;
  height: 18px;
}
/* 频道行展开箭头 */
.ws-channel-arrow {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--text-3);
  transition: transform 0.15s;
}
.ws-channel-arrow.expanded {
  transform: rotate(90deg);
}
.ws-channels,
.ws-boards {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ws-channel,
.ws-board {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-control);
  color: var(--text-2);
  text-align: left;
  cursor: pointer;
}
.ws-channel:hover,
.ws-board:hover {
  background: var(--surface);
}
.ws-channel.active,
.ws-board.active {
  background: var(--brand-weak);
  color: var(--brand);
  font-weight: 600;
}
.ws-channel-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ws-board-hash {
  opacity: 0.5;
}
.ws-empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
  margin: var(--sp-1) 0;
}
.ws-channel-head {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.ws-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-control);
  object-fit: cover;
}
.ws-head-main {
  flex: 1;
  min-width: 0;
}
.ws-head-name {
  font-size: var(--fs-page);
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.ws-head-link {
  color: var(--text-1);
  text-decoration: none;
}
.ws-head-link:hover {
  color: var(--brand);
}
.ws-profile {
  margin: 4px 0 0;
  color: var(--text-2);
  line-height: 1.6;
}
.ws-meta {
  margin-top: 4px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.ws-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.ws-manage-link {
  font-size: var(--fs-caption);
  color: var(--brand);
  white-space: nowrap;
}
.ws-feed .feed-toolbar {
  margin-bottom: var(--sp-3);
}
/* 发帖容器：贴住中间栏底部（信息流在其上方滚动），符合"下方发帖"操作习惯 */
.ws-composer-anchor {
  position: sticky;
  bottom: 0;
  z-index: 5;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-container);
  box-shadow: var(--shadow-sm);
  padding: var(--sp-2);
  margin-bottom: var(--sp-3);
}
.ws-composer-anchor .quick-composer {
  margin-bottom: 0;
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
.ws-panel {
  padding: var(--sp-2) 0;
}
/* 管理中心 / 运营中心入口 */
.ws-mgmt {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ws-mgmt-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: var(--radius-control);
  color: var(--text-2);
  text-decoration: none;
  font-size: var(--fs-body);
}
.ws-mgmt-item:hover {
  background: var(--surface);
  color: var(--brand);
}
.ws-mgmt-icon {
  width: 16px;
  height: 16px;
  color: var(--brand);
}
/* 发现模式（中间栏） */
.ws-discover {
  padding: var(--sp-2) 0;
}
.ws-discover-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  flex-wrap: wrap;
}
.ws-discover-search {
  display: flex;
  gap: var(--sp-2);
}
.ws-discover-search :deep(.t-input) {
  width: 200px;
}
.ws-discover-results {
  margin-top: var(--sp-1);
}
.ws-discover-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.ws-discover-count {
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.ws-search-card {
  display: block;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
}
.ws-search-card:hover {
  border-color: var(--brand);
}
.ws-search-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.ws-search-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.ws-search-title :deep(em.hl),
.ws-search-snippet :deep(em.hl) {
  font-style: normal;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 2px;
  padding: 0 1px;
}
.ws-search-snippet {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-body);
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ws-search-meta {
  margin-top: var(--sp-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.ws-search-time {
  margin-left: auto;
}
.topic-toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
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
  width: 100%;
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

/* ===== 移动端纵向：上/中/下 ===== */
.ws-top {
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.ws-chips {
  display: flex;
  gap: var(--sp-3);
  overflow-x: auto;
  padding: var(--sp-2) var(--sp-2) var(--sp-1);
  margin: 0 calc(-1 * var(--sp-2));
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  /* 两端渐隐遮罩：滚动条已隐藏，用“内容被裁切”暗示可横滑（#51） */
  -webkit-mask-image: linear-gradient(
    to right,
    transparent 0,
    #000 14px,
    #000 calc(100% - 14px),
    transparent 100%
  );
  mask-image: linear-gradient(
    to right,
    transparent 0,
    #000 14px,
    #000 calc(100% - 14px),
    transparent 100%
  );
}
.ws-chips::-webkit-scrollbar {
  display: none;
}
.ws-chip {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  max-width: 60px;
  padding: 0;
}
.ws-chip.active .ws-chip-name {
  color: var(--brand);
  font-weight: 600;
}
.ws-chip-name {
  /* 60px 只能显 5 个汉字，长名字几乎必然截断（#51） */
  max-width: 72px;
  font-size: 11px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ws-boards-row {
  margin-top: var(--sp-2);
}
.ws-board-tabs {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.ws-middle {
  margin-bottom: var(--sp-4);
}
.ws-bottom .ws-panel {
  border-top: 1px solid var(--border);
  padding: var(--sp-3) 0;
}
</style>
