<template>
  <main class="auth-page">
    <div class="auth-card">
      <!-- 登录/注册页是全屏无 tab 页，必须有返回站点的出口（#41） -->
      <router-link to="/" class="auth-brand">
        <LogoGithubFilledIcon class="auth-brand-icon" /> SDUdiscord
      </router-link>
      <h1 class="auth-title">登录</h1>
      <p class="auth-sub">使用用户名或邮箱登录 SDUdiscord</p>

      <t-form class="auth-form" label-align="top" @submit.prevent="onSubmit">
        <t-form-item label="用户名 / 邮箱">
          <t-input
            v-model="form.account"
            size="large"
            placeholder="用户名或邮箱"
            autocomplete="username"
            clearable
            required
          />
        </t-form-item>

        <t-form-item label="密码">
          <t-input
            v-model="form.password"
            size="large"
            :type="showPwd ? 'text' : 'password'"
            placeholder="密码"
            :autocomplete="showPwd ? 'off' : 'current-password'"
            clearable
            required
          >
            <template #suffix>
              <button type="button" class="pwd-toggle" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
                {{ showPwd ? '隐藏' : '显示' }}
              </button>
            </template>
          </t-input>
        </t-form-item>

        <p v-if="error" class="error">{{ error }}</p>

        <t-button theme="primary" size="large" type="submit" block :loading="loading">
          {{ loading ? '登录中…' : '登录' }}
        </t-button>
      </t-form>

      <p class="auth-switch">
        还没有账号？
        <router-link to="/register">注册</router-link>
      </p>
    </div>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LogoGithubFilledIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'
import { useAuthStore, type TokenPair } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ account: '', password: '' })
const loading = ref(false)
const error = ref('')
const showPwd = ref(false)

async function onSubmit() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await request<TokenPair>({
      url: '/auth/login',
      method: 'POST',
      data: { account: form.account, password: form.password },
    })
    auth.setTokens(data)
    await auth.fetchMe()
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-6) var(--sp-4);
  background: var(--td-bg-color-page);
}
.auth-card {
  width: 100%;
  max-width: 380px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-5) var(--sp-4) var(--sp-4);
  box-shadow: var(--td-shadow-2);
}
.auth-brand {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--sp-2);
  font-size: var(--fs-body);
  font-weight: 700;
  color: var(--brand);
  text-decoration: none;
}
.auth-brand:hover {
  text-decoration: underline;
}
.auth-brand-icon {
  width: 18px;
  height: 18px;
}
.auth-title {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 600;
}
.auth-sub {
  margin: var(--sp-1) 0 var(--sp-5);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.auth-form :deep(.t-form__item) {
  margin-bottom: 0;
}
.pwd-toggle {
  border: none;
  background: transparent;
  padding: 2px 4px;
  color: var(--td-text-color-secondary);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.pwd-toggle:hover {
  color: var(--brand);
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-error-color);
}
.auth-switch {
  margin: var(--sp-5) 0 0;
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
</style>
