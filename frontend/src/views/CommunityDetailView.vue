<template>
  <main class="detail">
    <header class="page-header">
      <router-link to="/discover" class="back">← 发现</router-link>
      <h1 class="page-title">{{ community?.name || '频道' }}</h1>
      <span v-if="community?.is_member" class="tag tag-member">已加入</span>
    </header>

    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="community">
      <section class="panel head-panel">
        <p class="profile">{{ community.profile || '暂无简介' }}</p>
        <div class="meta">
          <span>{{ community.member_count }} 成员</span>
          <span>{{ community.boards.length }} 个版块</span>
          <span>#{{ community.number }}</span>
        </div>
        <div class="actions">
          <template v-if="community.is_member">
            <button v-if="community.my_member_type !== 0" class="btn-ghost" @click="onLeave">退出频道</button>
            <router-link v-if="community.my_member_type === 0" to="/me" class="btn-ghost">管理</router-link>
          </template>
          <button v-else class="btn-primary" :disabled="joining" @click="onJoin">
            {{ joining ? '处理中…' : '加入频道' }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="board-tabs" role="tablist">
          <button
            v-for="b in community.boards"
            :key="b.id"
            class="tab"
            :class="{ active: activeBoard === b.id }"
            @click="activeBoard = b.id"
          >
            {{ b.name }}
          </button>
          <span v-if="community.boards.length === 0" class="no-board">暂无版块</span>
        </div>
        <div v-if="activeBoardInfo" class="board-desc">{{ activeBoardInfo.description || '暂无版块描述' }}</div>
        <div v-else-if="community.boards.length === 0" class="empty-block">
          <p class="state">版块还未创建，帖子功能将在后续阶段上线</p>
        </div>
      </section>
    </div>
    <div v-else class="state">频道不存在</div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { communityApi, type Community } from '@/api/community'
import { tokenStore } from '@/api/http'

const route = useRoute()
const cid = Number(route.params.id)
const community = ref<Community | null>(null)
const loading = ref(true)
const joining = ref(false)
const activeBoard = ref<number | null>(null)

const activeBoardInfo = computed(
  () => community.value?.boards.find((b) => b.id === activeBoard.value) ?? null,
)

onMounted(async () => {
  try {
    community.value = await communityApi.get(cid)
    if (community.value.boards.length > 0) {
      activeBoard.value = community.value.boards[0].id
    }
  } finally {
    loading.value = false
  }
})

async function onJoin() {
  if (!tokenStore.access) {
    window.location.href = '/login'
    return
  }
  if (joining.value) return
  joining.value = true
  try {
    await communityApi.join(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    alert(e instanceof Error ? e.message : '操作失败')
  } finally {
    joining.value = false
  }
}

async function onLeave() {
  if (!confirm('确定退出该频道？')) return
  try {
    await communityApi.leave(cid)
    community.value = await communityApi.get(cid)
  } catch (e) {
    alert(e instanceof Error ? e.message : '操作失败')
  }
}
</script>

<style scoped>
.detail {
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
.state {
  padding: var(--sp-6) 0;
  text-align: center;
  color: var(--text-3);
}
.panel {
  margin-top: var(--sp-4);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--sp-4);
}
.head-panel .profile {
  margin: 0;
  color: var(--text-2);
}
.meta {
  margin-top: var(--sp-3);
  display: flex;
  gap: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.actions {
  margin-top: var(--sp-4);
  display: flex;
  gap: var(--sp-2);
}
.board-tabs {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
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
  transition: all 0.15s;
}
.tab.active {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-weak);
}
.no-board {
  color: var(--text-3);
  font-size: var(--fs-caption);
}
.board-desc {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--text-3);
}
.empty-block {
  margin-top: var(--sp-3);
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
  height: 36px;
  padding: 0 var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-btn);
  background: var(--bg-card);
  color: var(--text-1);
  font-size: var(--fs-body);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
</style>
