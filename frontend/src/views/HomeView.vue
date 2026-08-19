<template>
  <main class="home">
    <header class="home-header">
      <h1 class="brand">SDUdiscord</h1>
      <nav v-if="auth.user" class="nav">
        <router-link to="/discover" class="nav-link">发现</router-link>
        <router-link to="/me" class="nav-link">
          {{ auth.user.nickname || auth.user.username }}
        </router-link>
        <button class="nav-logout" @click="onLogout">退出</button>
      </nav>
      <nav v-else class="nav">
        <router-link to="/discover" class="nav-link">发现</router-link>
        <router-link to="/login" class="nav-link">登录</router-link>
        <router-link to="/register" class="nav-link">注册</router-link>
      </nav>
    </header>

    <section class="hero">
      <h2 class="hero-title">仿腾讯频道 · 私域社区</h2>
      <p class="hero-desc">频道 → 版块 → 帖子 → 评论，构建你的兴趣社区（课设项目，功能逐步上线）</p>
      <router-link to="/discover" class="btn-primary hero-btn">浏览频道</router-link>
    </section>

    <section class="panel">
      <h3 class="panel-title">功能进度</h3>
      <ul class="progress-list">
        <li class="done">账号系统：注册（邮箱验证码）/ 登录 / JWT / 资料</li>
        <li class="done">频道 / 版块：创建 / 加入 / 审核 / 成员管理 / 图片上传</li>
        <li class="done">内容互动：发帖 / 评论楼中楼 / 点赞 / 关注 / 帖子流</li>
        <li>管理后台 / 搜索：待开发（阶段 4~5）</li>
        <li>通知 / AI：待开发（阶段 6~7）</li>
      </ul>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

onMounted(() => {
  auth.fetchMe()
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.home {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.brand {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--brand);
}
.nav {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  font-size: var(--fs-body);
}
.nav-link {
  color: var(--text-1);
}
.nav-link:hover {
  color: var(--brand);
}
.nav-logout {
  border: none;
  background: none;
  color: var(--text-3);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.hero {
  padding: var(--sp-6) 0 var(--sp-5);
  border-bottom: 1px solid var(--border);
}
.hero-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}
.hero-desc {
  margin: var(--sp-2) 0 0;
  color: var(--text-2);
}
.hero-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: var(--sp-4);
  height: 40px;
  padding: 0 var(--sp-5);
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  text-decoration: none;
}
.hero-btn:hover {
  background: var(--brand-hover);
}
.panel {
  margin-top: var(--sp-5);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-title);
  font-weight: 600;
}
.progress-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  color: var(--text-3);
  font-size: var(--fs-body);
}
.progress-list .done {
  color: var(--text-1);
}
.progress-list .done::before {
  content: '✓ ';
  color: var(--success);
}
</style>
