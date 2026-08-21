<template>
  <article class="feed-card" @click="goDetail">
    <div class="fc-head">
      <span class="fc-title">{{ post.title }}</span>
      <t-tag v-if="post.is_top" theme="danger" variant="light" size="small">置顶</t-tag>
      <t-tag v-if="post.is_essence" theme="warning" variant="light" size="small">精华</t-tag>
    </div>
    <p v-if="post.images.length" class="fc-thumbs">
      <img v-for="img in post.images.slice(0, 3)" :key="img" :src="img" alt="" />
    </p>
    <p class="fc-excerpt">{{ post.source_markdown }}</p>
    <div class="fc-meta">
      <span v-if="showCommunity" class="fc-community">{{ post.community_name }}</span>
      <router-link :to="`/users/${post.author_id}`" class="fc-author" @click.stop>
        <UserAvatar :name="post.author_nickname" :src="post.author_avatar" :size="18" />
        {{ post.author_nickname }}
      </router-link>
      <span class="fc-stat">{{ post.comment_count }} 评论</span>
      <span class="fc-time">{{ timeAgo(post.created_at) }}</span>
    </div>
    <div class="fc-actions">
      <button class="fc-action" :class="{ liked: post.is_liked }" :disabled="liking" @click.stop="toggleLike">
        <ThumbUpIcon class="fc-action-icon" />
        <span>{{ post.is_liked ? '已赞' : '赞' }}</span>
        <span v-if="post.like_count" class="fc-action-count">{{ post.like_count }}</span>
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ThumbUpIcon } from 'tdesign-icons-vue-next'
import type { PostItem } from '@/api/post'
import { postApi } from '@/api/post'
import { tokenStore } from '@/api/http'
import UserAvatar from '@/components/UserAvatar.vue'
import { timeAgo } from '@/utils/time'
import { toast } from '@/utils/toast'

const props = withDefaults(
  defineProps<{ post: PostItem; showCommunity?: boolean }>(),
  { showCommunity: false },
)

const emit = defineEmits<{ (e: 'updated'): void }>()
const router = useRouter()
const route = useRoute()
const liking = ref(false)

function goDetail() {
  router.push(`/p/${props.post.id}`)
}

function requireLogin(): boolean {
  if (tokenStore.access) return true
  router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
  return false
}

async function toggleLike() {
  if (!requireLogin() || liking.value) return
  const p = props.post
  liking.value = true
  try {
    if (p.is_liked) {
      const r = await postApi.unlike(p.id)
      p.is_liked = false
      p.like_count = r.count
    } else {
      const r = await postApi.like(p.id)
      p.is_liked = true
      p.like_count = r.count
    }
    emit('updated')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    liking.value = false
  }
}
</script>

<style scoped>
.feed-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  cursor: pointer;
  transition: box-shadow var(--anim-duration) var(--anim-ease),
    border-color var(--anim-duration) var(--anim-ease);
}
.feed-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-1);
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
.fc-thumbs {
  display: flex;
  gap: var(--sp-2);
  margin: var(--sp-2) 0 0;
}
.fc-thumbs img {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-btn);
  object-fit: cover;
}
.fc-excerpt {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-body);
  color: var(--text-2);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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
