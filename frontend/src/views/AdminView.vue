<template>
  <main class="admin">
    <header class="page-header">
      <router-link :to="`/c/${cid}`" class="back">← {{ community?.name || '频道' }}</router-link>
      <h1 class="page-title">管理后台</h1>
    </header>

    <div class="tabs" role="tablist">
      <button class="tab" :class="{ active: tab === 'members' }" @click="tab = 'members'">成员管理</button>
      <button class="tab" :class="{ active: tab === 'roles' }" @click="tab = 'roles'">身份组</button>
      <button class="tab" :class="{ active: tab === 'ops' }" @click="tab = 'ops'">操作日志</button>
    </div>

    <p v-if="msg" class="msg">{{ msg }}</p>

    <!-- 成员管理 -->
    <section v-if="tab === 'members'" class="panel">
      <div class="member-row" v-for="m in members" :key="m.id">
        <img v-if="m.avatar_url" :src="m.avatar_url" class="avatar" alt="" />
        <div class="m-info">
          <div class="m-name">
            {{ m.user_nickname || m.nickname }}
            <span class="m-role" :title="`member_type=${m.member_type}`">
              {{ m.role_name || memberTypeName(m.member_type) }}
            </span>
          </div>
          <div class="m-sub">
            <span v-if="m.shutup_expire_at" class="m-muted">🔇 禁言至 {{ m.shutup_expire_at.slice(0, 16) }}</span>
            <span v-if="m.is_blocked" class="m-blocked">🚫 已移出</span>
            <span v-else class="m-muted">@{{ m.username }}</span>
          </div>
        </div>
        <div v-if="canManage(m)" class="m-actions">
          <select
            v-model="roleSel[m.user_id]"
            class="input select-sm"
            :disabled="m.is_blocked"
            @change="onAssign(m)"
          >
            <option :value="null">默认身份</option>
            <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
          <button class="btn-ghost btn-xs" :disabled="m.is_blocked" @click="onShutup(m)">禁言</button>
          <button v-if="m.shutup_expire_at" class="btn-ghost btn-xs" :disabled="m.is_blocked" @click="onUnshutup(m)">解禁</button>
          <button class="btn-ghost btn-xs danger" :disabled="m.is_blocked" @click="onKick(m)">踢出</button>
          <button v-if="m.is_blocked" class="btn-ghost btn-xs" @click="onUnblock(m)">解除拉黑</button>
          <button v-else class="btn-ghost btn-xs danger" @click="onBlock(m)">拉黑</button>
        </div>
      </div>
      <p v-if="members.length === 0" class="empty">暂无成员</p>
    </section>

    <!-- 身份组 -->
    <section v-if="tab === 'roles'" class="panel">
      <div class="role-form">
        <input v-model.trim="roleForm.name" class="input role-name-input" placeholder="身份组名称" maxlength="32" />
        <input v-model="roleForm.color" class="input color-input" placeholder="#1a73e8" maxlength="7" />
        <input v-model.number="roleForm.level" class="input level-input" type="number" min="0" max="99" placeholder="等级" />
        <button class="btn-primary btn-sm" :disabled="roleSaving || !roleForm.name" @click="onCreateRole">
          {{ roleSaving ? '创建中…' : '新建身份组' }}
        </button>
      </div>
      <div class="role-card" v-for="r in roles" :key="r.id">
        <div class="role-head">
          <span class="role-dot" :style="{ background: r.color }"></span>
          <span class="role-name">{{ r.name }}</span>
          <span class="role-level">Lv.{{ r.level }}</span>
          <span v-if="r.is_default" class="tag">默认</span>
          <span class="role-id">#{{ r.id }}</span>
        </div>
        <div class="perms">
          <label v-for="p in PERM_ITEMS" :key="p.key" class="perm">
            <input
              type="checkbox"
              :checked="r.perms.includes(p.key)"
              :disabled="r.name === '频道主'"
              @change="onTogglePerm(r, p.key, ($event.target as HTMLInputElement).checked)"
            />
            {{ p.label }}
          </label>
        </div>
        <button v-if="!r.is_default" class="btn-ghost btn-xs danger" @click="onDeleteRole(r)">删除</button>
      </div>
    </section>

    <!-- 操作日志 -->
    <section v-if="tab === 'ops'" class="panel">
      <div class="op-row" v-for="o in ops" :key="o.id">
        <span class="op-time">{{ o.created_at.slice(0, 16) }}</span>
        <span class="op-action">{{ actionLabel(o.action) }}</span>
        <span class="op-operator">{{ o.operator_nickname }}</span>
      </div>
      <p v-if="ops.length === 0" class="empty">暂无操作记录</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { communityApi, manageApi, roleApi, type Community, type Member, type OpLogItem, type RoleItem } from '@/api/community'
import { toast } from '@/utils/toast'

const route = useRoute()
const auth = useAuthStore()
const cid = Number(route.params.id)

const tab = ref<'members' | 'roles' | 'ops'>('members')
const community = ref<Community | null>(null)
const members = ref<Member[]>([])
const roles = ref<RoleItem[]>([])
const ops = ref<OpLogItem[]>([])
const msg = ref('')
const roleSel = reactive<Record<number, number | null>>({})
const roleSaving = ref(false)
const roleForm = reactive({ name: '', color: '#1a73e8', level: 0 })

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

async function reloadMembers() {
  const data = await communityApi.members(cid, 1, 100)
  members.value = data.items
  for (const m of data.items) roleSel[m.user_id] = m.role_id ?? null
}

onMounted(async () => {
  try {
    if (!auth.user) await auth.fetchMe()
    community.value = await communityApi.get(cid)
    roles.value = await roleApi.list(cid)
    await reloadMembers()
    ops.value = (await manageApi.ops(cid, 1, 50)).items
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '加载失败'
  }
})

async function onShutup(m: Member) {
  const input = window.prompt(`禁言 ${m.user_nickname || m.nickname} 的时长（小时，1-720）`, '24')
  if (input === null) return
  const hours = Number(input)
  if (!Number.isFinite(hours) || hours < 1 || hours > 720) {
    toast('请输入 1-720 的整数小时', 'error')
    return
  }
  try {
    await manageApi.shutup(cid, m.user_id, Math.floor(hours))
    toast('已禁言')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
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
  if (!confirm(`确定踢出 ${m.user_nickname || m.nickname}？其将无法再进入该频道发帖。`)) return
  try {
    await manageApi.kick(cid, m.user_id)
    toast('已踢出')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onBlock(m: Member) {
  if (!confirm(`确定拉黑 ${m.user_nickname || m.nickname}？`)) return
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
  const roleId = roleSel[m.user_id] ?? null
  try {
    await roleApi.assign(cid, m.user_id, roleId)
    toast('身份已更新')
    await reloadMembers()
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
    await reloadMembers()
  }
}

async function onCreateRole() {
  roleSaving.value = true
  try {
    await roleApi.create(cid, { ...roleForm, perms: [] })
    roleForm.name = ''
    roleForm.level = 0
    roles.value = await roleApi.list(cid)
    toast('身份组已创建')
  } catch (e) {
    toast(e instanceof Error ? e.message : '创建失败', 'error')
  } finally {
    roleSaving.value = false
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
  if (!confirm(`确定删除身份组「${r.name}」？其成员将回到默认身份。`)) return
  try {
    await roleApi.remove(cid, r.id)
    roles.value = await roleApi.list(cid)
    toast('身份组已删除')
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
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
}
.page-title {
  margin: 0;
  font-size: var(--fs-title);
  font-weight: 600;
  flex: 1;
}
.tabs {
  display: flex;
  gap: var(--sp-2);
  margin: var(--sp-3) 0;
}
.tab {
  height: 34px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-2);
  font-size: var(--fs-body);
  cursor: pointer;
}
.tab.active {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-weak);
}
.panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.msg {
  color: var(--danger);
  font-size: var(--fs-caption);
}
.empty {
  color: var(--text-3);
  font-size: var(--fs-caption);
  text-align: center;
  padding: var(--sp-4) 0;
}
.member-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
}
.member-row:last-child {
  border-bottom: none;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border);
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
  font-size: var(--fs-caption);
  color: var(--brand);
  background: var(--brand-weak);
  border-radius: 4px;
  padding: 1px 6px;
}
.m-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.m-blocked {
  color: var(--danger);
}
.m-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  flex-wrap: wrap;
}
.btn-xs {
  height: 26px;
  padding: 0 var(--sp-2);
  font-size: var(--fs-caption);
}
.select-sm {
  height: 26px;
  font-size: var(--fs-caption);
  padding: 0 var(--sp-1);
  max-width: 96px;
}
.btn-ghost {
  height: 36px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.btn-ghost.danger {
  color: var(--danger);
  border-color: var(--danger);
}
.btn-primary {
  height: 36px;
  padding: 0 var(--sp-4);
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand);
  color: #fff;
  font-size: var(--fs-body);
  cursor: pointer;
}
.btn-sm {
  height: 32px;
  padding: 0 var(--sp-3);
  font-size: var(--fs-caption);
}
.input {
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  padding: 0 var(--sp-2);
  height: 32px;
  font-size: var(--fs-caption);
  outline: none;
  background: var(--bg-card);
  color: var(--text-1);
}
.input:focus {
  border-color: var(--brand);
}
.role-form {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--border);
  margin-bottom: var(--sp-2);
}
.role-name-input {
  flex: 1;
  min-width: 120px;
}
.color-input {
  width: 96px;
}
.level-input {
  width: 72px;
}
.role-card {
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--border);
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
.role-level {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.role-id {
  margin-left: auto;
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.tag {
  font-size: var(--fs-caption);
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}
.perms {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin: var(--sp-2) 0;
}
.perm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-caption);
  color: var(--text-2);
  cursor: pointer;
}
.op-row {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-1) 0;
  font-size: var(--fs-caption);
  border-bottom: 1px dashed var(--border);
}
.op-row:last-child {
  border-bottom: none;
}
.op-time {
  color: var(--text-3);
}
.op-action {
  font-weight: 600;
}
.op-operator {
  margin-left: auto;
  color: var(--text-2);
}
</style>
