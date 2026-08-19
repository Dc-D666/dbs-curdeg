<template>
  <main class="me">
    <header class="me-header">
      <router-link to="/" class="back">← 返回</router-link>
      <h1 class="me-title">个人中心</h1>
    </header>

    <section class="panel">
      <div class="profile-row">
        <div class="avatar-wrap">
          <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="avatar-img" alt="头像" />
          <div v-else class="avatar">{{ initial }}</div>
          <label class="avatar-edit" title="更换头像">
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="onAvatarChange" />
            <span>更换</span>
          </label>
        </div>
        <div class="profile-main">
          <p class="nickname">{{ form.nickname || auth.user?.username }}</p>
          <p class="meta">@{{ auth.user?.username }} · 注册于 {{ createdDate }}</p>
        </div>
      </div>
      <p v-if="avatarMsg" class="msg">{{ avatarMsg }}</p>
    </section>

    <section class="panel">
      <h3 class="panel-title">编辑资料</h3>
      <form class="form" @submit.prevent="onSave">
        <label class="field">
          <span class="field-label">昵称</span>
          <input v-model.trim="form.nickname" class="input" type="text" maxlength="64" />
        </label>
        <label class="field">
          <span class="field-label">简介</span>
          <textarea v-model.trim="form.bio" class="input textarea" rows="3" maxlength="255"></textarea>
        </label>
        <label class="field">
          <span class="field-label">性别</span>
          <select v-model.number="form.gender" class="input">
            <option :value="0">保密</option>
            <option :value="1">男</option>
            <option :value="2">女</option>
          </select>
        </label>
        <div class="field-row">
          <label class="field">
            <span class="field-label">省份</span>
            <input v-model.trim="form.province" class="input" type="text" maxlength="32" />
          </label>
          <label class="field">
            <span class="field-label">城市</span>
            <input v-model.trim="form.city" class="input" type="text" maxlength="32" />
          </label>
        </div>
        <p v-if="msg" class="msg">{{ msg }}</p>
        <button class="btn-primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </form>
    </section>

    <section class="panel">
      <router-link to="/me/feed" class="feed-link">
        <span>我关注的频道</span>
        <span class="feed-arrow">→</span>
      </router-link>
    </section>

    <section class="panel">
      <h3 class="panel-title">修改密码</h3>
      <form class="form" @submit.prevent="onChangePassword">
        <label class="field">
          <span class="field-label">原密码</span>
          <input v-model="pwForm.old_password" class="input" type="password" autocomplete="current-password" />
        </label>
        <label class="field">
          <span class="field-label">新密码（至少 6 位，含字母和数字）</span>
          <input v-model="pwForm.new_password" class="input" type="password" autocomplete="new-password" />
        </label>
        <label class="field">
          <span class="field-label">确认新密码</span>
          <input v-model="pwForm.confirm" class="input" type="password" autocomplete="new-password" />
        </label>
        <p v-if="pwMsg" class="msg" :class="{ error: pwError }">{{ pwMsg }}</p>
        <button class="btn-primary" type="submit" :disabled="pwSaving">
          {{ pwSaving ? '提交中…' : '修改密码' }}
        </button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { request } from '@/api/http'
import { useAuthStore, type UserInfo } from '@/stores/auth'

const auth = useAuthStore()
const form = reactive({
  nickname: '',
  bio: '',
  gender: 0,
  province: '',
  city: '',
})
const saving = ref(false)
const msg = ref('')
const avatarMsg = ref('')
const pwForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwSaving = ref(false)
const pwMsg = ref('')
const pwError = ref(false)

const initial = computed(() => (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1).toUpperCase())
const createdDate = computed(() => (auth.user?.created_at || '').slice(0, 10))

onMounted(async () => {
  const me = await auth.fetchMe()
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
    avatarMsg.value = '头像已更新'
  } catch (err) {
    avatarMsg.value = err instanceof Error ? err.message : '上传失败'
  }
}

async function onSave() {
  if (saving.value) return
  saving.value = true
  msg.value = ''
  try {
    const updated = await request<UserInfo>({
      url: '/users/me',
      method: 'PUT',
      data: form,
    })
    auth.user = updated
    msg.value = '已保存'
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

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
}
.me-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
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
.profile-main {
  min-width: 0;
  flex: 1;
}
.profile-main .nickname,
.profile-main .meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--brand-weak);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 600;
}
.avatar-wrap {
  position: relative;
  flex-shrink: 0;
}
.avatar-img {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border);
}
.avatar-edit {
  position: absolute;
  right: -2px;
  bottom: -2px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 11px;
  color: var(--text-2);
  padding: 0 4px;
  cursor: pointer;
}
.avatar-edit input {
  display: none;
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
.field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.field-row {
  display: flex;
  gap: var(--sp-3);
}
.field-row .field {
  flex: 1;
  min-width: 0;
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
.textarea {
  height: auto;
  padding: var(--sp-2) var(--sp-3);
  resize: vertical;
  font-family: inherit;
}
.input:focus {
  border-color: var(--brand);
}
.msg {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--success);
}
.msg.error {
  color: var(--danger);
}
.feed-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-1);
  font-size: var(--fs-body);
  text-decoration: none;
  padding: var(--sp-1) 0;
  min-width: 0;
}
.feed-arrow {
  color: var(--text-3);
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
</style>
