<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">账号安全</h1>
    </header>

    <section class="panel">
      <h3 class="panel-title">账号信息</h3>
      <t-descriptions bordered size="small" :items="accountItems" :column="1" />
    </section>

    <section class="panel">
      <h3 class="panel-title">修改密码</h3>
      <t-form class="form" label-align="top" @submit="onChangePassword">
        <t-form-item label="原密码">
          <t-input v-model="pwForm.old_password" size="large" type="password" autocomplete="current-password" />
        </t-form-item>
        <t-form-item label="新密码（至少 6 位，含字母和数字）">
          <t-input v-model="pwForm.new_password" size="large" type="password" autocomplete="new-password" />
        </t-form-item>
        <t-form-item label="确认新密码">
          <t-input v-model="pwForm.confirm" size="large" type="password" autocomplete="new-password" />
        </t-form-item>
        <p v-if="pwMsg" class="msg" :class="{ error: pwError }">{{ pwMsg }}</p>
        <t-button theme="primary" size="large" type="submit" block :loading="pwSaving">
          {{ pwSaving ? '提交中…' : '修改密码' }}
        </t-button>
      </t-form>
    </section>

    <section class="panel panel-danger">
      <h3 class="panel-title danger-title">危险操作</h3>
      <t-button variant="outline" theme="danger" block :loading="deactivating" @click="onDeactivate">
        {{ deactivating ? '处理中…' : '注销账号' }}
      </t-button>
      <p class="deactivate-hint">注销后无法登录，频道内的帖子与评论保留（作者标记为已注销）。</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { confirmDialog } from '@/utils/confirm'
import { toast } from '@/utils/toast'

const auth = useAuthStore()
const pwForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwSaving = ref(false)
const pwMsg = ref('')
const pwError = ref(false)
const deactivating = ref(false)

const createdDate = computed(() => (auth.user?.created_at || '').slice(0, 10))

const accountItems = computed(() => [
  { label: '账号', content: auth.user?.username || '—' },
  { label: '邮箱', content: auth.user?.email || '未绑定' },
  { label: '注册时间', content: createdDate.value },
])

async function onChangePassword() {
  if (pwSaving.value) return
  pwMsg.value = ''
  pwError.value = false
  if (pwForm.new_password.length < 6 || !/[a-zA-Z]/.test(pwForm.new_password) || !/\d/.test(pwForm.new_password)) {
    pwMsg.value = '新密码至少 6 位，且需同时包含字母和数字'
    pwError.value = true
    return
  }
  if (pwForm.new_password !== pwForm.confirm) {
    pwMsg.value = '两次输入的新密码不一致'
    pwError.value = true
    return
  }
  pwSaving.value = true
  try {
    await request<null>({
      url: '/auth/password',
      method: 'PUT',
      data: { old_password: pwForm.old_password, new_password: pwForm.new_password },
    })
    pwMsg.value = '密码已修改，下次登录请使用新密码'
    pwForm.old_password = ''
    pwForm.new_password = ''
    pwForm.confirm = ''
  } catch (e) {
    pwMsg.value = e instanceof Error ? e.message : '修改失败'
    pwError.value = true
  } finally {
    pwSaving.value = false
  }
}

async function onDeactivate() {
  if (!(await confirmDialog('注销账号', '确定注销账号？此操作不可撤销！'))) return
  deactivating.value = true
  try {
    await request<null>({ url: '/users/me/deactivate', method: 'POST' })
    auth.logout()
    toast('账号已注销', 'success')
    window.location.href = '/login'
  } catch (e) {
    toast(e instanceof Error ? e.message : '注销失败', 'error')
  } finally {
    deactivating.value = false
  }
}
</script>

<style scoped>
.page {
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
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.panel {
  margin-top: var(--sp-4);
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-4);
}
.panel-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-title);
  font-weight: 600;
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.form :deep(.t-form__item) {
  margin-bottom: 0;
}
.msg {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-success-color);
}
.msg.error {
  color: var(--td-error-color);
}
.panel-danger {
  margin-top: var(--sp-4);
}
.danger-title {
  color: var(--td-error-color);
}
.deactivate-hint {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
</style>