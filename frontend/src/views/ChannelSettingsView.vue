<template>
  <main class="cset">
    <header class="page-header">
      <router-link to="/" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回主页
      </router-link>
      <h1 class="page-title">{{ community?.name || '频道设置' }}</h1>
    </header>

    <div v-if="loading" class="state"><t-skeleton :row="5" animation="gradient" /></div>
    <ErrorState v-else-if="loadError" :text="loadError" @retry="init" />

    <template v-else>
      <t-tabs v-model="tab" class="tabs">
        <!-- 频道基本资料 -->
        <t-tab-panel value="basic" label="基本资料">
          <div class="panel">
            <div class="row">
              <span class="label">频道头像</span>
              <img v-if="community?.avatar_url" :src="community.avatar_url" class="avatar" alt="" />
              <label class="btn-ghost">
                上传图片
                <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden @change="onAvatarUpload" />
              </label>
            </div>
            <div class="row">
              <span class="label">频道名称</span>
              <t-input v-model.trim="form.name" class="input" maxlength="64" placeholder="频道名称" />
            </div>
            <div class="row">
              <span class="label">频道简介</span>
              <t-textarea v-model.trim="form.profile" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="255" class="input" />
            </div>
            <div class="row">
              <t-button theme="primary" size="small" :loading="saving" @click="saveBasic">保存资料</t-button>
              <span v-if="saveMsg" class="save-msg">{{ saveMsg }}</span>
            </div>

            <div class="divider"></div>
            <!-- 分享二维码 -->
            <div class="row">
              <span class="label">分享二维码</span>
              <img v-if="qrUrl" :src="qrUrl" class="qr" alt="频道分享二维码" />
              <span v-else class="muted">加载中…</span>
              <span class="hint">扫码打开频道分享页（仅需登录，未加入也可打开）</span>
            </div>
          </div>
        </t-tab-panel>

        <!-- 我的资料 -->
        <t-tab-panel value="me" label="我的资料">
          <div class="panel">
            <div class="row">
              <span class="label">频道内昵称</span>
              <t-input v-model.trim="myMember.nickname" class="input" maxlength="64" placeholder="在频道中显示的昵称" />
              <t-button variant="outline" size="small" @click="saveMyNickname">保存</t-button>
            </div>
            <p class="row-note">频道内昵称仅在本频道显示；全局昵称/头像在个人中心修改。</p>
          </div>
        </t-tab-panel>

        <!-- 我的等级 -->
        <t-tab-panel value="level" label="我的等级">
          <div class="panel">
            <div class="level-card">
              <span class="level-num">Lv.{{ myMember.level }}</span>
              <div class="level-info">
                <span class="level-role">{{ myMember.is_owner ? '频道主' : myMember.role_name || memberTypeName }}</span>
                <span class="level-join">加入于 {{ myMember.join_time ? formatTime(myMember.join_time) : '—' }}</span>
              </div>
            </div>
            <p class="hint">活跃等级随互动增长；等级达标可自动获得对应身份组（如频道配置了等级身份）。</p>
          </div>
        </t-tab-panel>

        <!-- 频道消息 -->
        <t-tab-panel value="msgs" label="频道消息">
          <div class="panel">
            <div class="toolbar">
              <span v-if="msgTotal" class="count">共 {{ msgTotal }} 条（已加载 {{ msgs.length }}）</span>
              <span v-else class="count">加载中…</span>
            </div>
            <div v-if="msgs.length" class="msg-list">
              <div v-for="n in msgs" :key="n.id" class="msg-item" @click="gotoMsg(n)">
                <span class="msg-dot" :class="{ unread: !n.is_read }" />
                <div class="msg-body">
                  <div class="msg-row">
                    <span class="msg-type">{{ typeLabel(n.type) }}</span>
                    <span class="msg-time">{{ timeAgo(n.created_at) }}</span>
                  </div>
                  <p class="msg-title">{{ n.title }}</p>
                  <p v-if="n.summary" class="msg-summary">{{ n.summary }}</p>
                </div>
              </div>
            </div>
            <t-empty v-else-if="msgLoaded && msgs.length === 0" description="本频道暂无消息" />
            <t-button v-if="msgs.length < msgTotal" variant="outline" block class="load-more" @click="loadMoreMsgs">
              {{ msgLoading ? '加载中…' : `加载更多（${msgs.length}/${msgTotal}）` }}
            </t-button>
          </div>
        </t-tab-panel>

        <!-- 消息接收类型 -->
        <t-tab-panel value="notify" label="消息接收类型">
          <div class="panel">
            <div v-for="s in settingRows" :key="s.key" class="switch-row">
              <div class="switch-side">
                <span class="switch-label">{{ s.label }}</span>
                <span class="switch-desc">{{ s.desc }}</span>
              </div>
              <t-switch :value="!!notifyForm[s.key]" size="small" @change="(v: boolean) => onToggleNotify(s.key, v)" />
            </div>
            <p class="hint">本频道的消息接收类型；未开启的类型将不在「频道消息」展示。系统通知始终接收。</p>
          </div>
        </t-tab-panel>

        <!-- 频道管理（仅频道主/有权限） -->
        <t-tab-panel v-if="canManage" value="manage" label="频道管理">
          <div class="panel">
            <p class="hint">板块、成员、身份组、操作日志、帖子等管理能力，请前往频道管理后台。</p>
            <t-button theme="primary" @click="router.push(`/c/${cid}/admin`)">进入管理后台</t-button>
          </div>
        </t-tab-panel>

        <!-- 运营中心（仅频道主/有成员数据权限） -->
        <t-tab-panel v-if="canOps" value="ops" label="运营中心">
          <div class="panel">
            <p class="hint">查看本频道的昨日数据、用户数据、内容分析与排名。</p>
            <t-button theme="primary" @click="router.push(`/c/${cid}/ops`)">进入运营中心</t-button>
          </div>
        </t-tab-panel>
      </t-tabs>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Community, type MyMemberInfo } from '@/api/community'
import { notificationApi, type NotificationItem, type NotifySettings } from '@/api/notification'
import { request } from '@/api/http'
import { toast } from '@/utils/toast'
import { errMessage } from '@/utils/error'
import { formatTime, timeAgo } from '@/utils/time'
import ErrorState from '@/components/ErrorState.vue'

defineOptions({ name: 'ChannelSettingsView' })

const route = useRoute()
const router = useRouter()
const cid = computed(() => Number(route.params.id))

const validTabs = ['basic', 'me', 'level', 'msgs', 'notify', 'manage', 'ops'] as const
type Tab = typeof validTabs[number]
const qtab = String(route.query.tab || 'basic')
const tab = ref<Tab>((validTabs.includes(qtab as Tab) ? qtab : 'basic') as Tab)
const loading = ref(true)
const loadError = ref('')
const community = ref<Community | null>(null)
const form = reactive({ name: '', profile: '' })
const saving = ref(false)
const saveMsg = ref('')
const qrUrl = ref('')

// 我的资料 / 等级
const myMember = ref<MyMemberInfo>({ member_id: 0, level: 1, member_type: 2, nickname: '', role_id: null, role_name: '', role_color: '', is_owner: false, join_time: null })

// 频道消息
const msgs = ref<NotificationItem[]>([])
const msgPage = ref(0)
const msgTotal = ref(0)
const msgLoading = ref(false)
const msgLoaded = ref(false)

// 消息接收类型
const notifyForm = reactive<Record<string, boolean>>({})
const settingRows: Array<{ key: keyof NotifySettings; label: string; desc: string }> = [
  { key: 'mention', label: '@ 提及我', desc: '有人在这个频道里 @ 我时提醒' },
  { key: 'like', label: '收到的赞', desc: '本频道我的内容被点赞时提醒' },
  { key: 'comment', label: '评论与回复', desc: '本频道有人评论我时提醒' },
  { key: 'follow', label: '新关注', desc: '有人关注我时提醒' },
  { key: 'review', label: '审核结果', desc: '本频道我的内容审核结果提醒' },
  { key: 'report', label: '举报反馈', desc: '本频道我提交的举报处理结果提醒' },
]

const memberTypeName = computed(() => myMember.value.member_type === 0 ? '频道主' : myMember.value.member_type === 1 ? '管理员' : '成员')
const canManage = computed(() => !!community.value?.my_perms.includes('super') || !!community.value?.my_perms.includes('role_manage') || !!community.value?.my_perms.includes('member_manage'))
const canOps = computed(() => !!community.value?.is_owner || !!community.value?.my_perms.includes('member_manage') || !!community.value?.my_perms.includes('moderate'))

const typeLabels: Record<string, string> = {
  mention: '@提及', like: '点赞', comment: '评论', follow: '关注',
  system: '系统', review_result: '审核', report_feedback: '举报',
}
function typeLabel(t: string) { return typeLabels[t] || t }

async function init() {
  loading.value = true
  loadError.value = ''
  try {
    const c = await communityApi.get(cid.value)
    community.value = c
    form.name = c.name
    form.profile = c.profile
    loadQr()
    loadMyMember()
    loadNotifySettings()
    loadMsgs(1)
  } catch (e) {
    loadError.value = errMessage(e, '频道设置加载失败')
  } finally {
    loading.value = false
  }
}

async function loadQr() {
  try {
    const res = await communityApi.qr(cid.value)
    if (!res.ok) return
    const blob = await res.blob()
    qrUrl.value = URL.createObjectURL(blob)
  } catch { /* ignore */ }
}

async function loadMyMember() {
  try {
    myMember.value = await communityApi.myMember(cid.value)
  } catch { /* 非成员/游客：保持默认 */ }
}

async function saveMyNickname() {
  try {
    await communityApi.updateMyMember(cid.value, myMember.value.nickname)
    toast('昵称已更新', 'success')
  } catch (e) {
    toast(errMessage(e, '保存失败'), 'error')
  }
}

async function loadNotifySettings() {
  try {
    const s = await notificationApi.getCommunitySettings(cid.value)
    for (const row of settingRows) notifyForm[row.key] = !!s[row.key]
  } catch { /* ignore */ }
}

async function onToggleNotify(key: keyof NotifySettings, v: boolean) {
  try {
    await notificationApi.updateCommunitySettings(cid.value, { [key]: v } as Partial<NotifySettings>)
    notifyForm[key] = v
  } catch (e) {
    toast(errMessage(e, '保存失败'), 'error')
  }
}

async function loadMsgs(page: number, append = false) {
  if (msgLoading.value) return
  msgLoading.value = true
  try {
    const data = await notificationApi.communityList(cid.value, page, 20)
    msgs.value = append ? [...msgs.value, ...data.items] : data.items
    msgPage.value = page
    msgTotal.value = data.total
    msgLoaded.value = true
  } catch { /* ignore */ } finally {
    msgLoading.value = false
  }
}
function loadMoreMsgs() { loadMsgs(msgPage.value + 1, true) }

function gotoMsg(n: NotificationItem) {
  if (!n.is_read) notificationApi.read(n.id).catch(() => {})
  let path = ''
  if (n.type === 'comment' || n.type === 'like' || n.type === 'mention') {
    if (n.ref_id) path = `/p/${n.ref_id}`
  } else if (n.type === 'system') {
    if (n.ref_id) path = `/c/${n.ref_id}`
  } else {
    if (n.ref_id) path = `/c/${n.ref_id}`
  }
  if (path) router.push(path)
}

async function saveBasic() {
  saving.value = true
  saveMsg.value = ''
  try {
    await communityApi.update(cid.value, { name: form.name, profile: form.profile })
    saveMsg.value = '资料已保存'
    toast('资料已保存', 'success')
  } catch (e) {
    saveMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function onAvatarUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    const up = await request<{ url: string }>({ url: '/uploads', method: 'POST', data: fd })
    await communityApi.update(cid.value, { avatar_url: up.url })
    community.value = await communityApi.get(cid.value)
    toast('头像已更新', 'success')
  } catch (err) {
    toast(err instanceof Error ? err.message : '上传失败', 'error')
  }
}

onMounted(init)
</script>

<style scoped>
.cset {
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
  text-decoration: none;
}
.back:hover { color: var(--brand); }
.back-icon { width: 16px; height: 16px; }
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.state { padding: 48px 0; text-align: center; color: var(--text-3); }
.tabs { margin-top: var(--sp-3); }
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  flex-wrap: wrap;
}
.label {
  width: 88px;
  font-size: var(--fs-caption);
  color: var(--text-2);
  flex-shrink: 0;
}
.input { flex: 1; min-width: 160px; }
.avatar {
  width: 56px; height: 56px; border-radius: var(--radius-control);
  object-fit: cover; border: 1px solid var(--border);
}
.qr { width: 140px; height: 140px; border: 1px solid var(--border); border-radius: 8px; }
.hint { width: 100%; font-size: var(--fs-caption); color: var(--text-3); }
.muted { font-size: var(--fs-caption); color: var(--text-3); }
.save-msg { font-size: var(--fs-caption); color: var(--success); }
.divider { height: 1px; background: var(--border); margin: var(--sp-3) 0; }
.btn-ghost {
  display: inline-flex; align-items: center; height: 32px; padding: 0 var(--sp-3);
  border: 1px solid var(--td-component-border); border-radius: var(--td-radius-default);
  background: var(--td-bg-color-container); color: var(--td-text-color-primary);
  font-size: var(--fs-caption); cursor: pointer;
}
.btn-ghost:hover { border-color: var(--td-brand-color); color: var(--td-brand-color); }
.row-note { margin: var(--sp-1) 0 0 88px; font-size: var(--fs-caption); color: var(--text-3); }
.level-card {
  display: flex; align-items: center; gap: var(--sp-4);
  padding: var(--sp-4); background: var(--surface);
  border: 1px solid var(--border-soft); border-radius: var(--radius-card);
}
.level-num { font-size: 32px; font-weight: 700; color: var(--brand); }
.level-info { display: flex; flex-direction: column; gap: 4px; }
.level-role { font-weight: 600; }
.level-join { font-size: var(--fs-caption); color: var(--text-3); }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--sp-2); }
.count { font-size: var(--fs-caption); color: var(--text-3); }
.msg-list { display: flex; flex-direction: column; }
.msg-item {
  display: flex; gap: var(--sp-2); padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border); cursor: pointer;
}
.msg-item:last-child { border-bottom: none; }
.msg-dot { width: 8px; height: 8px; border-radius: 50%; background: transparent; flex-shrink: 0; margin-top: 6px; }
.msg-dot.unread { background: var(--danger); }
.msg-body { flex: 1; min-width: 0; }
.msg-row { display: flex; align-items: baseline; gap: 8px; }
.msg-type { font-size: var(--fs-caption); color: var(--brand); background: var(--brand-weak); border-radius: 4px; padding: 0 6px; }
.msg-time { margin-left: auto; font-size: var(--fs-caption); color: var(--text-3); }
.msg-title { margin: 2px 0 0; font-size: var(--fs-body); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-summary { margin: 2px 0 0; font-size: var(--fs-caption); color: var(--text-2); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.load-more { margin-top: var(--sp-2); }
.switch-row {
  display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3);
  padding: var(--sp-3) 0; border-bottom: 1px solid var(--border);
}
.switch-row:last-child { border-bottom: none; }
.switch-side { min-width: 0; }
.switch-label { font-size: var(--fs-body); }
.switch-desc { display: block; margin-top: 2px; font-size: var(--fs-caption); color: var(--text-3); }
</style>