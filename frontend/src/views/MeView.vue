<template>
  <main class="me">
    <header class="me-header">
      <router-link to="/" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回
      </router-link>
      <h1 class="me-title">个人中心</h1>
    </header>

    <!-- 账号信息卡片 -->
    <section class="profile-card">
      <t-avatar :image="auth.user?.avatar_url || undefined" size="56px" class="profile-avatar">
        <template #icon>{{ initial }}</template>
      </t-avatar>
      <div class="profile-main">
        <p class="nickname">{{ accountName }}</p>
        <p class="meta">@{{ accountName }} · 注册于 {{ createdDate || '—' }}</p>
      </div>
    </section>

    <div class="section">
      <h2 class="section-title">账号</h2>
      <div class="panel">
        <router-link to="/me/profile" class="row">
          <span class="row-icon"><UserIcon class="row-icon-svg" /></span>
          <span class="row-label">个人资料</span>
          <span class="row-hint">昵称、简介、头像</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
        <router-link to="/me/security" class="row">
          <span class="row-icon"><KeyIcon class="row-icon-svg" /></span>
          <span class="row-label">账号安全</span>
          <span class="row-hint">修改密码、注销</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">我的频道</h2>
      <div class="panel">
        <router-link to="/me/channels" class="row">
          <span class="row-icon"><UsergroupIcon class="row-icon-svg" /></span>
          <span class="row-label">我加入的频道</span>
          <span class="row-hint">我创建的、管理的、加入的</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">内容</h2>
      <div class="panel">
        <router-link to="/me/favorites" class="row">
          <span class="row-icon"><StarIcon class="row-icon-svg" /></span>
          <span class="row-label">我的收藏</span>
          <span class="row-hint">收藏的帖子</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
        <router-link to="/me/feed" class="row">
          <span class="row-icon"><ChatIcon class="row-icon-svg" /></span>
          <span class="row-label">我关注的频道</span>
          <span class="row-hint">关注频道的动态</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
      </div>
    </div>

    <div class="section">
      <h2 class="section-title">偏好</h2>
      <div class="panel">
        <router-link to="/me/notification-settings" class="row">
          <span class="row-icon"><NotificationIcon class="row-icon-svg" /></span>
          <span class="row-label">通知设置</span>
          <span class="row-hint">@提及、点赞、评论等</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
      </div>
    </div>

    <div v-if="auth.user?.user_type === 1" class="section">
      <h2 class="section-title">管理</h2>
      <div class="panel">
        <router-link to="/dashboard" class="row">
          <span class="row-icon"><DashboardIcon class="row-icon-svg" /></span>
          <span class="row-label">运营看板</span>
          <span class="row-hint">系统管理员</span>
          <ChevronRightIcon class="row-arrow" />
        </router-link>
      </div>
    </div>

    <t-button variant="outline" theme="default" block class="logout" @click="onLogout">退出登录</t-button>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowLeftIcon, ChatIcon, ChevronRightIcon, DashboardIcon, KeyIcon, NotificationIcon, StarIcon, UserIcon, UsergroupIcon } from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'
import { confirmDialog } from '@/utils/confirm'
import { toast } from '@/utils/toast'

const auth = useAuthStore()
const initial = computed(() => (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1).toUpperCase())
const accountName = computed(() => auth.user?.nickname || auth.user?.username || '未登录')
const createdDate = computed(() => (auth.user?.created_at || '').slice(0, 10))

// 进入个人中心时确保用户态已拉取，避免账号卡片显示空白
onMounted(() => {
  if (!auth.loaded) auth.fetchMe()
})

async function onLogout() {
  if (!(await confirmDialog('退出登录', '确定退出当前账号？'))) return
  auth.logout()
  toast('已退出登录')
  window.location.href = '/'
}
</script>

<style scoped>
.me {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.me-header {
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
}
.back-icon {
  width: 16px;
  height: 16px;
}
.me-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.profile-card {
  margin-top: var(--sp-4);
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: var(--sp-4);
  background: linear-gradient(135deg, var(--brand-weak), transparent);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
}
.profile-avatar {
  flex-shrink: 0;
}
.profile-main {
  min-width: 0;
  flex: 1;
}
.nickname,
.meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.section {
  margin-top: var(--sp-5);
}
.section-title {
  margin: 0 0 var(--sp-2) var(--sp-1);
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--text-3);
}
.panel {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  overflow: hidden;
}
.row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  min-height: 56px;
  color: var(--td-text-color-primary);
  text-decoration: none;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.row:last-child {
  border-bottom: none;
}
.row:active {
  background: var(--bg-secondary);
}
.row-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.row-icon-svg {
  width: 18px;
  height: 18px;
}
.row-label {
  font-size: var(--fs-body);
  font-weight: 500;
  flex-shrink: 0;
}
.row-hint {
  flex: 1;
  min-width: 0;
  text-align: right;
  font-size: var(--fs-caption);
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-arrow {
  width: 16px;
  height: 16px;
  color: var(--text-3);
  flex-shrink: 0;
}
.logout {
  margin-top: var(--sp-5);
}
</style>