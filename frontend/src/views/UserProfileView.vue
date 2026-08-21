<template>
  <main class="profile">
    <header class="page-header">
      <t-button variant="text" @click="$router.back()">
        <ArrowLeftIcon class="back-icon" /> 返回
      </t-button>
      <h1 class="page-title">用户主页</h1>
    </header>

    <div v-if="loading" class="state">
      <t-skeleton :row="3" :loading="true" animation="gradient" />
    </div>

    <section v-else-if="user" class="panel">
      <div class="profile-row">
        <t-avatar :image="user.avatar_url || undefined" size="64px">
          <template #icon>{{ initial }}</template>
        </t-avatar>
        <div class="profile-main">
          <p class="nickname">{{ user.nickname || user.username }}</p>
          <p class="meta">@{{ user.username }} · 注册于 {{ createdDate }}</p>
        </div>
        <t-button
          v-if="auth.user && auth.user.id !== uid"
          variant="outline"
          :class="{ 't-active': following }"
          :loading="followBusy"
          @click="toggleFollow"
        >{{ following ? '已关注' : '关注' }}</t-button>
      </div>
      <p v-if="user.bio" class="bio">{{ user.bio }}</p>
      <p v-else class="bio empty">这个人很懒，什么都没写</p>
      <p v-if="user.province || user.city" class="location">
        📍 {{ user.province }} {{ user.city }}
      </p>
      <p class="follow-stats">关注 <b>{{ followCount }}</b> 人</p>
    </section>

    <div v-else class="state">用户不存在</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { userApi, type PublicUser } from '@/api/user'
import { useAuthStore } from '@/stores/auth'
import { tokenStore } from '@/api/http'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()
const uid = Number(route.params.id)
const auth = useAuthStore()
const user = ref<PublicUser | null>(null)
const loading = ref(true)
const following = ref(false)
const followBusy = ref(false)
const followCount = ref(0)

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
  if (tokenStore.access && auth.user?.id !== uid) {
    userApi.followStatus(uid).then((r) => (following.value = r.following)).catch(() => {})
  }
})

async function toggleFollow() {
  if (!tokenStore.access) {
    router.push(`/login?redirect=${encodeURIComponent(route.fullPath)}`)
    return
  }
  if (followBusy.value) return
  followBusy.value = true
  try {
    if (following.value) {
      const r = await userApi.unfollow(uid)
      following.value = false
      followCount.value = r.count
    } else {
      const r = await userApi.follow(uid)
      following.value = true
      followCount.value = r.count
      toast('已关注', 'success')
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    followBusy.value = false
  }
}
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
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-4);
}
.profile-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}
.back-icon {
  width: 16px;
  height: 16px;
  vertical-align: -2px;
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
.follow-stats {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.t-active {
  color: var(--td-brand-color);
  border-color: var(--td-brand-color);
}
</style>
