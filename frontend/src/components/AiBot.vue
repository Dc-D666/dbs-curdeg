<template>
  <div class="ai-bot">
    <!-- 浮动入口（登录后显示） -->
    <button v-if="authed && !open" class="ai-bot-fab" title="AI 问答助手" @click="open = true">
      <RobotIcon class="ai-fab-icon" />
    </button>

    <!-- 对话框 -->
    <div v-if="open" class="ai-bot-panel">
      <header class="ai-bot-head">
        <span><RobotIcon class="ai-head-icon" /> 频道问答助手</span>
        <button class="ai-bot-close" title="关闭" @click="open = false">✕</button>
      </header>
      <div ref="bodyEl" class="ai-bot-body">
        <p class="ai-bot-tip">基于频道内帖子内容回答，支持引用跳转。</p>
        <div v-for="(m, i) in messages" :key="i" class="ai-msg" :class="m.role">
          <div class="ai-msg-bubble">
            <p v-if="m.status" class="ai-msg-status">{{ m.status }}<span v-if="m.streaming" class="ai-cursor">▍</span></p>
            <p class="ai-msg-text">{{ m.text }}<span v-if="m.text && m.streaming" class="ai-cursor">▍</span></p>
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
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { RobotIcon } from 'tdesign-icons-vue-next'
import { tokenStore } from '@/api/http'
import { streamPost } from '@/utils/sse'

interface QaMsg {
  role: 'user' | 'bot'
  text: string
  status?: string
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
  // 必须用 reactive 持有 proxy：push 进 ref 数组后，模板读到的是响应式代理，
  // 若直接用普通对象再写 text/status 会绕过响应式触发，导致流式/状态不渲染。
  const bot = reactive<QaMsg>({ role: 'bot', text: '', streaming: true })
  messages.value.push(bot)
  busy.value = true
  try {
    await streamPost(
      '/api/v1/ai/qa/stream',
      { question: q },
      (delta) => {
        bot.text += delta
      },
      {
        onEvent(event) {
          if (event.type === 'error') {
            bot.text = event.message || '问答失败，请稍后再试'
            return
          }
          if (event.type === 'progress') {
            if (event.stage === 'search') {
              bot.status = '正在检索帖子…'
            } else if (event.stage === 'embed') {
              bot.status = `正在为帖子构建语义向量 ${event.done ?? 0}/${event.total ?? 0}…`
            } else if (event.stage === 'answer') {
              bot.status = '正在生成回答…'
            }
            return
          }
          if (event.type === 'answer') {
            bot.status = undefined
          }
          if (event.type === 'refs' && event.references?.length) {
            bot.refs = event.references
            bot.status = undefined
          }
        },
      },
    )
  } catch (e) {
    if (bot.text) return // 已输出部分内容则保留，不做整段覆盖
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.ai-fab-icon {
  width: 26px;
  height: 26px;
  color: #fff;
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
.ai-head-icon {
  width: 16px;
  height: 16px;
  vertical-align: -2px;
  margin-right: 4px;
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
.ai-msg-status {
  margin: 0 0 2px;
  font-size: var(--fs-caption);
  color: var(--text-3);
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
