<template>
  <!-- 频道成员花名册弹层：按身份组分组排列（频道主 → 管理员 → 各身份组按权重 → 普通成员） -->
  <t-dialog
    :visible="visible"
    header="频道成员"
    :footer="false"
    width="640px"
    :confirm-btn="null"
    :cancel-btn="null"
    @close="emit('update:visible', false)"
  >
    <div class="roster">
      <ErrorState v-if="loadError" :text="loadError" :retryable="true" @retry="reload" />
      <template v-else>
        <!-- 搜索：跳转到身份组/快速找人 -->
        <t-input
          v-model="keyword"
          class="roster-search"
          placeholder="按用户名 / 昵称搜索成员"
          clearable
          @enter="reload"
          @clear="reload"
        />
        <p v-if="loading && members.length === 0" class="roster-state">加载中…</p>
        <template v-else>
          <p class="roster-total">共 {{ total }} 人</p>
          <section v-for="g in groups" :key="g.name" class="roster-group">
            <header class="roster-group-head">
              <span class="roster-group-dot" :style="{ background: g.color }" />
              <span class="roster-group-name">{{ g.name }}</span>
              <span class="roster-group-count">{{ g.members.length }} 人</span>
            </header>
            <ul class="roster-members">
              <li v-for="m in g.members" :key="m.id" class="roster-member">
                <UserAvatar :name="m.user_nickname || m.nickname" :src="m.avatar_url" :size="32" />
                <div class="roster-member-info">
                  <router-link
                    :to="`/users/${m.user_id}`"
                    class="roster-member-name"
                    @click="emit('update:visible', false)"
                  >{{ m.user_nickname || m.nickname }}</router-link>
                  <span class="roster-member-sub">
                    @{{ m.username }}<template v-if="m.level > 1"> · Lv.{{ m.level }}</template>
                  </span>
                </div>
                <t-tag v-if="m.shutup_expire_at" size="small" variant="light" theme="warning">禁言中</t-tag>
              </li>
            </ul>
          </section>
          <!-- 空组不占位；无搜索结果时给明确反馈 -->
          <p v-if="groups.length === 0" class="roster-state">没有匹配的成员</p>
          <!-- 大频道分页续拉：接口每页最多 50 -->
          <t-button
            v-if="members.length < total"
            variant="outline"
            block
            class="roster-more"
            :loading="loading"
            @click="loadMore"
          >{{ loading ? '加载中…' : `加载更多（${members.length}/${total}）` }}</t-button>
        </template>
      </template>
    </div>
  </t-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { communityApi, roleApi, type Member, type RoleItem } from '@/api/community'
import UserAvatar from '@/components/UserAvatar.vue'
import ErrorState from '@/components/ErrorState.vue'

const props = defineProps<{ cid: number; visible: boolean }>()
const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const members = ref<Member[]>([])
const roles = ref<RoleItem[]>([])
const total = ref(0)
const page = ref(0)
const loading = ref(false)
const loadError = ref('')
const keyword = ref('')

/** 按身份组分组：频道主 → 管理员 → 各身份组（按 sort 权重升序）→ 未分组普通成员。
 *  空组不展示；搜索结果同样保持分组结构。 */
const groups = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const pool = kw
    ? members.value.filter(
        (m) =>
          m.username.toLowerCase().includes(kw) ||
          (m.user_nickname || m.nickname).toLowerCase().includes(kw),
      )
    : members.value
  const out: Array<{ name: string; color: string; members: Member[] }> = [
    { name: '频道主', color: '#ed7b2f', members: pool.filter((m) => m.member_type === 0) },
    { name: '管理员', color: '#0052d9', members: pool.filter((m) => m.member_type === 1) },
  ]
  for (const r of roles.value) {
    out.push({
      name: r.name,
      color: r.color,
      members: pool.filter((m) => m.member_type >= 2 && m.role_id === r.id),
    })
  }
  out.push({
    name: '成员',
    color: 'var(--text-3)',
    members: pool.filter((m) => m.member_type >= 2 && !m.role_id),
  })
  return out.filter((g) => g.members.length > 0)
})

async function loadPage(p: number, append = false) {
  if (loading.value) return
  loading.value = true
  try {
    // 成员与身份组两个公开接口；成员带 role_id/role_name，身份组列表给排序与颜色
    const data = await communityApi.members(props.cid, p, 50, keyword.value.trim() || undefined)
    members.value = append ? [...members.value, ...data.items] : data.items
    page.value = p
    total.value = data.total
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '成员列表加载失败'
  } finally {
    loading.value = false
  }
}

/** 首次打开：拉身份组 + 首页成员（keyword 搜索交给服务端，身份组只拉一次）。 */
async function reload() {
  loadError.value = ''
  try {
    if (roles.value.length === 0) roles.value = await roleApi.list(props.cid)
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '身份组加载失败'
    return
  }
  await loadPage(1)
}

function loadMore() {
  return loadPage(page.value + 1, true)
}

watch(
  () => props.visible,
  (v) => {
    // 打开时拉取（首次或换过频道后）
    if (v && members.value.length === 0) reload()
  },
)

// 切频道（三栏左栏就地切换 /c/:id）：清空缓存，下次打开重拉新频道数据
watch(
  () => props.cid,
  () => {
    members.value = []
    roles.value = []
    total.value = 0
    page.value = 0
    keyword.value = ''
    loadError.value = ''
  },
)
</script>

<style scoped>
.roster {
  max-height: 60vh;
  overflow-y: auto;
}
.roster-search {
  margin-bottom: var(--sp-3);
}
.roster-total {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.roster-group {
  margin-bottom: var(--sp-4);
}
.roster-group-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--sp-2);
  padding-bottom: var(--sp-1);
  border-bottom: 1px solid var(--border);
}
.roster-group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.roster-group-name {
  font-size: var(--fs-body);
  font-weight: 600;
  color: var(--text-1);
}
.roster-group-count {
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.roster-members {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--sp-2);
}
.roster-member {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.roster-member-info {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}
.roster-member-name {
  font-size: var(--fs-body);
  color: var(--text-1);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.roster-member-name:hover {
  color: var(--brand);
}
.roster-member-sub {
  font-size: var(--fs-caption);
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.roster-state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.roster-more {
  margin-top: var(--sp-2);
}
</style>
