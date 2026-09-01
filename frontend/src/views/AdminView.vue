<template>
  <main class="admin">
    <header class="page-header">
      <router-link to="/" class="back">
        <ArrowLeftIcon class="back-icon" /> 返回主页
      </router-link>
      <h1 class="page-title">频道管理</h1>
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

      <!-- 板块管理 -->
      <t-tab-panel value="boards" label="板块管理">
        <div class="panel">
          <div class="board-form">
            <t-input v-model.trim="boardForm.name" class="board-name-input" placeholder="板块名称" maxlength="64" clearable />
            <t-input v-model.trim="boardForm.description" class="board-name-input" placeholder="简介（可选）" maxlength="255" clearable />
            <t-select v-model="boardForm.allow_post_role_ids" class="board-role-select" multiple placeholder="发帖身份组（空=所有人）" clearable>
              <t-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" />
            </t-select>
            <t-button theme="primary" size="small" :loading="boardSaving" :disabled="!boardForm.name.trim()" @click="onCreateBoard">
              {{ boardSaving ? '创建中…' : '新建板块' }}
            </t-button>
          </div>
          <p class="board-form-hint">「发帖身份组」不选 = 所有人可发帖；选了仅指定身份组可在此板块发帖。</p>
          <div class="board-card" v-for="(b, i) in boards" :key="b.id">
            <div class="board-head">
              <span class="board-name">#{{ b.name }}</span>
              <t-tag v-if="b.status === 2" size="small" variant="light" theme="danger">已关闭</t-tag>
              <t-tag v-if="b.allow_post_role_ids.length" size="small" variant="outline">限身份组发帖</t-tag>
              <span class="board-desc">{{ b.description || '暂无简介' }}</span>
            </div>
            <div class="board-ops">
              <t-button variant="text" size="small" :disabled="i === 0" @click="onMoveBoard(b, 'up')">↑ 上移</t-button>
              <t-button variant="text" size="small" :disabled="i === boards.length - 1" @click="onMoveBoard(b, 'down')">↓ 下移</t-button>
              <t-button variant="outline" size="small" @click="openBoardEdit(b)">编辑</t-button>
              <t-button v-if="b.status !== 2" variant="outline" size="small" theme="danger" @click="onCloseBoard(b)">关闭</t-button>
              <t-button v-else variant="outline" size="small" @click="onReopenBoard(b)">重新启用</t-button>
            </div>
          </div>
          <t-empty v-if="boards.length === 0" description="暂无板块" />

          <!-- 板块编辑弹窗：名称/简介/发帖身份组/排序 -->
          <t-dialog
            v-model:visible="boardDialog"
            header="编辑板块"
            :confirm-btn="{ content: '保存', theme: 'primary', loading: boardSaving }"
            cancel-btn="取消"
            @confirm="onSaveBoard"
          >
            <div class="board-edit-form">
              <div class="board-edit-field">
                <span class="board-edit-label">板块名称</span>
                <t-input v-model.trim="boardEditForm.name" maxlength="64" placeholder="板块名称" />
              </div>
              <div class="board-edit-field">
                <span class="board-edit-label">板块简介</span>
                <t-textarea v-model.trim="boardEditForm.description" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="255" placeholder="简介（可选）" />
              </div>
              <div class="board-edit-field">
                <span class="board-edit-label">发帖身份组</span>
                <t-select v-model="boardEditForm.allow_post_role_ids" multiple placeholder="空=所有人可发帖" clearable>
                  <t-option v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" />
                </t-select>
              </div>
              <div class="board-edit-field">
                <span class="board-edit-label">排序（数字越小越靠前）</span>
                <t-input-number v-model="boardEditForm.sort" :min="0" :max="9999" theme="column" />
              </div>
            </div>
          </t-dialog>
        </div>
      </t-tab-panel>

      <!-- 加入设置 -->
      <t-tab-panel value="join" label="加入设置">
        <div class="panel">
          <div class="join-row">
            <span class="join-label">谁可以加入</span>
            <t-radio-group v-model="joinSetting" variant="default-filled" @change="onJoinSettingChange">
              <t-radio :value="0">所有人（自由加入）</t-radio>
              <t-radio :value="1">需要审核</t-radio>
              <t-radio :value="2">不允许任何人加入</t-radio>
            </t-radio-group>
          </div>
          <p class="join-hint">设置为「需要审核」后，成员申请需管理员在此通过；「不允许任何人加入」将关闭加入入口。</p>

          <template v-if="joinSetting === 1">
            <div class="divider"></div>
            <div class="join-requests">
              <div class="join-req-head">
                <span class="join-req-count">待审核申请（{{ requestsTotal }}）</span>
                <t-button variant="outline" size="small" :loading="requestsLoading" @click="loadRequests(1)">刷新</t-button>
              </div>
              <div class="join-req-row" v-for="r in joinRequests" :key="r.id">
                <t-avatar :image="r.user_avatar || undefined" size="32px">
                  <template #icon>{{ (r.user_nickname || r.username).slice(0, 1) }}</template>
                </t-avatar>
                <span class="join-req-name">{{ r.user_nickname || r.username }}</span>
                <span class="join-req-time">{{ formatTime(r.created_at) }}</span>
                <t-button variant="outline" size="small" @click="onHandleRequest(r, true)">通过</t-button>
                <t-button variant="outline" size="small" theme="danger" @click="onHandleRequest(r, false)">驳回</t-button>
              </div>
              <t-empty v-if="joinRequests.length === 0" description="暂无待审核申请" />
            </div>
          </template>
        </div>
      </t-tab-panel>

      <!-- 全员禁言 -->
      <t-tab-panel value="mute" label="全员禁言">
        <div class="panel">
          <div class="mute-status">
            <span class="mute-label">当前状态</span>
            <t-tag :theme="isAllMuted ? 'danger' : 'success'" variant="light">
              {{ isAllMuted ? `已全员禁言至 ${formatTime(community?.all_muted_until || '')}` : '未禁言' }}
            </t-tag>
          </div>
          <div class="mute-form">
            <span class="mute-field">
              <t-input-number v-model="muteDays" :min="0" :max="30" theme="column" class="mute-num" />
              <span class="mute-unit">天</span>
            </span>
            <span class="mute-field">
              <t-input-number v-model="muteHours" :min="0" :max="23" theme="column" class="mute-num" />
              <span class="mute-unit">时</span>
            </span>
            <span class="mute-field">
              <t-input-number v-model="muteMinutes" :min="0" :max="59" theme="column" class="mute-num" />
              <span class="mute-unit">分</span>
            </span>
            <t-button theme="primary" size="small" :loading="muteSaving" :disabled="muteTotalHours <= 0" @click="onAllMute(true)">全员禁言</t-button>
            <t-button variant="outline" size="small" theme="danger" :disabled="!isAllMuted" :loading="muteSaving" @click="onAllMute(false)">解除禁言</t-button>
          </div>
          <p class="mute-hint">禁言期间所有成员不能发帖与评论，点赞不受影响；到期自动解除。</p>
        </div>
      </t-tab-panel>

      <!-- 帖子管理 -->
      <t-tab-panel value="posts" label="帖子管理">
        <div class="panel">
          <div class="posts-toolbar">
            <t-select v-model="postBoardFilter" class="post-board-filter" placeholder="全部板块" clearable>
              <t-option v-for="b in boards" :key="b.id" :value="b.id" :label="b.name" />
            </t-select>
            <t-button variant="outline" size="small" :loading="postsLoading" @click="loadPosts(1)">刷新</t-button>
          </div>
          <div class="post-row" v-for="p in posts" :key="p.id">
            <div class="post-info">
              <router-link :to="`/p/${p.id}`" class="post-title">{{ p.title }}</router-link>
              <div class="post-meta">
                <span>{{ p.board_name }}</span>
                <span>{{ p.like_count }} 赞 · {{ p.comment_count }} 评</span>
                <span>{{ timeAgo(p.created_at) }}</span>
              </div>
            </div>
            <div class="post-ops">
              <t-select
                :value="p.board_id"
                class="post-move-select"
                size="small"
                placeholder="移动到板块"
                @change="(v: number) => onMovePost(p, v)"
              >
                <t-option v-for="b in boards" :key="b.id" :value="b.id" :label="b.name" />
              </t-select>
              <t-button variant="outline" size="small" theme="danger" @click="onDeletePost(p)">删除</t-button>
            </div>
          </div>
          <t-empty v-if="posts.length === 0" description="暂无帖子" />
          <t-button
            v-if="postsHasMore"
            variant="outline"
            block
            class="load-more-posts"
            :loading="postsLoading"
            @click="loadPosts(postsPage + 1, true)"
          >加载更多（已加载 {{ posts.length }}）</t-button>
        </div>
      </t-tab-panel>

      <!-- 黑名单 -->
      <t-tab-panel value="blacklist" label="黑名单">
        <div class="panel">
          <div class="blacklist-toolbar">
            <t-input v-model.trim="blacklistKeyword" class="blacklist-search" placeholder="按用户名/昵称搜索" clearable @enter="onBlacklistSearch" @clear="onBlacklistSearch" />
            <t-button variant="outline" size="small" :loading="blacklistLoading" @click="onBlacklistSearch">搜索</t-button>
          </div>
          <div class="member-row" v-for="m in blacklistMembers" :key="m.user_id">
            <t-avatar :image="m.avatar_url || undefined" size="36px">
              <template #icon>{{ (m.user_nickname || m.nickname).slice(0, 1) }}</template>
            </t-avatar>
            <div class="m-info">
              <div class="m-name">{{ m.user_nickname || m.nickname }}</div>
              <div class="m-sub">@{{ m.username }} · 已移出</div>
            </div>
            <t-button variant="outline" size="small" @click="onUnblockBlacklist(m)">解除拉黑</t-button>
          </div>
          <t-empty v-if="blacklistMembers.length === 0" description="黑名单为空" />
          <t-button
            v-if="blacklistMembers.length < blacklistTotal"
            variant="outline"
            block
            class="load-more-blacklist"
            :loading="blacklistLoading"
            @click="loadBlacklist(blacklistPage + 1)"
          >加载更多（{{ blacklistMembers.length }}/{{ blacklistTotal }}）</t-button>
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

      <!-- AI bot 管理 -->
      <t-tab-panel value="ai" label="AI bot 管理">
        <div class="panel">
          <p class="ai-hint">创建虚拟助手成员，可在发帖评论中 @ 提问（后续完善对话配置）。</p>
          <div class="ai-row">
            <t-input v-model.trim="aiNickname" class="ai-nickname" placeholder="助手昵称" maxlength="64" />
            <t-button theme="primary" size="small" :loading="aiSaving" @click="onEnsureAi">启用 AI 助手</t-button>
          </div>
        </div>
      </t-tab-panel>

      <!-- 转让频道 -->
      <t-tab-panel value="transfer" label="转让频道">
        <div class="panel">
          <p class="transfer-hint">把频道主身份交给另一位成员。转让后你将降为普通成员。</p>
          <t-select v-model="transferTarget" class="transfer-select" filterable placeholder="选择新频道主（成员）">
            <t-option v-for="m in transferCandidates" :key="m.user_id" :value="m.user_id" :label="m.user_nickname || m.nickname" />
          </t-select>
          <p v-if="transferCandidates.length === 0" class="transfer-empty">暂无其他可转让的成员</p>
          <div class="transfer-ops">
            <t-button theme="primary" size="small" :loading="transferSaving" :disabled="!transferTarget" @click="onTransfer">
              {{ transferSaving ? '转让中…' : '确认转让' }}
            </t-button>
          </div>
        </div>
      </t-tab-panel>

      <!-- 解散频道 -->
      <t-tab-panel value="dissolve" label="解散频道">
        <div class="panel">
          <div class="dissolve-box">
            <p class="dissolve-warn">解散频道将<b>永久删除</b>频道全部数据（帖子、评论、成员关系、通知等），该操作不可恢复。</p>
            <t-input v-model.trim="dissolveConfirm" class="dissolve-input" placeholder="输入频道名称确认解散" maxlength="64" />
            <div class="dissolve-ops">
              <t-button theme="danger" size="small" :loading="dissolving" :disabled="dissolveConfirm !== (community?.name || '')" @click="onDissolve">
                {{ dissolving ? '解散中…' : '永久解散频道' }}
              </t-button>
            </div>
          </div>
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
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftIcon, ErrorCircleIcon, SoundMute1Icon } from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'
import { communityApi, feedStrategyApi, manageApi, roleApi, type Community, type JoinRequestItem, type Member, type MyRole, type OpLogItem, type RoleItem } from '@/api/community'
import { postApi, type PostItem } from '@/api/post'
import { toast } from '@/utils/toast'
import { formatTime, timeAgo } from '@/utils/time'
import { confirmDialog } from '@/utils/confirm'
import { ApiError } from '@/api/http'
import { loadErrorMessage } from '@/utils/error'
import ErrorState from '@/components/ErrorState.vue'
import { useInfiniteScroll } from '@/composables/useInfiniteScroll'

const route = useRoute()
const auth = useAuthStore()
const cid = Number(route.params.id)

const tab = ref<'members' | 'boards' | 'join' | 'mute' | 'posts' | 'blacklist' | 'roles' | 'ops' | 'ai' | 'transfer' | 'dissolve' | 'strategy'>('members')
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

// ---------- 板块管理 ----------
const boards = ref<Community['boards']>([])
const boardSaving = ref(false)
const boardForm = reactive({ id: 0, name: '', description: '', allow_post_role_ids: [] as number[] })
// 板块编辑弹窗表单（与新建表单分离）
const boardDialog = ref(false)
const boardEditForm = reactive({ id: 0, name: '', description: '', sort: 0, allow_post_role_ids: [] as number[] })

// ---------- 加入设置 ----------
const joinSetting = ref<number>(0)
const joinRequests = ref<JoinRequestItem[]>([])
const requestsTotal = ref(0)
const requestsLoading = ref(false)

// ---------- 全员禁言 ----------
const muteDays = ref(0)
const muteHours = ref(0)
const muteMinutes = ref(30)
const muteTotalHours = computed(() => muteDays.value * 24 + muteHours.value + muteMinutes.value / 60)
const muteSaving = ref(false)
const isAllMuted = computed(() => !!community.value?.all_muted_until)

// ---------- 帖子管理 ----------
const posts = ref<PostItem[]>([])
const postsPage = ref(1)
const postsLoading = ref(false)
const postBoardFilter = ref<number | undefined>(undefined)

// ---------- 黑名单 ----------
const blacklistMembers = ref<Member[]>([])
const blacklistPage = ref(1)
const blacklistTotal = ref(0)
const blacklistLoading = ref(false)
const blacklistKeyword = ref('')

// ---------- AI bot 管理 ----------
const aiNickname = ref('频道助手')
const aiSaving = ref(false)

// ---------- 转让 / 解散 ----------
const transferTarget = ref<number | undefined>(undefined)
const transferSaving = ref(false)
const dissolveConfirm = ref('')
const dissolving = ref(false)
const router = useRouter()

/** 转让候选成员：懒加载拉取全部成员（排除频道主本人与被拉黑者）。 */
const transferCandidates = ref<Member[]>([])
let transferLoaded = false
async function loadAllMembers() {
  if (transferLoaded) return
  transferLoaded = true
  try {
    const all: Member[] = []
    let page = 1
    for (;;) {
      const data = await communityApi.members(cid, page, 50)
      all.push(...data.items)
      if (all.length >= data.total || data.items.length === 0) break
      page += 1
    }
    transferCandidates.value = all.filter((m) => m.user_id !== auth.user?.id && !m.is_blocked && m.member_type !== 0)
  } catch { /* 加载失败则保持已加载的部分 */ }
}

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
    boards.value = community.value.boards
    joinSetting.value = community.value.join_setting
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

// ---------- 板块管理 ----------
async function loadBoards() {
  try {
    // 管理后台：包含已关闭板块（以便重新启用）
    boards.value = await communityApi.boards(cid, true)
  } catch { /* ignore */ }
}

async function onCreateBoard() {
  if (!boardForm.name.trim()) {
    toast('请填写板块名称', 'error')
    return
  }
  boardSaving.value = true
  try {
    await communityApi.createBoard(cid, {
      name: boardForm.name.trim(),
      description: boardForm.description.trim(),
      allow_post_role_ids: boardForm.allow_post_role_ids,
    })
    toast('板块已创建', 'success')
    boardForm.name = ''
    boardForm.description = ''
    boardForm.allow_post_role_ids = []
    await loadBoards()
  } catch (e) {
    toast(e instanceof Error ? e.message : '创建失败', 'error')
  } finally {
    boardSaving.value = false
  }
}

function openBoardEdit(b: Community['boards'][number]) {
  boardEditForm.id = b.id
  boardEditForm.name = b.name
  boardEditForm.description = b.description
  boardEditForm.sort = b.sort
  boardEditForm.allow_post_role_ids = [...b.allow_post_role_ids]
  boardDialog.value = true
}

/** 保存板块编辑（名称/简介/发帖身份组/排序）。 */
async function onSaveBoard() {
  if (!boardEditForm.name.trim()) {
    toast('请填写板块名称', 'error')
    return
  }
  boardSaving.value = true
  try {
    await communityApi.updateBoard(cid, boardEditForm.id, {
      name: boardEditForm.name.trim(),
      description: boardEditForm.description.trim(),
      sort: boardEditForm.sort,
      allow_post_role_ids: boardEditForm.allow_post_role_ids,
    })
    toast('板块已保存', 'success')
    boardDialog.value = false
    await loadBoards()
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    boardSaving.value = false
  }
}

/** 板块排序：上移/下移（按当前展示顺序重新编号 sort，避免同值/间隔导致交换无效）。 */
async function onMoveBoard(b: Community['boards'][number], dir: 'up' | 'down') {
  const idx = boards.value.findIndex((x) => x.id === b.id)
  const targetIdx = dir === 'up' ? idx - 1 : idx + 1
  if (targetIdx < 0 || targetIdx >= boards.value.length) return
  // 本地重排数组，得到新顺序
  const next = [...boards.value]
  const tmp = next[idx]
  next[idx] = next[targetIdx]
  next[targetIdx] = tmp
  // 按新顺序重新编号 sort（0,1,2,...），保证严格递增、无重复
  boardSaving.value = true
  try {
    for (let i = 0; i < next.length; i++) {
      if (next[i].sort !== i) {
        await communityApi.updateBoard(cid, next[i].id, { sort: i })
      }
    }
    await loadBoards()
    toast('排序已更新', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '排序失败', 'error')
  } finally {
    boardSaving.value = false
  }
}

async function onCloseBoard(b: Community['boards'][number]) {
  if (!(await confirmDialog('关闭板块', `确定关闭板块「${b.name}」？其帖子将不再对外展示。`))) return
  try {
    await communityApi.updateBoard(cid, b.id, { status: 2 })
    await loadBoards()
    toast('板块已关闭', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function onReopenBoard(b: Community['boards'][number]) {
  try {
    await communityApi.updateBoard(cid, b.id, { status: 0 })
    await loadBoards()
    toast('板块已重新启用', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

// ---------- 加入设置 ----------
async function onJoinSettingChange(v: number) {
  try {
    await communityApi.update(cid, { join_setting: v })
    toast('加入设置已更新', 'success')
    if (v === 1) await loadRequests(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '保存失败', 'error')
    joinSetting.value = community.value?.join_setting ?? 0
  }
}

async function loadRequests(page: number) {
  requestsLoading.value = true
  try {
    const data = await communityApi.joinRequests(cid, page, 20)
    // 只保留待审核申请（status=0）：已通过/已驳回的不再展示，避免"点了没反应"
    const pending = data.items.filter((r) => r.status === 0)
    joinRequests.value = page === 1 ? pending : [...joinRequests.value, ...pending]
    requestsTotal.value = data.total
  } catch { /* ignore */ } finally {
    requestsLoading.value = false
  }
}

async function onHandleRequest(r: JoinRequestItem, approve: boolean) {
  try {
    await communityApi.handleJoinRequest(cid, r.id, approve)
    toast(approve ? '已通过' : '已驳回', 'success')
    // 本地立即移除该项 + 重拉待审列表，双保险
    joinRequests.value = joinRequests.value.filter((x) => x.id !== r.id)
    await loadRequests(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

// ---------- 全员禁言 ----------
async function onAllMute(enable: boolean) {
  const totalHours = muteTotalHours.value
  if (enable && (!Number.isFinite(totalHours) || totalHours <= 0 || totalHours > 720)) {
    toast('禁言时长需大于 0 且不超过 720 小时（30 天）', 'error')
    return
  }
  const tip = enable
    ? `确定全员禁言 ${muteDays.value} 天 ${muteHours.value} 小时 ${muteMinutes.value} 分钟？期间所有成员不能发帖/评论（点赞不受影响）。`
    : '确定解除全员禁言？'
  if (!(await confirmDialog('全员禁言', tip))) return
  muteSaving.value = true
  try {
    community.value = await communityApi.allMute(cid, enable ? Math.round(totalHours * 60) / 60 : 0)
    toast(enable ? '已全员禁言' : '已解除全员禁言', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    muteSaving.value = false
  }
}

// ---------- 帖子管理 ----------
const postsCursor = ref<string | null>(null)
const postsHasMore = ref(false)
async function loadPosts(page: number, append = false) {
  if (postsLoading.value) return
  postsLoading.value = true
  try {
    const data = await postApi.feed(cid, 'latest', append ? postsCursor.value : null, 20, postBoardFilter.value)
    posts.value = append ? [...posts.value, ...data.items] : data.items
    postsPage.value = page
    postsCursor.value = data.next_cursor
    postsHasMore.value = data.has_more
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载帖子失败', 'error')
  } finally {
    postsLoading.value = false
  }
}

async function onMovePost(p: PostItem, boardId: number) {
  if (boardId === p.board_id) return
  try {
    await postApi.move(p.id, boardId)
    toast('帖子已移动', 'success')
    await loadPosts(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '移动失败', 'error')
  }
}

async function onDeletePost(p: PostItem) {
  if (!(await confirmDialog('删除帖子', `确定删除帖子「${p.title}」？该操作不可恢复。`))) return
  try {
    await postApi.remove(p.id)
    toast('帖子已删除', 'success')
    await loadPosts(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

// 帖子管理：滚动到底自动加载下一页
const postsScrollEnabled = computed(() => tab.value === 'posts' && postsHasMore.value && !postsLoading.value)
useInfiniteScroll({ enabled: postsScrollEnabled, load: () => loadPosts(postsPage.value + 1, true) })

// 成员管理：滚动到底自动加载下一页
const membersScrollEnabled = computed(() => tab.value === 'members' && membersHasMore.value && !membersLoading.value)
useInfiniteScroll({ enabled: membersScrollEnabled, load: () => loadMembers(membersPage.value + 1, true) })

// ---------- 黑名单 ----------
async function loadBlacklist(page: number, append = false) {
  if (blacklistLoading.value) return
  blacklistLoading.value = true
  try {
    const data = await communityApi.blacklist(cid, page, 50, blacklistKeyword.value.trim() || undefined)
    blacklistMembers.value = append ? [...blacklistMembers.value, ...data.items] : data.items
    blacklistPage.value = page
    blacklistTotal.value = data.total
  } catch (e) {
    toast(e instanceof Error ? e.message : '加载黑名单失败', 'error')
  } finally {
    blacklistLoading.value = false
  }
}

function onBlacklistSearch() {
  loadBlacklist(1)
}

async function onUnblockBlacklist(m: Member) {
  if (!(await confirmDialog('解除拉黑', `确定解除 ${m.user_nickname || m.nickname} 的拉黑？其可重新加入频道。`))) return
  try {
    await manageApi.unblock(cid, m.user_id)
    toast('已解除拉黑', 'success')
    await loadBlacklist(1)
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

// ---------- AI bot 管理 ----------
async function onEnsureAi() {
  if (!aiNickname.value.trim()) {
    toast('请填写助手昵称', 'error')
    return
  }
  aiSaving.value = true
  try {
    await communityApi.ensureAiAssistant(cid, aiNickname.value.trim())
    toast('AI 助手已启用', 'success')
  } catch (e) {
    toast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    aiSaving.value = false
  }
}

// ---------- 转让 / 解散 ----------
async function onTransfer() {
  if (!transferTarget.value) {
    toast('请选择新频道主', 'error')
    return
  }
  const t = transferCandidates.value.find((m) => m.user_id === transferTarget.value)
  if (!(await confirmDialog('转让频道', `确定把频道主转让给 ${t?.user_nickname || t?.nickname}？转让后你将降为普通成员。`))) return
  transferSaving.value = true
  try {
    await communityApi.transfer(cid, transferTarget.value)
    toast('频道已转让', 'success')
    transferTarget.value = undefined
    await Promise.all([reloadRoles(), reloadMembers(), loadOps(1)])
  } catch (e) {
    toast(e instanceof Error ? e.message : '转让失败', 'error')
  } finally {
    transferSaving.value = false
  }
}

async function onDissolve() {
  if (!(await confirmDialog('解散频道', `确定永久解散频道「${community.value?.name}」？所有数据将无法恢复。`))) return
  dissolving.value = true
  try {
    await communityApi.dissolve(cid)
    toast('频道已解散', 'success')
    router.push('/')
  } catch (e) {
    toast(e instanceof Error ? e.message : '解散失败', 'error')
  } finally {
    dissolving.value = false
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

// 各 tab 懒加载：首次切到才拉对应数据（板块/加入审核/帖子/黑名单/策略）
const loadedTabs = new Set<string>(['members', 'roles', 'ops'])
watch(tab, (t) => {
  if (loadedTabs.has(t)) return
  loadedTabs.add(t)
  if (t === 'strategy') loadStrategy()
  else if (t === 'join') loadRequests(1)
  else if (t === 'posts') loadPosts(1)
  else if (t === 'blacklist') loadBlacklist(1)
  else if (t === 'boards') loadBoards()
  else if (t === 'transfer') loadAllMembers()
})

// 帖子管理：切换板块过滤时重拉首屏
watch(postBoardFilter, () => {
  if (tab.value === 'posts') loadPosts(1)
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
/* ===== 板块管理 ===== */
.board-form {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--td-component-border);
  margin-bottom: var(--sp-2);
}
.board-name-input {
  flex: 1;
  min-width: 140px;
}
.board-role-select {
  width: 220px;
}
.board-form-hint {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.board-card {
  padding: var(--sp-3) 0;
  border-bottom: 1px dashed var(--td-component-border);
}
.board-card:last-child {
  border-bottom: none;
}
.board-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.board-name {
  font-weight: 600;
}
.board-desc {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.board-ops {
  margin-top: var(--sp-2);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.board-edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.board-edit-field {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.board-edit-label {
  font-size: var(--fs-caption);
  color: var(--td-text-color-secondary);
}
/* ===== 加入设置 ===== */
.join-row {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
  flex-wrap: wrap;
}
.join-label {
  width: 96px;
  font-size: var(--fs-body);
  font-weight: 600;
  padding-top: 4px;
}
.join-hint {
  margin: var(--sp-3) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.divider {
  height: 1px;
  background: var(--td-component-border);
  margin: var(--sp-4) 0;
}
.join-requests {
  display: flex;
  flex-direction: column;
}
.join-req-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
}
.join-req-count {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.join-req-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--td-component-border);
}
.join-req-row:last-child {
  border-bottom: none;
}
.join-req-name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
}
.join-req-time {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
/* ===== 全员禁言 ===== */
.mute-status {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.mute-label {
  font-weight: 600;
}
.mute-form {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.mute-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.mute-num {
  width: 72px;
}
.mute-unit {
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.mute-hint {
  margin: var(--sp-3) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
/* ===== 帖子管理 ===== */
.posts-toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}
.post-board-filter {
  width: 200px;
}
.post-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--td-component-border);
}
.post-row:last-child {
  border-bottom: none;
}
.post-info {
  flex: 1;
  min-width: 0;
}
.post-title {
  font-weight: 600;
  color: var(--td-text-color-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.post-meta {
  margin-top: 2px;
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.post-ops {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-shrink: 0;
}
.post-move-select {
  width: 130px;
}
.load-more-posts {
  margin-top: var(--sp-3);
}
/* ===== 黑名单 ===== */
.blacklist-toolbar {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}
.blacklist-search {
  flex: 1;
  min-width: 0;
}
.load-more-blacklist {
  margin-top: var(--sp-3);
}
/* ===== AI bot 管理 ===== */
.ai-hint {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.ai-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.ai-nickname {
  width: 220px;
}
/* ===== 转让 / 解散 ===== */
.transfer-hint,
.dissolve-warn {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--td-text-color-secondary);
  line-height: 1.6;
}
.dissolve-warn {
  color: var(--td-error-color);
}
.transfer-select {
  width: 100%;
  max-width: 360px;
}
.transfer-empty {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-caption);
  color: var(--td-text-color-placeholder);
}
.transfer-ops,
.dissolve-ops {
  margin-top: var(--sp-4);
}
.dissolve-input {
  max-width: 320px;
}
</style>
