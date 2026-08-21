<template>
  <main class="page">
    <header class="page-header">
      <router-link to="/me" class="back">
        <ArrowLeftIcon class="back-icon" /> 我的
      </router-link>
      <h1 class="page-title">我的频道</h1>
    </header>

    <t-tabs v-model="active" class="channels-tabs">
      <t-tab-panel :value="0" :label="`我创建的${lists.owned.length ? `（${lists.owned.length}）` : ''}`">
        <ChannelGroup :loading="loading" :items="lists.owned" empty-text="还没有创建过频道" />
      </t-tab-panel>
      <t-tab-panel :value="1" :label="`我管理的${lists.managed.length ? `（${lists.managed.length}）` : ''}`">
        <ChannelGroup :loading="loading" :items="lists.managed" empty-text="还没有管理的频道" />
      </t-tab-panel>
      <t-tab-panel :value="2" :label="`我加入的${lists.joined.length ? `（${lists.joined.length}）` : ''}`">
        <ChannelGroup :loading="loading" :items="lists.joined" empty-text="还没有加入的频道，去发现页看看吧" action-text="去发现频道" action-to="/discover" />
      </t-tab-panel>
    </t-tabs>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { onBeforeRouteUpdate } from 'vue-router'
import { ArrowLeftIcon } from 'tdesign-icons-vue-next'
import { communityApi, type Community } from '@/api/community'
import ChannelGroup from '@/components/channel/ChannelGroup.vue'

const active = ref(0)
const loading = ref(false)
const lists = reactive<{ owned: Community[]; managed: Community[]; joined: Community[] }>({
  owned: [],
  managed: [],
  joined: [],
})

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await communityApi.mine()
    lists.owned = data.owned
    lists.managed = data.managed
    lists.joined = data.joined
  } finally {
    loading.value = false
  }
}

// 切回本页时刷新
onMounted(load)
onBeforeRouteUpdate((to, from) => {
  if (to.name === 'my-channels' && from.name !== 'my-channels') load()
  return true
})
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
.channels-tabs {
  margin-top: var(--sp-3);
}
</style>