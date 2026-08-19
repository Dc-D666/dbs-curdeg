<template>
  <main class="profile">
    <header class="page-header">
      <button class="back" @click="$router.back()">← 返回</button>
      <h1 class="page-title">用户主页</h1>
    </header>

    <div v-if="loading" class="state">加载中…</div>

    <section v-else-if="user" class="panel">
      <div class="profile-row">
        <img v-if="user.avatar_url" :src="user.avatar_url" class="avatar-img" alt="头像" />
        <div v-else class="avatar">{{ initial }}</div>
        <div class="profile-main">
          <p class="nickname">{{ user.nickname || user.username }}</p>
          <p class="meta">@{{ user.username }} · 注册于 {{ createdDate }}</p>
        </div>
      </div>
      <p v-if="user.bio" class="bio">{{ user.bio }}</p>
      <p v-else class="bio empty">这个人很懒，什么都没写</p>
      <p v-if="user.province || user.city" class="location">
        📍 {{ user.province }} {{ user.city }}
      </p>
    </section>

    <div v-else class="state">用户不存在</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { userApi, type PublicUser } from '@/api/user'

const route = useRoute()
const uid = Number(route.params.id)
const user = ref<PublicUser | null>(null)
const loading = ref(true)

const initial = computed(() => (user.value?.nickname || user.value?.username || 'U').slice(0, 1).toUpperCase())
const createdDate = computed(() => (user.value?.created_at || '').slice(0, 10))

onMounted(async () => {
  try {
    user.value = await userApi.get(uid)
  } catch {
    user.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile {
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
  border: none;
  background: none;
  color: var(--text-3);
  font-size: var(--fs-body);
  cursor: pointer;
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
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
.profile-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}
.avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--brand-weak);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  flex-shrink: 0;
}
.avatar-img {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border);
  flex-shrink: 0;
}
.nickname {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.meta {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.bio {
  margin: var(--sp-4) 0 0;
  font-size: var(--fs-body);
  color: var(--text-1);
  line-height: 1.6;
}
.bio.empty {
  color: var(--text-3);
}
.location {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
