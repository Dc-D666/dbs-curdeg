<template>
  <!-- 可聚焦/回车打开：桌面开抽屉、移动跳页，无法用纯 router-link，
       用 role=link + tabindex + Enter 达成键盘可达性（#38） -->
  <article
    class="feed-card"
    role="link"
    tabindex="0"
    :aria-label="post.title"
    @click="goDetail"
    @keydown.enter="goDetail"
  >
    <div class="fc-head">
      <span class="fc-title">{{ post.title }}</span>
      <t-tag v-if="post.is_top" theme="danger" variant="light" size="small">置顶</t-tag>
      <t-tag v-if="post.is_essence" theme="warning" variant="light" size="small">精华</t-tag>
    </div>

    <!-- 图片：自适应栅格 + 懒加载 + 灯箱 -->
    <div v-if="post.images.length" class="fc-media" :class="imgClass">
      <img
        v-for="(img, i) in post.images.slice(0, 9)"
        :key="img"
        :src="img"
        :alt="post.title"
        loading="lazy"
        class="fc-img"
        :class="{ loaded: imgLoaded[img] }"
        @click.stop="openLightbox(i)"
        @load="markLoaded(img)"
      />
    </div>

    <!-- 正文：折叠 + 渐变遮罩 + 展开全文 -->
    <p v-if="post.source_markdown" ref="excerptEl" class="fc-excerpt" :class="{ clamped, expanded: !clamped }">
      {{ post.source_markdown }}
    </p>
    <button v-if="overflowing" class="fc-expand" @click.stop="clamped = !clamped">
      {{ clamped ? '展开全文' : '收起' }}
    </button>

    <div class="fc-meta">
      <router-link
        v-if="showCommunity"
        :to="`/c/${post.community_id}`"
        class="fc-community"
        @click.stop
      >{{ post.community_name }}</router-link>
      <router-link :to="`/users/${post.author_id}`" class="fc-author" @click.stop>
        <UserAvatar :name="post.author_nickname" :src="post.author_avatar" :size="18" />
        {{ post.author_nickname }}
      </router-link>
      <span class="fc-stat">{{ post.comment_count }} 评论</span>
      <span class="fc-time">{{ timeAgo(post.created_at) }}</span>
    </div>
    <div class="fc-actions">
      <button class="fc-action" :class="{ liked: post.is_liked }" :disabled="interaction.isPending(`like:${post.id}`)" @click.stop="toggleLike">
        <ThumbUpIcon :key="popTick" class="fc-action-icon" :class="{ 'liked-pop': post.is_liked }" />
        <span>{{ post.is_liked ? '已赞' : '赞' }}</span>
        <span v-if="post.like_count" class="fc-action-count">{{ post.like_count }}</span>
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ThumbUpIcon } from 'tdesign-icons-vue-next'
import type { PostItem } from '@/api/post'
import { postApi } from '@/api/post'
import { tokenStore } from '@/api/http'
import UserAvatar from '@/components/UserAvatar.vue'
import { useInteractionStore } from '@/stores/interaction'
import { usePostDrawer } from '@/stores/postDrawer'
import { useLightboxStore } from '@/stores/lightbox'
import { timeAgo } from '@/utils/time'
import { toast } from '@/utils/toast'

const props = withDefaults(
  defineProps<{ post: PostItem; showCommunity?: boolean }>(),
  { showCommunity: false },
)

const emit = defineEmits<{ (e: 'updated'): void }>()
const router = useRouter()
const route = useRoute()
const interaction = useInteractionStore()
// 点赞图标弹跳动画重触发：每次点赞更新 key 使图标重挂载，重新播放 CSS 动画
const popTick = ref(0)

// ---------- 图片栅格 / 懒加载 / 全局灯箱 ----------
// 全局单例灯箱（#59）：不再每张卡片各挂一个 Teleport 实例
const lightbox = useLightboxStore()
const imgLoaded = reactive<Record<string, boolean>>({})

const imgClass = computed(() => {
  const n = Math.min(props.post.images.length, 9)
  if (n === 1) return 'cols-1'
  if (n === 2) return 'cols-2'
  if (n === 4) return 'cols-2'
  return 'cols-3'
})

function markLoaded(url: string) {
  imgLoaded[url] = true
  // 懒加载图片就位后卡片高度变化，重测「展开全文」判定（#58）
  measureOverflow()
}

function openLightbox(i: number) {
  lightbox.open(props.post.images.slice(0, 9), i)
}

// ---------- 正文折叠 + 渐变遮罩 ----------
const excerptEl = ref<HTMLElement | null>(null)
const clamped = ref(true)
const overflowing = ref(false)

async function measureOverflow() {
  await nextTick()
  const el = excerptEl.value
  if (!el) {
    overflowing.value = false
    return
  }
  // -webkit-line-clamp 下 scrollHeight 仍为完整内容高度，可与可视高度比较判断是否溢出
  overflowing.value = el.scrollHeight > el.clientHeight + 2
}

onMounted(() => {
  measureOverflow()
  window.addEventListener('resize', measureOverflow)
  // web 字体就位后行高变化，也会影响折叠判定（#58）
  document.fonts?.ready.then(() => measureOverflow()).catch(() => {})
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', measureOverflow)
})
watch(() => props.post.source_markdown, () => {
  clamped.value = true
  measureOverflow()
})

function goDetail() {
  // 桌面端用右侧抽屉保持上下文；移动端整页跳转体验更好
  if (window.innerWidth >= 1024) {
    usePostDrawer().open(props.post.id)
  } else {
    router.push(`/p/${props.post.id}`)
  }
}

function requireLogin(): boolean {
  if (tokenStore.access) return true
  router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
  return false
}

async function toggleLike() {
  if (!requireLogin()) return
  const p = props.post
  const key = `like:${p.id}`
  if (interaction.isPending(key)) return
  const wasLiked = p.is_liked
  const prevCount = p.like_count
  popTick.value += 1
  try {
    await interaction.run(key, {
      // 乐观翻转：点击瞬间计数变化，不等接口返回
      apply: () => {
        p.is_liked = !wasLiked
        p.like_count = Math.max(0, prevCount + (wasLiked ? -1 : 1))
      },
      rollback: () => {
        p.is_liked = wasLiked
        p.like_count = prevCount
      },
      request: () => (wasLiked ? postApi.unlike(p.id) : postApi.like(p.id)),
      // 成功后以服务端权威计数校准（消除并发期间的误差）
      onSuccess: (r) => {
        p.like_count = r.count
      },
    })
    emit('updated')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}
</script>

<style scoped>
.feed-card {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-container);
  padding: var(--sp-4);
  cursor: pointer;
  transition: box-shadow var(--anim-duration) var(--anim-ease),
    border-color var(--anim-duration) var(--anim-ease);
}
.feed-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-md);
}
/* 键盘导航落焦样式（配合 useGlobalShortcuts 的 J/K 落焦高亮） */
.feed-card:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}
.fc-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.fc-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 图片栅格：1/2/4/9 宫格 */
.fc-media {
  display: grid;
  gap: 6px;
  margin: var(--sp-3) 0 0;
}
.fc-media.cols-1 {
  grid-template-columns: 1fr;
}
.fc-media.cols-2 {
  grid-template-columns: repeat(2, 1fr);
}
.fc-media.cols-3 {
  grid-template-columns: repeat(3, 1fr);
}
.fc-img {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--radius-btn);
  object-fit: cover;
  background: var(--bg-secondary);
  opacity: 0;
  transition: opacity 0.35s ease;
}
.fc-img.loaded {
  opacity: 1;
}
.fc-media.cols-1 .fc-img {
  aspect-ratio: 16 / 9;
}

/* 正文：默认折叠 4 行 + 渐变遮罩，展开后取消限制 */
.fc-excerpt {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-body);
  color: var(--text-2);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.fc-excerpt.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  position: relative;
}
.fc-excerpt.clamped::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 24px;
  background: linear-gradient(to bottom, transparent, var(--bg-card));
}
.fc-excerpt.expanded {
  white-space: normal;
}
.fc-expand {
  margin-top: 6px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--brand);
  font-size: var(--fs-caption);
  cursor: pointer;
}

.fc-meta {
  margin-top: var(--sp-3);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-3);
  font-size: 12px;
  color: var(--text-3);
}
.fc-community {
  color: var(--brand);
}
.fc-author {
  color: var(--text-3);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.fc-author:hover {
  color: var(--brand);
}
.fc-stat {
  color: var(--text-3);
}
.fc-time {
  margin-left: auto;
}
.fc-actions {
  margin-top: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: 1px solid var(--border);
}
.fc-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px; /* 触摸热区（>=32px），避免移动端难点/误触 */
  padding: 4px 10px;
  border: none;
  background: transparent;
  color: var(--text-3);
  font-size: 12px;
  cursor: pointer;
  border-radius: var(--radius-btn);
  transition: color var(--anim-duration) var(--anim-ease),
    background var(--anim-duration) var(--anim-ease);
}
.fc-action:hover {
  color: var(--brand);
  background: var(--brand-weak);
}
.fc-action.liked {
  color: var(--td-brand-color);
}
.fc-action.liked .fc-action-icon {
  fill: currentColor;
}
.fc-action.liked .fc-action-icon.liked-pop {
  animation: like-pop 0.3s ease;
}
@keyframes like-pop {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.4);
  }
  100% {
    transform: scale(1);
  }
}
.fc-action:disabled {
  cursor: default;
  opacity: 0.6;
}
.fc-action-icon {
  width: 15px;
  height: 15px;
}
.fc-action-count {
  font-variant-numeric: tabular-nums;
}
</style>
