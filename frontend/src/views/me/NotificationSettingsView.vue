<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">通知设置</h1>
    </header>

    <!-- 加载失败不能静默吞掉：所有开关会默认显示为「关」，用户会误以为自己关了通知 -->
    <ErrorState v-if="loadError" :text="loadError" @retry="loadSettings" />
    <template v-else>
      <section class="panel">
        <div v-for="s in settingRows" :key="s.key" class="switch-row">
          <div class="switch-side">
            <span class="switch-label">{{ s.label }}</span>
            <span class="switch-desc">{{ s.desc }}</span>
          </div>
          <t-switch
            :value="!!(form[s.key])"
            size="small"
            :disabled="loading"
            @change="(v: boolean) => onToggle(s.key, v)"
          />
        </div>
        <p v-if="msg" class="msg" :class="{ error }">{{ msg }}</p>
      </section>

      <p v-if="loading" class="hint">设置加载中…</p>
      <p v-else class="hint">关闭后你将不再收到对应类型的通知（系统消息除外）。</p>
    </template>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { notificationApi, type NotifySettings } from '@/api/notification'
import ErrorState from '@/components/ErrorState.vue'
import { errMessage } from '@/utils/error'

const settingRows: Array<{ key: keyof NotifySettings; label: string; desc: string }> = [
  { key: 'mention', label: '@ 提及我', desc: '有人在我的帖子或评论里 @ 我时提醒' },
  { key: 'like', label: '收到的赞', desc: '我的帖子或评论被点赞时提醒' },
  { key: 'comment', label: '评论与回复', desc: '有人评论我的帖子或回复我时提醒' },
  { key: 'follow', label: '新关注', desc: '有人关注我时提醒' },
  { key: 'system', label: '系统通知', desc: '平台与运营相关的系统消息' },
  { key: 'review', label: '审核结果', desc: '我的内容审核通过或驳回时提醒' },
  { key: 'report', label: '举报反馈', desc: '我提交的举报有处理结果时提醒' },
]

const form = reactive<Record<string, boolean>>({})
const msg = ref('')
const error = ref(false)
const loading = ref(true)
const loadError = ref('')

async function loadSettings() {
  loading.value = true
  loadError.value = ''
  try {
    const settings = await notificationApi.getSettings()
    for (const row of settingRows) form[row.key] = !!settings[row.key]
  } catch (e) {
    loadError.value = errMessage(e, '通知设置加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadSettings)

async function onToggle(key: keyof NotifySettings, v: boolean) {
  msg.value = ''
  error.value = false
  try {
    await notificationApi.updateSettings({ [key]: v } as Partial<NotifySettings>)
    form[key] = v
    msg.value = '设置已保存'
  } catch (e) {
    error.value = true
    msg.value = e instanceof Error ? e.message : '保存失败'
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
  padding: var(--sp-2) var(--sp-4);
}
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.switch-row:last-child {
  border-bottom: none;
}
.switch-side {
  min-width: 0;
}
.switch-label {
  font-size: var(--fs-body);
  color: var(--td-text-color-primary);
}
.switch-desc {
  display: block;
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.msg {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-success-color);
}
.msg.error {
  color: var(--td-error-color);
}
.hint {
  margin: var(--sp-3) var(--sp-2) 0;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
</style>