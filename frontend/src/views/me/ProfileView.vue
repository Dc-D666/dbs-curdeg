<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">个人资料</h1>
    </header>

    <section class="panel">
      <div class="avatar-row">
        <div class="avatar-wrap">
          <t-avatar :image="auth.user?.avatar_url || undefined" size="64px" class="avatar">
            <template #icon>{{ initial }}</template>
          </t-avatar>
          <label class="avatar-edit" title="更换头像">
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onAvatarChange" />
            <span>更换</span>
          </label>
        </div>
        <div class="avatar-side">
          <p class="avatar-name">@{{ auth.user?.username }}</p>
          <p class="avatar-meta">注册于 {{ createdDate }}</p>
          <p v-if="avatarMsg" class="msg avatar-msg">{{ avatarMsg }}</p>
        </div>
      </div>
    </section>

    <section class="panel">
      <h3 class="panel-title">基本信息</h3>
      <t-form class="form" label-align="top" @submit="onSave">
        <t-form-item label="昵称">
          <t-input v-model="form.nickname" size="large" maxlength="64" clearable placeholder="设置一个昵称" />
        </t-form-item>
        <t-form-item label="简介">
          <t-textarea v-model="form.bio" :autosize="{ minRows: 3, maxRows: 6 }" maxlength="255" placeholder="介绍一下自己" />
        </t-form-item>
        <t-form-item label="性别">
          <t-select v-model="form.gender" size="large" class="full-width">
            <t-option :value="0" label="保密" />
            <t-option :value="1" label="男" />
            <t-option :value="2" label="女" />
          </t-select>
        </t-form-item>
        <t-form-item label="所在地">
          <t-space :size="12" class="full-width">
            <t-input v-model="form.province" size="large" maxlength="32" clearable placeholder="省份" />
            <t-input v-model="form.city" size="large" maxlength="32" clearable placeholder="城市" />
          </t-space>
        </t-form-item>
        <p v-if="msg" class="msg" :class="{ error: error }">{{ msg }}</p>
        <t-button theme="primary" size="large" type="submit" block :loading="saving">
          {{ saving ? '保存中…' : '保存' }}
        </t-button>
      </t-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { request } from '@/api/http'
import { useAuthStore, type UserInfo } from '@/stores/auth'

const auth = useAuthStore()
const form = reactive({ nickname: '', bio: '', gender: 0, province: '', city: '' })
const saving = ref(false)
const msg = ref('')
const error = ref(false)
const avatarMsg = ref('')

const initial = computed(() => (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1).toUpperCase())
const createdDate = computed(() => (auth.user?.created_at || '').slice(0, 10))

onMounted(async () => {
  const me = auth.user ?? (await auth.fetchMe())
  if (me) {
    form.nickname = me.nickname
    form.bio = me.bio
    form.gender = me.gender
    form.province = me.province
    form.city = me.city
  }
})

async function onAvatarChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  avatarMsg.value = '上传中…'
  const fd = new FormData()
  fd.append('file', file)
  try {
    const updated = await request<UserInfo>({ url: '/users/me/avatar', method: 'POST', data: fd })
    auth.user = updated
    error.value = false
    avatarMsg.value = '头像已更新'
  } catch (err) {
    error.value = true
    avatarMsg.value = err instanceof Error ? err.message : '上传失败'
  }
}

async function onSave() {
  if (saving.value) return
  saving.value = true
  msg.value = ''
  error.value = false
  try {
    const updated = await request<UserInfo>({ url: '/users/me', method: 'PUT', data: form })
    auth.user = updated
    msg.value = '已保存'
  } catch (e) {
    error.value = true
    msg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
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
.avatar-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}
.avatar-wrap {
  position: relative;
  flex-shrink: 0;
}
.avatar-edit {
  position: absolute;
  right: -2px;
  bottom: -2px;
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: 10px;
  font-size: 11px;
  color: var(--td-text-color-secondary);
  padding: 0 4px;
  cursor: pointer;
}
.avatar-edit input {
  display: none;
}
.avatar-side {
  min-width: 0;
}
.avatar-name {
  margin: 0;
  font-size: var(--fs-body);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.avatar-meta {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.avatar-msg {
  margin-top: var(--sp-2);
}
.panel-title {
  margin: 0 0 var(--sp-4);
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
.full-width {
  width: 100%;
}
.msg {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--td-success-color);
}
.msg.error {
  color: var(--td-error-color);
}
</style>