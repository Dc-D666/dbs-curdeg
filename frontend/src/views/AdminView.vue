<template>
  <main class="admin">
    <header class="page-header">
      <router-link :to="`/c/${cid}`" class="back">
        <ArrowLeftIcon class="back-icon" /> {{ community?.name || '频道' }}
      </router-link>
      <h1 class="page-title">管理后台</h1>
    </header>

    <t-tabs v-model="tab" class="tabs">
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
                <span v-if="m.shutup_expire_at" class="m-muted">🔇 禁言至 {{ formatTime(m.shutup_expire_at) }}</span>
                <span v-if="m.is_blocked" class="m-blocked">🚫 已移出</span>
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
            <span class="op-count">共 {{ ops.length }} 条</span>
            <t-button variant="outline" size="small" @click="exportOps">导出 CSV</t-button>
          </div>
          <div class="op-row" v-for="o in ops" :key="o.id">
            <span class="op-time">{{ formatTime(o.created_at) }}</span>
            <t-tag size="small" variant="light" theme="primary" class="op-action">{{ actionLabel(o.action) }}</t-tag>
            <span class="op-operator">{{ o.operator_nickname }}</span>
            <span v-if="o.detail" class="op-detail" :title="JSON.stringify(o.detail)">{{ JSON.stringify(o.detail) }}</span>
          </div>
          <t-empty v-if="ops.length === 0" description="暂无操作记录" />
        </div>
      </t-tab-panel>
    </t-tabs>

    <p v-if="msg" class="msg">{{ msg }}</p>

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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'
import { communityApi, manageApi, roleApi, type Community, type Member, type MyRole, type OpLogItem, type RoleItem } from '@/api/community'
import { toast } from '@/utils/toast'
import { formatTime } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import { tokenStore } from '@/api/http'

const route = useRoute()
const auth = useAuthStore()
const cid = Number(route.params.id)

const tab = ref<'members' | 'roles' | 'ops'>('members')
const community = ref<Community | null>(null)
const members = ref<Member[]>([])
const membersPage = ref(1)
const membersTotal = ref(0)
const membersHasMore = computed(() => members.value.length < membersTotal.value)
const membersLoading = ref(false)
const memberKeyword = ref('')
const roles = ref<RoleItem[]>([])
const ops = ref<OpLogItem[]>([])
const msg = ref('')
const roleSel = reactive<Record<number, number>>({})
const roleSaving = ref(false)
const roleForm = reactive({ name: '', color: '#1a73e8', level: 1, is_level_role: false })
const myRole = ref<MyRole | null>(null)
const levelRoleMap = reactive<Record<number, boolean>>({})

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

onMounted(async () => {
  try {
    if (!auth.user) await auth.fetchMe()
    community.value = await communityApi.get(cid)
    myRole.value = await roleApi.my(cid)
    await reloadRoles()
    await reloadMembers()
    ops.value = (await manageApi.ops(cid, 1, 50)).items
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '加载失败'
  }
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
.msg {
  color: var(--td-error-color);
  font-size: var(--fs-caption);
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
</style>
