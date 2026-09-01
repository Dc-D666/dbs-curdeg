<template>
  <main class="auth-page">
    <div class="auth-card">
      <!-- 登录/注册页是全屏无 tab 页，必须有返回站点的出口（#41） -->
      <router-link to="/" class="auth-brand">
        <LogoGithubFilledIcon class="auth-brand-icon" /> SDUdiscord
      </router-link>
      <h1 class="auth-title">注册</h1>
      <p class="auth-sub">创建 SDUdiscord 账号</p>

      <t-form class="auth-form" label-align="top" @submit.prevent="onSubmit" novalidate>
        <t-form-item label="用户名">
          <t-input
            ref="usernameRef"
            v-model="form.username"
            size="large"
            placeholder="3-32 位字母数字下划线"
            autocomplete="username"
            clearable
          />
          <p v-if="errors.username" class="field-error">{{ errors.username }}</p>
        </t-form-item>

        <t-form-item label="邮箱">
          <t-input
            ref="emailRef"
            v-model="form.email"
            size="large"
            type="email"
            placeholder="用于接收验证码"
            autocomplete="email"
            clearable
          />
          <p v-if="errors.email" class="field-error">{{ errors.email }}</p>
        </t-form-item>

        <t-form-item label="验证码">
          <div class="code-row">
            <t-input
              ref="codeRef"
              v-model="form.code"
              class="code-input"
              size="large"
              maxlength="6"
              placeholder="6 位验证码"
              clearable
            />
            <t-button
              variant="outline"
              theme="primary"
              :disabled="sending || countdown > 0"
              @click="sendCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : sending ? '发送中…' : '发送验证码' }}
            </t-button>
          </div>
          <p v-if="errors.code" class="field-error">{{ errors.code }}</p>
        </t-form-item>

        <t-form-item label="密码">
          <t-input
            ref="passwordRef"
            v-model="form.password"
            size="large"
            :type="showPwd ? 'text' : 'password'"
            placeholder="至少 6 位，含字母和数字"
            :autocomplete="showPwd ? 'off' : 'new-password'"
            clearable
          >
            <template #suffix>
              <button type="button" class="pwd-toggle" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
                {{ showPwd ? '隐藏' : '显示' }}
              </button>
            </template>
          </t-input>
          <div v-if="form.password" class="pwd-strength" aria-live="polite">
            <span class="pwd-strength-bars">
              <i v-for="i in 3" :key="i" class="pwd-strength-bar" :class="{ on: i <= strengthLevel }" />
            </span>
            <span class="pwd-strength-text">{{ strengthText }}</span>
          </div>
          <p v-if="errors.password" class="field-error">{{ errors.password }}</p>
        </t-form-item>

        <t-form-item label="确认密码">
          <t-input
            ref="confirmRef"
            v-model="form.confirm"
            size="large"
            :type="showPwd ? 'text' : 'password'"
            placeholder="再输入一次密码"
            :autocomplete="showPwd ? 'off' : 'new-password'"
            clearable
          />
          <p v-if="errors.confirm" class="field-error">{{ errors.confirm }}</p>
        </t-form-item>

        <p v-if="error" class="error">{{ error }}</p>

        <t-button theme="primary" size="large" type="submit" block :loading="loading">
          {{ loading ? '注册中…' : '注册' }}
        </t-button>
      </t-form>

      <p class="auth-switch">
        已有账号？
        <router-link to="/login">登录</router-link>
      </p>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LogoGithubFilledIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'
import { useAuthStore, type TokenPair } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({
  username: '',
  email: '',
  code: '',
  password: '',
  confirm: '',
})
const loading = ref(false)
const sending = ref(false)
const error = ref('')
const showPwd = ref(false)

// 字段级校验错误（#43）：提交时逐字段校验并聚焦第一个出错字段
const errors = reactive({ username: '', email: '', code: '', password: '', confirm: '' })
const usernameRef = ref()
const emailRef = ref()
const codeRef = ref()
const passwordRef = ref()
const confirmRef = ref()

// 输入变化即清除该字段的错误，避免改了还挂着旧报错
watch(
  () => form.username, () => (errors.username = ''),
)
watch(
  () => form.email, () => (errors.email = ''),
)
watch(
  () => form.code, () => (errors.code = ''),
)
watch(
  () => form.password, () => (errors.password = ''),
)
watch(
  () => form.confirm, () => (errors.confirm = ''),
)

// ---------- 密码强度（#42）：长度 + 字符种类粗分三档 ----------
const strengthLevel = computed(() => {
  const p = form.password
  if (!p) return 0
  let kinds = 0
  if (/[a-z]/.test(p)) kinds += 1
  if (/[A-Z]/.test(p)) kinds += 1
  if (/\d/.test(p)) kinds += 1
  if (/[^a-zA-Z0-9]/.test(p)) kinds += 1
  if (p.length >= 8 && kinds >= 3) return 3
  if (p.length >= 6 && kinds >= 2) return 2
  return 1
})
const strengthText = computed(() => ['', '弱', '中', '强'][strengthLevel.value] || '')

// ---------- 验证码倒计时：刷新页面不丢（#42） ----------
// 只存「发送时间 + 邮箱」，剩余秒数按当前时间推算，天然免疫刷新
const CODE_SENT_KEY = 'reg_code_sent_at'
const CODE_EMAIL_KEY = 'reg_code_email'
const CODE_WAIT_SECONDS = 60
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function resumeCountdown() {
  const at = Number(sessionStorage.getItem(CODE_SENT_KEY))
  const email = sessionStorage.getItem(CODE_EMAIL_KEY) || ''
  if (!at || !email) return
  const remain = Math.ceil(CODE_WAIT_SECONDS - (Date.now() - at) / 1000)
  if (remain <= 0) {
    sessionStorage.removeItem(CODE_SENT_KEY)
    sessionStorage.removeItem(CODE_EMAIL_KEY)
    return
  }
  // 回填邮箱并继续倒计时：验证码还在路上，用户不用重新填表
  if (!form.email) form.email = email
  countdown.value = remain
  startTimer()
}

function startTimer() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      countdown.value = 0
      if (timer) {
        clearInterval(timer)
        timer = null
      }
      sessionStorage.removeItem(CODE_SENT_KEY)
      sessionStorage.removeItem(CODE_EMAIL_KEY)
    }
  }, 1000)
}

async function sendCode() {
  if (sending.value || countdown.value > 0) return
  errors.email = ''
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = '请先填写正确的邮箱'
    emailRef.value?.focus?.()
    return
  }
  sending.value = true
  error.value = ''
  try {
    await request({ url: '/auth/send-code', method: 'POST', data: { email: form.email } })
    sessionStorage.setItem(CODE_SENT_KEY, String(Date.now()))
    sessionStorage.setItem(CODE_EMAIL_KEY, form.email)
    countdown.value = CODE_WAIT_SECONDS
    startTimer()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '验证码发送失败'
  } finally {
    sending.value = false
  }
}

/** 逐字段校验：返回第一个出错字段的 ref 供聚焦。全部通过返回 null。 */
function validate(): typeof usernameRef | null {
  errors.username = ''
  errors.email = ''
  errors.code = ''
  errors.password = ''
  errors.confirm = ''
  if (!/^[a-zA-Z0-9_]{3,32}$/.test(form.username)) {
    errors.username = '用户名需为 3-32 位字母、数字或下划线'
    return usernameRef
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = '请填写正确的邮箱'
    return emailRef
  }
  if (!/^\d{6}$/.test(form.code)) {
    errors.code = '验证码为 6 位数字'
    return codeRef
  }
  if (form.password.length < 6 || !/[a-zA-Z]/.test(form.password) || !/\d/.test(form.password)) {
    errors.password = '密码至少 6 位，且需同时包含字母和数字'
    return passwordRef
  }
  if (form.confirm !== form.password) {
    errors.confirm = '两次输入的密码不一致'
    return confirmRef
  }
  return null
}

async function onSubmit() {
  if (loading.value) return
  const firstInvalid = validate()
  if (firstInvalid) {
    // 聚焦（并隐式滚动）到第一个出错字段，错误文案就在字段下方
    firstInvalid.value?.focus?.()
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await request<TokenPair>({
      url: '/auth/register',
      method: 'POST',
      data: {
        username: form.username,
        email: form.email,
        code: form.code,
        password: form.password,
      },
    })
    auth.setTokens(data)
    await auth.fetchMe()
    // 注册完成：倒计时状态不再需要
    sessionStorage.removeItem(CODE_SENT_KEY)
    sessionStorage.removeItem(CODE_EMAIL_KEY)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '注册失败'
  } finally {
    loading.value = false
  }
}

onMounted(resumeCountdown)
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
/* 字段级内联错误（#43） */
.field-error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-error-color);
}
.code-row {
  display: flex;
  gap: var(--sp-2);
  width: 100%;
}
.code-input {
  flex: 1;
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
/* 显示密码开关（#42） */
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
/* 密码强度（#42）：三格条 + 文案 */
.pwd-strength {
  display: flex;
  align-items: center;
  gap: 6px;
}
.pwd-strength-bars {
  display: inline-flex;
  gap: 3px;
}
.pwd-strength-bar {
  width: 24px;
  height: 4px;
  border-radius: 2px;
  background: var(--td-component-border);
}
.pwd-strength-bar.on:nth-child(1) {
  background: var(--td-error-color);
}
.pwd-strength-bar.on:nth-child(2) {
  background: var(--td-warning-color);
}
.pwd-strength-bar.on:nth-child(3) {
  background: var(--td-success-color);
}
.pwd-strength-text {
  font-size: var(--fs-caption);
  color: var(--td-text-color-secondary);
}
</style>
