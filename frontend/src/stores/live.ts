/** 实时新内容计数（P1 ③）：后端 WS 广播 feed_new 后按频道递增，前端浮动药丸展示。
 *
 * feed_new 是「按频道」的定向广播（载荷含 community_id），而药丸的「点击查看」
 * 只会刷新当前正在看的信息流 —— 因此计数必须按频道分开存：
 * 看 A 频道时 B 频道的新帖不应让药丸出现（点了也刷新不出任何东西）。
 * 「当前频道」由 NewPostsPill 按路由判定（/c/:id 读路由参数，首页读 activeCid），
 * 无单一频道上下文的聚合流（发现/关注）则累计全部。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useLiveStore = defineStore('live', () => {
  /** community_id → 未查看的新内容数。 */
  const counts = ref<Record<number, number>>({})
  /** 首页工作台当前展示的频道（由 ChannelWorkspace 写入；null = 无上下文/未展示）。 */
  const activeCid = ref<number | null>(null)

  const total = computed(() => Object.values(counts.value).reduce((a, b) => a + b, 0))

  /** 指定频道的计数；cid 为 null（无上下文）返回 0。 */
  function countFor(cid: number | null): number {
    return cid === null ? 0 : counts.value[cid] ?? 0
  }

  function increment(communityId: number, n = 1) {
    counts.value = { ...counts.value, [communityId]: (counts.value[communityId] ?? 0) + n }
  }

  function reset() {
    counts.value = {}
  }

  /** 首页工作台声明当前频道（keep-alive 下用 activated/deactivated 维护，离开置空）。 */
  function setActive(cid: number | null) {
    activeCid.value = cid
  }

  return { counts, activeCid, total, countFor, increment, reset, setActive }
})
