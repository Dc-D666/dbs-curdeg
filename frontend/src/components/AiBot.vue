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
        <div class="ai-head-ops">
          <button class="ai-bot-clear" title="清空会话" :disabled="busy" @click="clearSession">清空</button>
          <button class="ai-bot-close" title="关闭" @click="open = false">✕</button>
        </div>
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
        <!-- 流式回答中给出「停止」入口：此前 busy 锁最长 60s，用户只能干等 -->
        <t-button v-if="busy" theme="danger" variant="outline" size="small" @click="stop">停止</t-button>
        <t-button v-else theme="primary" size="small" :disabled="!question.trim()" @click="ask">发送</t-button>
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
import { useAuthStore } from '@/stores/auth'

interface QaMsg {
  role: 'user' | 'bot'
  text: string
  status?: string
  refs?: Array<{ id: number; title: string }>
  streaming?: boolean
}

const router = useRouter()
const auth = useAuthStore()
const authed = computed(() => !!tokenStore.access)
const open = ref(false)
const busy = ref(false)
const question = ref('')
const messages = ref<QaMsg[]>([])
const bodyEl = ref<HTMLElement | null>(null)
// 流式请求的中断控制器（「停止生成」）
let controller: AbortController | null = null

// ---------- 会话持久化：关闭面板不再清空历史 ----------

const SESSION_TTL = 24 * 3600 * 1000
const sessionKey = computed(() => `ai_bot_session:${auth.user?.id ?? 0}`)

function persist() {
  try {
    // 空会话直接清键：否则清空后防抖的 persist 会把 [] 又写回去
    if (messages.value.length === 0) {
      localStorage.removeItem(sessionKey.value)
      return
    }
    // 只存可见内容，不存 streaming 等瞬时状态；最多留最近 50 条
    const data = messages.value.slice(-50).map(({ role, text, status, refs }) => ({
      role,
      text,
      status,
      refs,
    }))
    localStorage.setItem(sessionKey.value, JSON.stringify({ ts: Date.now(), data }))
  } catch {
    // localStorage 不可用（隐私模式/超限）：静默忽略，不影响对话
  }
}

function restore() {
  try {
    const raw = localStorage.getItem(sessionKey.value)
    if (!raw) return
    const parsed = JSON.parse(raw) as { ts?: number; data?: QaMsg[] }
    if (!Array.isArray(parsed.data)) return
    // 超过 24h 的会话不再恢复，避免上下文过期
    if (parsed.ts && Date.now() - parsed.ts > SESSION_TTL) {
      localStorage.removeItem(sessionKey.value)
      return
    }
    messages.value = parsed.data
      .filter((m) => m && (m.role === 'user' || m.role === 'bot'))
      .map((m) => ({ role: m.role, text: m.text || '', status: m.status, refs: m.refs }))
  } catch {
    /* 坏数据：忽略，按空会话处理 */
  }
}

let saveTimer: number | undefined
watch(
  messages,
  () => {
    window.clearTimeout(saveTimer)
    saveTimer = window.setTimeout(persist, 400) // 流式输出很密集，防抖落盘
  },
  { deep: true },
)

watch(open, (v) => {
  if (v) {
    if (messages.value.length === 0) restore()
    return
  }
  window.clearTimeout(saveTimer)
  persist()
})

// 换账号时不能串会话
watch(sessionKey, () => {
  messages.value = []
  if (open.value) restore()
})

function clearSession() {
  messages.value = []
  try {
    localStorage.removeItem(sessionKey.value)
  } catch {
    /* ignore */
  }
}

function stop() {
  controller?.abort()
}

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
  controller = new AbortController()
  try {
    await streamPost(
      '/api/v1/ai/qa/stream',
      { question: q },
      (delta) => {
        bot.text += delta
      },
      {
        signal: controller.signal,
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
    if ((e as Error)?.name === 'AbortError') {
      // 用户主动停止：保留已生成的部分，不弹错误
      if (!bot.text) bot.text = '（已停止生成）'
      return
    }
    if (bot.text) return // 已输出部分内容则保留，不做整段覆盖
    bot.text = (e as Error).message || '问答失败，请稍后再试'
  } finally {
    bot.streaming = false
    busy.value = false
    controller = null
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
.ai-head-ops {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-bot-clear {
  border: none;
  background: transparent;
  color: #fff;
  font-size: 12px;
  opacity: 0.85;
  cursor: pointer;
  padding: 2px 4px;
}
.ai-bot-clear:hover {
  opacity: 1;
}
.ai-bot-clear:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
