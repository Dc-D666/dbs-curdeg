<template>
  <main class="discover">
    <header class="page-header">
      <h1 class="page-title">发现频道</h1>
      <button class="btn-primary btn-sm" @click="showCreate = true">创建频道</button>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="communities.length === 0" class="state empty">还没有频道，创建第一个吧</div>
    <div v-else class="list">
      <article
        v-for="c in communities"
        :key="c.id"
        class="card"
        @click="goDetail(c.id)"
      >
        <div class="card-head">
          <h3 class="card-name">{{ c.name }}</h3>
          <span v-if="c.is_member" class="tag tag-member">已加入</span>
          <span v-else-if="c.join_setting === 1" class="tag">审核制</span>
          <span v-else-if="c.join_setting === 2" class="tag">邀请制</span>
        </div>
        <p class="card-profile">{{ c.profile || '暂无简介' }}</p>
        <div class="card-meta">
          <span>{{ c.member_count }} 成员</span>
          <span>#{{ c.number }}</span>
        </div>
      </article>
    </div>

    <!-- 创建频道弹层 -->
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3 class="dialog-title">创建频道</h3>
        <form @submit.prevent="onCreate">
          <label class="field">
            <span class="field-label">频道名称</span>
            <input v-model.trim="form.name" class="input" type="text" maxlength="64" required />
          </label>
          <label class="field">
            <span class="field-label">简介</span>
            <textarea v-model.trim="form.profile" class="input textarea" rows="3" maxlength="255"></textarea>
          </label>
          <label class="field">
            <span class="field-label">加入方式</span>
            <select v-model.number="form.join_setting" class="input">
              <option :value="0">自由加入</option>
              <option :value="1">审核加入</option>
              <option :value="2">邀请制</option>
            </select>
          </label>
          <p v-if="error" class="error">{{ error }}</p>
          <div class="dialog-actions">
            <button type="button" class="btn-ghost" @click="showCreate = false">取消</button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? '创建中…' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { communityApi, type Community } from '@/api/community'

const router = useRouter()
const communities = ref<Community[]>([])
const loading = ref(true)
const showCreate = ref(false)
const creating = ref(false)
const error = ref('')
const form = reactive({ name: '', profile: '', join_setting: 0 })

onMounted(async () => {
  try {
    const data = await communityApi.list(1, 50)
    communities.value = data.items
  } finally {
    loading.value = false
  }
})

async function onCreate() {
  if (creating.value) return
  creating.value = true
  error.value = ''
  try {
    const c = await communityApi.create({ ...form })
    showCreate.value = false
    router.push(`/c/${c.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    creating.value = false
  }
}

function goDetail(id: number) {
  router.push(`/c/${id}`)
}
</script>

<style scoped>
.discover {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--sp-4) var(--sp-6);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--nav-height);
  border-bottom: 1px solid var(--border);
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.btn-sm {
  height: 32px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-caption);
}
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.empty {
  padding: var(--sp-6) 0;
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
  cursor: pointer;
  transition: border-color 0.15s;
}
.card:hover {
  border-color: var(--brand);
}
.card-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.card-name {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
}
.tag {
  font-size: var(--fs-caption);
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}
.tag-member {
  color: var(--brand);
  border-color: var(--brand-weak);
  background: var(--brand-weak);
}
.card-profile {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-body);
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(31, 35, 41, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
}
.dialog {
  width: 100%;
  max-width: 380px;
  background: var(--bg-card);
  border-radius: var(--radius-overlay);
  box-shadow: var(--shadow-overlay);
  padding: var(--sp-5) var(--sp-4);
}
.dialog-title {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-title);
  font-weight: 600;
}
.dialog form {
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
.textarea {
  height: auto;
  padding: var(--sp-2) var(--sp-3);
  resize: vertical;
  font-family: inherit;
}
.input:focus {
  border-color: var(--brand);
}
.error {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--danger);
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
.btn-primary {
  height: 40px;
  padding: 0 var(--sp-4);
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
.btn-ghost {
  height: 40px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  cursor: pointer;
}
</style>
