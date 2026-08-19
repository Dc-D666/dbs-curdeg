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
      <span class="fc-stat">{{ post.like_count }} 赞</span>
      <span class="fc-stat">{{ post.comment_count }} 评论</span>
      <span class="fc-time">{{ post.created_at.slice(0, 16) }}</span>
    </div>
  </article>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { PostItem } from '@/api/post'
import UserAvatar from '@/components/UserAvatar.vue'

const props = withDefaults(
  defineProps<{ post: PostItem; showCommunity?: boolean }>(),
  { showCommunity: false },
)

const router = useRouter()
function goDetail() {
  router.push(`/p/${props.post.id}`)
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
  gap: var(--sp-3);
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
</style>
