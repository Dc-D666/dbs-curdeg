<template>
  <main class="auth-page">
    <div class="auth-card">
      <h1 class="auth-title">注册</h1>
      <p class="auth-sub">创建 SDUdiscord 账号</p>

      <form class="auth-form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="field-label">用户名</span>
          <input
            v-model.trim="form.username"
            class="input"
            type="text"
            placeholder="3-32 位字母数字下划线"
            autocomplete="username"
            required
          />
        </label>

        <label class="field">
          <span class="field-label">邮箱</span>
          <input
            v-model.trim="form.email"
            class="input"
            type="email"
            placeholder="用于接收验证码"
            autocomplete="email"
            required
          />
        </label>

        <div class="field">
          <span class="field-label">验证码</span>
          <div class="code-row">
            <input
              v-model.trim="form.code"
              class="input code-input"
              type="text"
              maxlength="6"
              placeholder="6 位验证码"
              inputmode="numeric"
              required
            />
            <button
              type="button"
              class="btn-ghost"
              :disabled="sending || countdown > 0"
              @click="sendCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : sending ? '发送中…' : '发送验证码' }}
            </button>
          </div>
        </div>

        <label class="field">
          <span class="field-label">密码</span>
          <input
            v-model="form.password"
            class="input"
            type="password"
            placeholder="至少 6 位，含字母和数字"
            autocomplete="new-password"
            required
          />
        </label>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="btn-primary" type="submit" :disabled="loading">
          {{ loading ? '注册中…' : '注册' }}
        </button>
      </form>

      <p class="auth-switch">
        已有账号？
        <router-link to="/login">登录</router-link>
      </p>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { request } from '@/api/http'
import { useAuthStore, type TokenPair } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({
  username: '',
  email: '',
  code: '',
  password: '',
})
const loading = ref(false)
const sending = ref(false)
const error = ref('')
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

async function sendCode() {
  if (sending.value || countdown.value > 0) return
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    error.value = '请先填写正确的邮箱'
    return
  }
  sending.value = true
  error.value = ''
  try {
    await request({ url: '/auth/send-code', method: 'POST', data: { email: form.email } })
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }, 1000)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '验证码发送失败'
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  if (loading.value) return
  // 本地校验（与后端规则一致，避免提交后才报笼统的"参数错误"）
  if (!/^[a-zA-Z0-9_]{3,32}$/.test(form.username)) {
    error.value = '用户名需为 3-32 位字母、数字或下划线'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    error.value = '请填写正确的邮箱'
    return
  }
  if (!/^\d{6}$/.test(form.code)) {
    error.value = '验证码为 6 位数字'
    return
  }
  if (form.password.length < 6 || !/[a-zA-Z]/.test(form.password) || !/\d/.test(form.password)) {
    error.value = '密码至少 6 位，且需同时包含字母和数字'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await request<TokenPair>({
      url: '/auth/register',
      method: 'POST',
      data: { ...form },
    })
    auth.setTokens(data)
    await auth.fetchMe()
    router.push('/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '注册失败'
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-6) var(--sp-4);
}
.auth-card {
  width: 100%;
  max-width: 380px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-5) var(--sp-4) var(--sp-4);
}
.auth-title {
  margin: 0;
  font-size: var(--fs-page);
  font-weight: 600;
}
.auth-sub {
  margin: var(--sp-1) 0 var(--sp-5);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.field-label {
  font-size: var(--fs-caption);
  color: var(--text-2);
}
.input {
  height: 40px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-body);
  color: var(--text-1);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  outline: none;
  transition: border-color 0.15s;
}
.input:focus {
  border-color: var(--brand);
}
.input::placeholder {
  color: var(--text-3);
}
.code-row {
  display: flex;
  gap: var(--sp-2);
}
.code-input {
  flex: 1;
}
.btn-ghost {
  height: 40px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--brand);
  font-size: var(--fs-caption);
  white-space: nowrap;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.btn-ghost:hover:not(:disabled) {
  border-color: var(--brand);
}
.btn-ghost:disabled {
  color: var(--text-3);
  cursor: not-allowed;
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--danger);
}
.btn-primary {
  height: 40px;
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover {
  background: var(--brand-hover);
}
.btn-primary:disabled {
  background: var(--text-3);
  cursor: not-allowed;
}
.auth-switch {
  margin: var(--sp-5) 0 0;
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>
