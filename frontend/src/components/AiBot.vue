<template>
  <div class="ai-bot">
    <!-- 浮动入口（登录后显示） -->
    <button v-if="authed && !open" class="ai-bot-fab" title="AI 问答助手" @click="open = true">
      🤖
    </button>

    <!-- 对话框 -->
    <div v-if="open" class="ai-bot-panel">
      <header class="ai-bot-head">
        <span>🤖 频道问答助手</span>
        <button class="ai-bot-close" title="关闭" @click="open = false">✕</button>
      </header>
      <div ref="bodyEl" class="ai-bot-body">
        <p class="ai-bot-tip">基于频道内帖子内容回答，支持引用跳转。</p>
        <div v-for="(m, i) in messages" :key="i" class="ai-msg" :class="m.role">
          <div class="ai-msg-bubble">
            <p class="ai-msg-text">{{ m.text }}<span v-if="m.streaming" class="ai-cursor">▍</span></p>
            <div v-if="m.refs?.length" class="ai-msg-refs">
              <a v-for="r in m.refs" :key="r.id" :href="`/p/${r.id}`" @click.prevent="gotoPost(r.id)">
                引用：《{{ r.title.slice(0, 20) }}》
              </a>
            </div>
          </div>
        </div>
      </div>
      <footer class="ai-bot-foot">
        <t-input v-model="question" placeholder="问点频道里的事…" size="small" @enter="ask" />
        <t-button theme="primary" size="small" :loading="busy" @click="ask">发送</t-button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { tokenStore } from '@/api/http'
import { request } from '@/api/http'

interface QaMsg {
  role: 'user' | 'bot'
  text: string
  refs?: Array<{ id: number; title: string }>
  streaming?: boolean
}

const router = useRouter()
const authed = computed(() => !!tokenStore.access)
const open = ref(false)
const busy = ref(false)
const question = ref('')
const messages = ref<QaMsg[]>([])
const bodyEl = ref<HTMLElement | null>(null)

watch(open, (v) => {
  if (v) {
    messages.value = []
    question.value = ''
  }
})

watch(messages, async () => {
  await nextTick()
  if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
})

async function ask() {
  const q = question.value.trim()
  if (!q || busy.value) return
  messages.value.push({ role: 'user', text: q })
  question.value = ''
  const bot: QaMsg = { role: 'bot', text: '', streaming: true }
  messages.value.push(bot)
  busy.value = true
  try {
    const data = await request<{ answer: string; references: Array<{ id: number; title: string }> }>({
      url: '/ai/qa',
      method: 'POST',
      data: { question: q },
    })
    bot.text = data.answer
    bot.refs = data.references
  } catch (e) {
    bot.text = (e as Error).message || '问答失败，请稍后再试'
  } finally {
    bot.streaming = false
    busy.value = false
  }
}

function gotoPost(id: number) {
  open.value = false
  router.push(`/p/${id}`)
}
</script>

<style scoped>
.ai-bot-fab {
  position: fixed;
  right: 16px;
  bottom: calc(var(--tabbar-height) + 16px);
  width: 48px;
  height: 48px;
  border: none;
  border-radius: 50%;
  background: var(--brand);
  font-size: 22px;
  cursor: pointer;
  z-index: 90;
  box-shadow: var(--shadow-overlay);
}
.ai-bot-panel {
  position: fixed;
  right: 16px;
  bottom: calc(var(--tabbar-height) + 16px);
  width: min(340px, calc(100vw - 32px));
  height: 460px;
  max-height: calc(100vh - 120px);
  background: var(--bg-card);
  border-radius: var(--radius-overlay);
  box-shadow: var(--shadow-overlay);
  display: flex;
  flex-direction: column;
  z-index: 91;
  overflow: hidden;
}
.ai-bot-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  font-weight: 600;
}
.ai-bot-close {
  border: none;
  background: transparent;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.ai-bot-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  background: var(--bg-page);
}
.ai-bot-tip {
  margin: 0 0 10px;
  font-size: var(--fs-caption);
  color: var(--text-3);
  text-align: center;
}
.ai-msg {
  display: flex;
  margin-bottom: 10px;
}
.ai-msg.user {
  justify-content: flex-end;
}
.ai-msg-bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 12px;
  background: var(--bg-card);
  font-size: var(--fs-body);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.ai-msg.user .ai-msg-bubble {
  background: var(--brand);
  color: #fff;
}
.ai-msg-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.ai-msg-refs {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ai-msg-refs a {
  font-size: var(--fs-caption);
  color: var(--brand);
}
.ai-msg.user .ai-msg-refs a {
  color: #fff;
  opacity: 0.9;
}
.ai-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: currentColor;
  vertical-align: -2px;
  animation: blink 0.8s steps(1) infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.ai-bot-foot {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid var(--border);
}
</style>
