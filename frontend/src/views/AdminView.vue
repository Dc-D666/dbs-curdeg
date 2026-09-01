<template>
  <main class="admin">
    <header class="page-header">
      <router-link :to="`/c/${cid}`" class="back">
        <ArrowLeftIcon class="back-icon" /> {{ community?.name || '频道' }}
      </router-link>
      <h1 class="page-title">管理后台</h1>
    </header>

    <!-- 加载失败：无权限/频道不存在给明确错误页（不再只底部一行小字），网络故障可重试 -->
    <ErrorState
      v-if="loadFailed"
      :text="loadError"
      :retryable="!notFound && !noPermission"
      @retry="init"
    >
      <router-link :to="`/c/${cid}`" class="state-link">返回频道</router-link>
    </ErrorState>

    <t-tabs v-else v-model="tab" class="tabs">
      <!-- 成员管理 -->
      <t-tab-panel value="members" label="成员管理">
        <div class="panel">
          <div class="members-toolbar">
            <t-input
              v-model="memberKeyword"
              class="member-search"
              placeholder="按用户名 / 昵称搜索成员"
              clearable
              @enter="onMemberSearch"
              @clear="onMemberSearch"
            />
            <t-button variant="outline" size="small" :loading="membersLoading" @click="onMemberSearch">搜索</t-button>
          </div>
          <div class="member-row" v-for="m in members" :key="m.id">            <t-avatar :image="m.avatar_url || undefined" size="36px">
              <template #icon>{{ (m.user_nickname || m.nickname).slice(0, 1) }}</template>
            </t-avatar>
            <div class="m-info">
              <div class="m-name">
                {{ m.user_nickname || m.nickname }}
                <t-tag v-if="m.role_name" size="small" variant="light" class="m-role">{{ m.role_name }}</t-tag>
                <t-tag v-else size="small" variant="outline" class="m-role">{{ memberTypeName(m.member_type) }}</t-tag>
                <t-tag size="small" variant="light" theme="warning" class="m-lv">Lv.{{ m.level }}</t-tag>
              </div>
              <div class="m-sub">
                <span v-if="m.shutup_expire_at" class="m-muted"><SoundMute1Icon class="m-sub-icon" /> 禁言至 {{ formatTime(m.shutup_expire_at) }}</span>
                <span v-if="m.is_blocked" class="m-blocked"><ErrorCircleIcon class="m-sub-icon" /> 已移出</span>
                <span v-else class="m-muted">@{{ m.username }}</span>
              </div>
            </div>
            <div v-if="canManage(m)" class="m-actions">
              <t-select
                v-model="roleSel[m.user_id]"
                class="select-sm"
                :disabled="m.is_blocked"
                size="small"
                @change="onAssign(m)"
              >
                <t-option :value="0" label="默认身份" />
                <t-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" />
              </t-select>
              <t-button variant="outline" size="small" :disabled="m.is_blocked" @click="openShutup(m)">禁言</t-button>
              <t-button v-if="m.shutup_expire_at" variant="outline" size="small" :disabled="m.is_blocked" @click="onUnshutup(m)">解禁</t-button>
              <t-button variant="outline" size="small" theme="danger" :disabled="m.is_blocked" @click="onKick(m)">踢出</t-button>
              <t-button v-if="m.is_blocked" variant="outline" size="small" @click="onUnblock(m)">解除拉黑</t-button>
              <t-button v-else variant="outline" size="small" theme="danger" @click="onBlock(m)">拉黑</t-button>
            </div>
          </div>
          <t-empty v-if="members.length === 0" description="暂无成员" />
          <t-button
            v-if="membersHasMore"
            variant="outline"
            block
            class="load-more-members"
            @click="loadMoreMembers()"
          >加载更多成员（{{ members.length }}/{{ membersTotal }}）</t-button>
        </div>
      </t-tab-panel>

      <!-- 身份组 -->
      <t-tab-panel value="roles" label="身份组">
        <div class="panel">
          <div class="role-form">
            <t-input v-model.trim="roleForm.name" class="role-name-input" placeholder="身份组名称" maxlength="32" clearable />
            <t-color-picker
              v-model="roleForm.color"
              :color-modes="['monochrome']"
              :enable-alpha="false"
              format="HEX"
              class="color-picker"
            />
            <t-checkbox v-model="roleForm.is_level_role" class="level-role-check">等级身份</t-checkbox>
            <t-input-number
              v-if="roleForm.is_level_role"
              v-model="roleForm.level"
              class="level-input"
              :min="1"
              :max="9999"
              theme="column"
              placeholder="门槛等级"
            />
            <t-button theme="primary" size="small" :loading="roleSaving" :disabled="!roleForm.name" @click="onCreateRole">
              {{ roleSaving ? '创建中…' : '新建身份组' }}
            </t-button>
          </div>
          <p class="role-form-hint">排序在前（权重高）的身份组可管理排序在后的身份组；等级身份按成员活跃等级达标自动授予</p>
          <div class="role-card" v-for="(r, i) in roles" :key="r.id">
            <div class="role-head">
              <span class="role-dot" :style="{ background: r.color }"></span>
              <span class="role-name">{{ r.name }}</span>
              <t-tag v-if="r.is_default" size="small" variant="outline">默认</t-tag>
              <t-tag v-if="r.is_level_role" size="small" variant="light" theme="warning">等级 Lv.{{ r.level }}+</t-tag>
              <span class="role-id">第 {{ i + 1 }} 位</span>
            </div>
            <div class="perms">
              <t-checkbox
                v-for="p in PERM_ITEMS"
                :key="p.key"
                :checked="r.perms.includes(p.key)"
                :disabled="!canEditRole(r)"
                @change="(v: boolean) => onTogglePerm(r, p.key, v)"
              >
                {{ p.label }}
              </t-checkbox>
            </div>
            <div class="role-ops">
              <t-button
                v-if="canEditRole(r)"
                variant="outline"
                size="small"
                :disabled="i === 0"
                @click="onMoveRole(r, 'up')"
              >↑ 上移</t-button>
              <t-button
                v-if="canEditRole(r)"
                variant="outline"
                size="small"
                :disabled="i === roles.length - 1"
                @click="onMoveRole(r, 'down')"
              >↓ 下移</t-button>
              <t-checkbox
                v-if="canEditRole(r)"
                v-model="levelRoleMap[r.id]"
                class="level-role-check"
                @change="onToggleLevelRole(r, $event as unknown as boolean)"
              >等级身份</t-checkbox>
              <t-input-number
                v-if="canEditRole(r) && r.is_level_role"
                :model-value="r.level"
                class="level-input"
                :min="1"
                :max="9999"
                size="small"
                theme="column"
                @change="onChangeThreshold(r, $event as number)"
              />
              <t-button
                v-if="!r.is_default && canEditRole(r)"
                variant="outline"
                size="small"
                theme="danger"
                @click="onDeleteRole(r)"
              >删除</t-button>
              <t-tag v-if="r.name === '频道主'" size="small" variant="light" theme="primary">拥有全部权限，不可修改</t-tag>
            </div>
          </div>
        </div>
      </t-tab-panel>

      <!-- 操作日志 -->
      <t-tab-panel value="ops" label="操作日志">
        <div class="panel">
          <div class="ops-toolbar">
            <!-- 真实总数（来自接口 total），不再用本地数组长度冒充 -->
            <span class="op-count">共 {{ opsTotal }} 条（已加载 {{ ops.length }} 条）</span>
            <t-button variant="outline" size="small" @click="exportOps">导出 CSV</t-button>
          </div>
          <div class="op-row" v-for="o in ops" :key="o.id">
            <span class="op-time">{{ formatTime(o.created_at) }}</span>
            <t-tag size="small" variant="light" theme="primary" class="op-action">{{ actionLabel(o.action) }}</t-tag>
            <span class="op-operator">{{ o.operator_nickname }}</span>
            <!-- 人性化展示 detail，不再把原始 JSON 直接给管理员看；悬停可看完整原始数据 -->
            <span v-if="fmtOpDetail(o)" class="op-detail" :title="JSON.stringify(o.detail)">{{ fmtOpDetail(o) }}</span>
          </div>
          <t-empty v-if="ops.length === 0" description="暂无操作记录" />
          <t-button
            v-if="ops.length < opsTotal"
            variant="outline"
            block
            class="load-more-ops"
            @click="loadMoreOps()"
          >加载更多（{{ ops.length }}/{{ opsTotal }}）</t-button>
        </div>
      </t-tab-panel>

      <!-- Feed 热度策略（文档⑮） -->
      <t-tab-panel value="strategy" label="Feed 策略">
        <div class="panel">
          <ErrorState v-if="strategyError" :text="strategyError" :retryable="true" @retry="loadStrategy" />
          <template v-else-if="strategyLoaded">
            <p class="strategy-hint">
              热度分 =（赞 × 权重 + 评 × 权重 + 藏 × 权重 + 置顶加成）× 时间衰减 exp(-发布时长 / 衰减系数)。改动保存后即时生效并清空热度缓存。
            </p>
            <div class="strategy-form">
              <div class="strategy-field strategy-field-wide">
                <label class="field-label">默认排序规则</label>
                <t-radio-group v-model="strategyForm.sort_rule" variant="default-filled">
                  <t-radio :value="0">最新发布</t-radio>
                  <t-radio :value="1">热度排序</t-radio>
                  <t-radio :value="2">精华优先</t-radio>
                </t-radio-group>
              </div>
              <div class="strategy-field">
                <label class="field-label">点赞权重</label>
                <t-input-number v-model="strategyForm.weight_like" :min="0" :max="100" theme="column" />
              </div>
              <div class="strategy-field">
                <label class="field-label">评论权重</label>
                <t-input-number v-model="strategyForm.weight_comment" :min="0" :max="100" theme="column" />
              </div>
              <div class="strategy-field">
                <label class="field-label">收藏权重</label>
                <t-input-number v-model="strategyForm.weight_favorite" :min="0" :max="100" theme="column" />
              </div>
              <div class="strategy-field">
                <label class="field-label">时间衰减（小时）</label>
                <t-input-number v-model="strategyForm.decay_hours" :min="1" :max="720" theme="column" />
              </div>
              <div class="strategy-field">
                <label class="field-label">置顶帖权重</label>
                <t-input-number v-model="strategyForm.top_weight" :min="0" :max="10000" theme="column" />
              </div>
              <div class="strategy-field">
                <label class="field-label">热度缓存秒数</label>
                <t-input-number v-model="strategyForm.cache_ttl" :min="30" :max="86400" theme="column" />
              </div>
            </div>
            <div class="strategy-ops">
              <t-button theme="primary" size="small" :loading="strategySaving" :disabled="!strategyChanged" @click="saveStrategy">
                {{ strategySaving ? '保存中…' : '保存策略' }}
              </t-button>
              <t-button v-if="strategyChanged" variant="outline" size="small" @click="resetStrategy">还原</t-button>
            </div>
          </template>
          <p v-else class="strategy-hint">加载中…</p>
        </div>
      </t-tab-panel>
    </t-tabs>

    <!-- 禁言时长弹窗 -->
    <t-dialog
      v-model:visible="shutupDialog"
      header="禁言成员"
      :confirm-btn="{ content: '确认禁言', theme: 'primary', loading: shutupSaving }"
      cancel-btn="取消"
      @confirm="confirmShutup"
    >
      <p class="shutup-tip">将禁言 <b>{{ shutupTarget?.user_nickname || shutupTarget?.nickname }}</b>：</p>
      <t-input-number v-model="shutupHours" :min="1" :max="720" theme="column" />
      <p class="shutup-tip">小时（1-720，到期自动解除）</p>
    </t-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeftIcon, ErrorCircleIcon, SoundMute1Icon } from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'
import { communityApi, feedStrategyApi, manageApi, roleApi, type Community, type Member, type MyRole, type OpLogItem, type RoleItem } from '@/api/community'
import { toast } from '@/utils/toast'
import { formatTime } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import { ApiError } from '@/api/http'
import { loadErrorMessage } from '@/utils/error'
import ErrorState from '@/components/ErrorState.vue'

const route = useRoute()
const auth = useAuthStore()
const cid = Number(route.params.id)

const tab = ref<'members' | 'roles' | 'ops' | 'strategy'>('members')
const community = ref<Community | null>(null)
const members = ref<Member[]>([])
const membersPage = ref(1)
const membersTotal = ref(0)
const membersHasMore = computed(() => members.value.length < membersTotal.value)
const membersLoading = ref(false)
const memberKeyword = ref('')
const roles = ref<RoleItem[]>([])
// 操作日志：分页拉取 + 真实总数（不再用本地数组长度冒充总数）
const ops = ref<OpLogItem[]>([])
const opsPage = ref(0)
const opsTotal = ref(0)
// 首屏加载失败态：区分无权限 / 频道不存在 / 网络故障（可重试）
const loadFailed = ref(false)
const loadError = ref('')
const notFound = ref(false)
const noPermission = ref(false)
const roleSel = reactive<Record<number, number>>({})
const roleSaving = ref(false)
const roleForm = reactive({ name: '', color: '#1a73e8', level: 1, is_level_role: false })
const myRole = ref<MyRole | null>(null)
const levelRoleMap = reactive<Record<number, boolean>>({})

// ---------- Feed 热度策略（文档⑮） ----------

const strategyForm = reactive({
  sort_rule: 1,
  weight_like: 1,
  weight_comment: 2,
  weight_favorite: 3,
  decay_hours: 24,
  top_weight: 100,
  cache_ttl: 300,
})
const strategyLoaded = ref(false)
const strategyError = ref('')
const strategySaving = ref(false)
// 保存后更新「已保存基线」，用于变更检测（显示保存/还原按钮）
let strategyBaseline = { ...strategyForm }
const strategyChanged = computed(() =>
  (Object.keys(strategyForm) as Array<keyof typeof strategyForm>).some(
    (k) => strategyForm[k] !== strategyBaseline[k],
  ),
)

async function loadStrategy() {
  strategyError.value = ''
  try {
    const s = await feedStrategyApi.get(cid)
    Object.assign(strategyForm, s)
    strategyBaseline = { ...strategyForm }
    strategyLoaded.value = true
  } catch (e) {
    strategyError.value = e instanceof Error ? e.message : '策略加载失败'
  }
}

function resetStrategy() {
  Object.assign(strategyForm, strategyBaseline)
}

async function saveStrategy() {
  if (strategySaving.value) return
  strategySaving.value = true
  try {
    const s = await feedStrategyApi.update(cid, { ...strategyForm })
    Object.assign(strategyForm, s)
    strategyBaseline = { ...strategyForm }
    toast('热度策略已保存，缓存已清空', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    strategySaving.value = false
  }
}

/** 可编辑范围：频道主恒可；否则仅排序（sort）在本人之后的身份组 */
function canEditRole(r: RoleItem): boolean {
  if (r.name === '频道主') return false
  if (myRole.value?.is_owner) return true
  return (myRole.value?.sort ?? 99) < r.sort
}

async function reloadRoles() {
  roles.value = await roleApi.list(cid)
  for (const r of roles.value) levelRoleMap[r.id] = r.is_level_role
}

// 禁言弹窗
const shutupDialog = ref(false)
const shutupSaving = ref(false)
const shutupTarget = ref<Member | null>(null)
const shutupHours = ref(24)

const PERM_ITEMS: Array<{ key: string; label: string }> = [
  { key: 'post.create', label: '发帖' },
  { key: 'comment.create', label: '评论' },
  { key: 'top', label: '置顶' },
  { key: 'essence', label: '加精' },
  { key: 'delete_post', label: '删帖' },
  { key: 'delete_comment', label: '删评论' },
  { key: 'shutup', label: '禁言' },
  { key: 'kick', label: '踢人' },
  { key: 'member_manage', label: '成员管理' },
  { key: 'role_manage', label: '身份组管理' },
  { key: 'moderate', label: '内容管理' },
  { key: 'super', label: '超级权限' },
]

const ACTION_LABELS: Record<string, string> = {
  set_top: '置顶', set_essence: '加精', delete_post: '删帖', delete_comment: '删评论',
  shutup: '禁言', unshutup: '解除禁言', kick: '踢出', block: '拉黑', unblock: '解除拉黑',
  assign_role: '分配身份', create_role: '创建身份组', update_role: '修改身份组', delete_role: '删除身份组',
  approve_join: '通过加入申请', reject_join: '驳回加入申请',
}

function memberTypeName(t: number): string {
  return t === 0 ? '频道主' : t === 1 ? '管理员' : '成员'
}

function actionLabel(a: string): string {
  return ACTION_LABELS[a] ?? a
}

/** 操作日志 detail 常见字段的人性化文案（后端写入的 key 集合见各 service 的 log_op 调用）。 */
const DETAIL_KEY_LABELS: Record<string, string> = {
  author_id: '作者',
  user_id: '用户',
  hours: '时长',
  is_top: '置顶',
  is_essence: '精华',
  name: '名称',
  sort: '排序',
}

/** 把 detail 对象转成可读文本，替代直接展示 JSON.stringify 结果。 */
function fmtOpDetail(o: OpLogItem): string {
  if (!o.detail) return ''
  const entries = Object.entries(o.detail)
  if (entries.length === 0) return ''
  return entries
    .map(([k, v]) => {
      const label = DETAIL_KEY_LABELS[k] ?? k
      let val: string
      if (k === 'hours') val = `${v} 小时`
      else if (typeof v === 'boolean') val = v ? '是' : '否'
      else if (k.endsWith('_id')) val = `#${v}`
      else val = String(v)
      return `${label}：${val}`
    })
    .join(' · ')
}

function canManage(m: Member): boolean {
  return m.user_id !== auth.user?.id && m.member_type !== 0
}

async function loadMembers(page: number, append = false) {
  // 后端 members 接口 page_size 上限 50，超出返回 400 —— 分页拉取
  membersLoading.value = true
  try {
    const data = await communityApi.members(cid, page, 50, memberKeyword.value.trim() || undefined)
    members.value = append ? [...members.value, ...data.items] : data.items
    membersTotal.value = data.total
    for (const m of data.items) roleSel[m.user_id] = m.role_id ?? 0
  } finally {
    membersLoading.value = false
  }
}

async function reloadMembers() {
  membersPage.value = 1
  await loadMembers(1)
}

async function loadMoreMembers() {
  membersPage.value += 1
  await loadMembers(membersPage.value, true)
}

async function onMemberSearch() {
  membersPage.value = 1
  await loadMembers(1)
}

/** 首屏加载：失败时给出完整错误页（无权限/不存在/可重试），不再只在底部留一行小字。 */
async function init() {
  loadFailed.value = false
  loadError.value = ''
  notFound.value = false
  noPermission.value = false
  try {
    if (!auth.user) await auth.fetchMe()
    community.value = await communityApi.get(cid)
    myRole.value = await roleApi.my(cid)
    await reloadRoles()
    await reloadMembers()
    await loadOps(1)
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) {
      noPermission.value = true
      loadError.value = '你没有该频道的管理权限（仅频道主 / 管理员 / 被授权身份可进入）'
    } else {
      const r = loadErrorMessage(e, '频道')
      notFound.value = r.notFound
      loadError.value = r.text
    }
    loadFailed.value = true
  }
}

async function loadOps(page: number, append = false) {
  const data = await manageApi.ops(cid, page, 50)
  ops.value = append ? [...ops.value, ...data.items] : data.items
  opsPage.value = page
  opsTotal.value = data.total
}

function loadMoreOps() {
  return loadOps(opsPage.value + 1, true)
}

onMounted(init)

// Feed 策略 tab 懒加载：首次切到才拉（GET 未配置时返回默认值，接口轻）
watch(tab, (t) => {
  if (t === 'strategy' && !strategyLoaded.value && !strategyError.value) loadStrategy()
})

function openShutup(m: Member) {
  shutupTarget.value = m
  shutupHours.value = 24
  shutupDialog.value = true
}

async function confirmShutup() {
  const m = shutupTarget.value
  const hours = Number(shutupHours.value)
  if (!m || !Number.isFinite(hours) || hours < 1 || hours > 720) {
    toast('请输入 1-720 的整数小时', 'error')
    shutupDialog.value = true // 弹窗已自动关闭，重新打开让用户改
    return
  }
  shutupSaving.value = true
  try {
    await manageApi.shutup(cid, m.user_id, Math.floor(hours))
    toast('已禁言')
    shutupDialog.value = false
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
    shutupDialog.value = true
  } finally {
    shutupSaving.value = false
  }
}

async function onUnshutup(m: Member) {
  try {
    await manageApi.unshutup(cid, m.user_id)
    toast('已解除禁言')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onKick(m: Member) {
  if (!(await confirmDialog('踢出成员', `确定踢出 ${m.user_nickname || m.nickname}？其将无法再进入该频道发帖。`))) return
  try {
    await manageApi.kick(cid, m.user_id)
    toast('已踢出')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onBlock(m: Member) {
  if (!(await confirmDialog('拉黑成员', `确定拉黑 ${m.user_nickname || m.nickname}？`))) return
  try {
    await manageApi.block(cid, m.user_id)
    toast('已拉黑')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onUnblock(m: Member) {
  try {
    await manageApi.unblock(cid, m.user_id)
    toast('已解除拉黑')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onAssign(m: Member) {
  const roleId = roleSel[m.user_id] === 0 ? null : roleSel[m.user_id]
  try {
    await roleApi.assign(cid, m.user_id, roleId)
    toast('身份已更新')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
    await reloadMembers()
  }
}

/** 颜色归一化：调色盘可能输出 #RRGGBB / #RRGGBBAA / rgb(r,g,b) / rgba(r,g,b,a)，统一为 6 位 hex */
function normalizeColor(c: string): string {
  const v = (c || '').trim()
  if (!v) return '#1a73e8'
  const rgb = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i)
  if (rgb) {
    return '#' + [rgb[1], rgb[2], rgb[3]].map((x) => Number(x).toString(16).padStart(2, '0')).join('')
  }
  return v.replace(/^#([0-9a-fA-F]{6})[0-9a-fA-F]{2}$/, '#$1')
}

async function onCreateRole() {
  roleSaving.value = true
  try {
    await roleApi.create(cid, {
      name: roleForm.name,
      color: normalizeColor(roleForm.color),
      level: roleForm.level,
      is_level_role: roleForm.is_level_role,
      perms: [],
    })
    roleForm.name = ''
    roleForm.level = 1
    roleForm.is_level_role = false
    await reloadRoles()
    toast('身份组已创建')
  } catch (e) {
    toast(e instanceof Error ? e.message : '创建失败', 'error')
  } finally {
    roleSaving.value = false
  }
}

async function onMoveRole(r: RoleItem, direction: 'up' | 'down') {
  try {
    await roleApi.move(cid, r.id, direction)
    await reloadRoles()
    toast('排序已调整')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onToggleLevelRole(r: RoleItem, checked: boolean) {
  try {
    await roleApi.update(cid, r.id, { is_level_role: checked })
    await reloadRoles()
    toast(checked ? '已设为等级身份' : '已取消等级身份')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  }
}

async function onChangeThreshold(r: RoleItem, value: number) {
  if (!Number.isFinite(value) || value < 1) return
  try {
    await roleApi.update(cid, r.id, { level: Math.floor(value) })
    await reloadRoles()
    toast('门槛等级已更新')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  }
}

async function onTogglePerm(r: RoleItem, perm: string, checked: boolean) {
  const perms = checked ? [...r.perms, perm] : r.perms.filter((p) => p !== perm)
  try {
    r.perms = perms
    await roleApi.update(cid, r.id, { perms })
    toast('权限已更新')
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  }
}

async function onDeleteRole(r: RoleItem) {
  if (!(await confirmDialog('删除身份组', `确定删除身份组「${r.name}」？其成员将回到默认身份。`))) return
  try {
    await roleApi.remove(cid, r.id)
    await reloadRoles()
    toast('身份组已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

/** 导出操作日志 CSV（P0）。 */
async function exportOps() {
  try {
    const res = await manageApi.exportOps(cid)
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      toast(body?.message || '导出失败', 'error')
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ops_${cid}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast('已导出操作日志', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '导出失败', 'error')
  }
}
</script>

<style scoped>
.admin {
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
.tabs {
  margin-top: var(--sp-3);
}
.panel {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-large);
  padding: var(--sp-4);
}
.load-more-ops {
  margin-top: var(--sp-2);
}
.members-toolbar {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}
.member-search {
  flex: 1;
  min-width: 0;
}
.member-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--td-component-border);
}
.member-row:last-child {
  border-bottom: none;
}
.m-info {
  flex: 1;
  min-width: 0;
}
.m-name {
  font-size: var(--fs-body);
  font-weight: 600;
}
.m-role {
  margin-left: var(--sp-2);
}
.m-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.m-blocked {
  color: var(--td-error-color);
}
/* 状态小图标：中性色随文案（禁言/移出），不用彩色 */
.m-sub-icon {
  width: 12px;
  height: 12px;
  vertical-align: -1px;
  margin-right: 2px;
}
.m-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  flex-wrap: wrap;
}
.select-sm {
  width: 110px;
}
.role-form {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--td-component-border);
  margin-bottom: var(--sp-2);
}
.role-form-hint {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.role-name-input {
  flex: 1;
  min-width: 120px;
}
.color-picker {
  width: 40px;
}
.level-input {
  width: 90px;
}
.level-role-check {
  margin-left: var(--sp-1);
}
.role-ops {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.m-lv {
  margin-left: var(--sp-1);
}
.load-more-members {
  margin-top: var(--sp-2);
}
.role-card {
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--td-component-border);
}
.role-card:last-child {
  border-bottom: none;
}
.role-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.role-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.role-name {
  font-weight: 600;
  font-size: var(--fs-body);
}
.role-id {
  margin-left: auto;
  color: var(--td-text-color-placeholder);
  font-size: var(--fs-caption);
}
.perms {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin: var(--sp-2) 0;
}
.op-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-1) 0;
  font-size: var(--fs-caption);
  border-bottom: 1px dashed var(--td-component-border);
}
.op-row:last-child {
  border-bottom: none;
}
.op-time {
  color: var(--td-text-color-placeholder);
}
.op-operator {
  margin-left: auto;
  color: var(--td-text-color-secondary);
}
.ops-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.op-count {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.op-detail {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.shutup-tip {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-body);
  color: var(--td-text-color-secondary);
}
/* Feed 热度策略表单 */
.strategy-hint {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
  line-height: 1.6;
}
.strategy-form {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--sp-4) var(--sp-3);
}
.strategy-field-wide {
  grid-column: 1 / -1;
}
.strategy-field .field-label {
  display: block;
  margin-bottom: var(--sp-1);
  font-size: var(--fs-caption);
  color: var(--td-text-color-secondary);
}
.strategy-ops {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-4);
}
</style>
