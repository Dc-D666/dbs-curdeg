/** 乐观更新（P0）：轻量交互（点赞/收藏/关注）点击瞬间翻转本地状态，后台静默提交，失败回滚。

用法（组件内）：
  const interaction = useInteractionStore()
  const key = `like:${post.id}`
  if (interaction.isPending(key)) return           // 防连点
  try {
    await interaction.run(key, {
      apply: () => { post.is_liked = !post.is_liked; post.like_count += delta },
      rollback: () => { 还原 apply 改动的状态 },
      request: () => postApi.like(post.id),        // 真实请求
      onSuccess: (r) => { post.like_count = r.count },  // 以服务端权威值校准
    })
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
*/
import { defineStore } from 'pinia'
import { reactive } from 'vue'

interface OptimisticOptions<T> {
  /** 立即应用乐观状态（同步执行）。 */
  apply: () => void
  /** 请求失败时还原 apply 产生的状态变化。 */
  rollback: () => void
  /** 真实后台请求。 */
  request: () => Promise<T>
  /** 成功后校准（可选，例如用服务端返回的权威计数覆盖本地）。 */
  onSuccess?: (data: T) => void
}

export const useInteractionStore = defineStore('interaction', () => {
  /** 进行中的操作 key（如 `like:12`），用于防连点与全局去重。 */
  const pending = reactive(new Set<string>())

  function isPending(key: string): boolean {
    return pending.has(key)
  }

  /**
   * 执行一次乐观操作：apply → request → onSuccess / rollback。
   * 返回 true 表示本次执行；key 已在途时返回 false（静默忽略连点）。
   * 请求失败会抛错（rollback 已执行），由调用方负责 toast。
   */
  async function run<T>(key: string, opts: OptimisticOptions<T>): Promise<boolean> {
    if (pending.has(key)) return false
    pending.add(key)
    opts.apply()
    try {
      const data = await opts.request()
      opts.onSuccess?.(data)
      return true
    } catch (e) {
      opts.rollback()
      throw e
    } finally {
      pending.delete(key)
    }
  }

  return { pending, isPending, run }
})
