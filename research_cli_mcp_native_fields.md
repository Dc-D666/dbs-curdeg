# tencent-channel-cli / MCP 网关原生字段调研笔记

> 调研日期：2026-08-19 ｜ 方式：bot token 失效后走 QQ 扫码鉴权，通过本地转发代理抓取 CLI 与 MCP 网关的完整请求/响应
> 本文件为原始证据与对照记录，供课设与技术选型参考。

## 0. 鉴权与工具链事实

- CLI：`tencent-channel-cli` v1.0.6（Go 二进制，npm 分发），低于 1.0.6 需升级。
- 登录：`login --json` 取二维码 + `verification_uri`，`login poll-token --json` 轮询拿令牌；凭证写入**系统密钥链**（Windows Credential Manager），`.env` 只是降级存储。
- 用户提供的 bot token `bot:v1_-Q1Qw6E-...` 经网关验证返回 **retcode 130001 "api info not exist"**（CLI 归类为 8011 未登录）——即 token 无效（可能是复制截断/过期/未开通 MCP 网关）。扫码登录后拿到的是**另一个** `bot:v1_...` 令牌（106 字符）。
- **MCP 网关端点**：`https://graph.qq.com/mcp_gateway/open_platform_agent_mcp/mcp`
- **认证头**：`Authorization: Bearer bot:v1_...`（env 可覆盖：`QQ_AI_CONNECT_MCP_URL` / `QQ_AI_CONNECT_MCP_ENV` / `QQ_AI_CONNECT_DEVICE_ID`）
- **传输协议**：HTTP POST + JSON-RPC 2.0，**直接 `tools/call`，无 initialize 握手**；`initialize`/`tools/list` 被网关禁用（返回 8011 "api info not exist"）。
- 工具名 **snake_case**（如 `get_my_join_guild_info`），参数 **camelCase**（如 `guildId`、`isShortLink`）。响应 `content[].text` 为可读文本 + `structuredContent` 为原生结构化数据 + `_meta.AdditionalFields.outputFieldSchema` 为 **protobuf 字段白名单 schema**。
- CLI 内置 `schema <domain.action>` 可查询每个命令参数定义（type/required/enum/default/示例），等价于 MCP 工具注册表。

## 1. CLI 命令面（= MCP 工具注册表）

- **feed 域**（帖子与内容，24 个）：get-guild-feeds / get-channel-timeline-feeds / get-feed-detail / get-feed-comments / search-guild-feeds / get-feed-share-url / get-notices / get-next-page-replies / publish-feed / del-feed(高危) / do-comment / do-reply / do-like / do-feed-prefer / alter-feed / top-feed / set-feed-essence / push-essence-feed / move-feed / quick-publish / search-and-comment / delete-and-mute(高危) / latest-feeds-detail / hot-feeds-detail
- **manage 域**（频道与成员，38 个）：get-guild-info / get-my-join-guild-info / get-user-info / get-guild-member-list / guild-member-search / get-guild-channel-list / search-guild-content / get-join-guild-setting / get-guild-share-url / get-share-info / kick-guild-member(高危) / modify-member-shut-up / update-guild-info / modify-guild-number / create-guild-role-group / modify-guild-role-group / add-role-members / remove-role-members(高危) / join-guild / create-channel / delete-channel(高危) / modify-channel / upload-guild-avatar / create-theme-private-guild / add-admin / remove-admin(高危) / push-group-dm-msg / update-join-guild-setting / leave-guild(高危) / notices-on / notices-off / notices-status / check-notices / subscribe-notices / unsubscribe-notices / check-new-notices / get-recent-notices / deal-notice / notify-daemon / search-and-join

## 2. 各接口原生字段（structuredContent）与 CLI 丢弃对照

### 2.1 get_guild_info（频道资料）
原生：
- `uint64GuildId`、`msgGuildInfo`{ `bytesGuildName`(base64)、`bytesGuildNumber`(base64)、`bytesProfile`(base64)、`uint32MemberNum`、`uint32VistorInteractionAllSwitch`、`uint64CreateTime`、`uint64FaceSeq` }、`guildUserInfo`{ `uint32IsMember`、`uint32Role`、`uint64JoinTime`、`uint64Tinyid` }、`bytesJoinGuildSig`(base64)、`uint32Result`

CLI 保留：name/guild_number/member_count/profile/create_time(+human)/avatar_url(由 faceSeq 计算)/share_url(额外调 get_share_url)/guild_type(派生)
**CLI 丢弃**：`uint32VistorInteractionAllSwitch`(访客互动总开关)、`bytesJoinGuildSig`(加入签名)、`guildUserInfo.uint32IsMember`(当前账号是否为成员)

### 2.2 get_guild_channel_list（版块列表）
原生：`guildInfoList[]`{ `guildId`、`channelList[]`{ `channelId`、`channelName`(base64) } }
CLI 基本全保留；注意默认只回「全部」一个版块。

### 2.3 get_guild_member_list（成员列表）
原生：
- 按身份组分页：`roleMemberList[]`{ `roleId`、`name`(base64)、`rptMemberList[]`{ `bytesMemberName`、`bytesNickName`、`location`{country/countryId/province/provinceId/city/cityId/cityZone/cityZoneId}、`uint32Gender`(1男2女)、`uint32Role`(ROLE_OWNER/ROLE_ADMIN/…)、`uint64JoinTime`、`uint64Tinyid`、`uint32Type`(1机器人/2 AI 成员) } }、`rptMsgNormalMemberList[]`、`rptMsgRobotList[]`
- 分页：`nextRoleIdIndex`、`bytesTransBuf`(base64 分页游标)、`uint32AllIsFinished`、`uint32IsFinished`、`uint32NormalUserNum`、`uint32RobotNum`

CLI 保留：按 频道主/管理员/成员/AI成员/机器人 分类汇总，gender→男/女，joinTime→北京时间
**CLI 丢弃**：全部 `location` 字段、`uint32Type` 细分、`bytesTransBuf`/`nextRoleIdIndex` 分页游标、normal/robot 数量、roleId

### 2.4 get_user_info（用户资料）
原生：`msgUserInfo`{ `bytesCountry`、`bytesMemberName`、`bytesNickName`、`bytesProvince`(均 base64)、`uint32Gender`、`uint64MemberTinyid` }
CLI 保留：country→中国、province→宁夏、gender→女、member_name/nickname/global_nickname（解码）
**CLI 丢弃**：`uint64MemberTinyid`（自身 tinyid）

### 2.5 get_guild_feeds / get_feed_detail（帖子）
原生（protobuf schema 全字段见 mcp_capture_6.json / _4.json）：
- `id`、`feedType`、`createTime`、`commentCount`、`totalPrefer.preferCount`
- `title`/`contents`：`contents[]` 富文本分片 { `type`(1文本/2@/3链接/4表情/8话题)、`textContent.text`、`atContent.user{id,nick,icon}`、`urlContent{url,displayText,type}`、`emojiContent{id,name,url,type}`、`topicContent{topicId,topicName,schema,showStatus}`、`patternId` }；`isMarkdown`、`sourceMarkdown`
- `images[]`{ `picUrl`、`width`、`height`、`picId`、`vecImageUrl[]`{`levelType`(1/2/3→m/c/b 三档)、`url`、`width`、`height`} }、`cover`、`videos[]`{`playUrl`、`duration`、`fileId`、`cover`}
- `poster`{`id`、`nick`、`icon.iconUrl`}、`share.channelShareInfo.channelSign`{`guildId`,`channelId`}、`channelInfo`{`sign`,`name`,`guildName`,`guildNumber`}
- `essence.timestamp/tinyid`（精华）、`topicContents[]`

CLI 保留：title/content 纯文本、author/author_id、channel_name/guild_name、comment_count/prefer_count、create_time(+raw)、feed_id、share_url(额外调用)
**CLI 丢弃**：images/cover/videos、富文本 type 结构、poster.icon、channelSign、essence、topicContents、totalPrefer 明细

### 2.6 get_feed_comments（评论）
原生：`attachInfo`（URL 编码 JSON，含 commentRankSys 排序态、total_cmt_and_rep_count）、`isFinish`
说明：评论走 rank 排序 + 分页游标；CLI 转成 attach_info 透传翻页。真实评论样例少（该测试频道评论为空），未拿到评论对象本体结构。

### 2.7 search_guild_content（全局搜索，scope=feed）
原生：`sessionInfo`(base64/gzip 会话游标)、`tabContentResult.resultItems[]`{ `id`、`name` }
CLI 保留：feed_id + title + has_more + next_page_token
**CLI 丢弃**：会话原始游标、其他 tab 结构

### 2.8 search_guild_feeds（频道内帖子搜索）⭐ AI 相关
原生：`aiSearchInfo`{ `guildUrl` }、`highlightWords[]`（如 ["文案"]）、`unionResult`{ `guildFeeds[]`{ `feedId`、`title`、`content`、`feedType`、`channelId`、`guildId`、`createTime`、`tinyId`、`nickName`、`BytesAvatarMeta`(base64)、`oriContents`(base64 **原始 protobuf**) }、`feedCookie`(base64 分页)、`feedIsEnd`、`feedTotal`、`guildName`、`guildNumber` }
**CLI 丢弃**：`highlightWords`(搜索高亮词)、`aiSearchInfo`、`oriContents`(原始二进制)、`BytesAvatarMeta`、`feedCookie` 等

### 2.9 get_share_url / get_share_info（分享短链）
原生：`url` + `shareInfo`(可读文本) ｜ `shareGuildInfo`{`guildId`,`guildName`,`guildNumber`}
机制：`pd.qq.com/s/<code>` 短链 → 解析为频道三要素；`isShortLink=true` 请求短链。

### 2.10 通知系统
- `notices-on/off/status`、`subscribe-notices`、`check-new-notices`(增量)、`get-recent-notices`(本地)、`deal-notice`(处理加入申请等)、`notify-daemon`(后台常驻)
- 未开启通知时 `check-new-notices` 返回校验错误（需先 notices-on，属写操作，调研未执行）

## 3. 关键结论（课设可直接引用）

1. **底层是 protobuf + 类 BFF 网关**：所有业务字段以 `uint32_/uint64_/bytes_` protobuf 命名 + base64 bytes 传输，网关外层再做 JSON 化与字段白名单（outputFieldSchema 可见）。CLI 做 base64 解码、snake→camel、时间格式化、派生 URL。
2. **"字段丢弃"确认发生在 CLI 层**：CLI 面向 Agent 消费，做的是**摘要化**——图片/视频/富文本结构/定位/分页游标/高亮词/原始二进制等被过滤；想拿全量原生字段需直连网关（但 `tools/list`/`initialize` 被禁用，只能按已知工具名 `tools/call`）。
3. **帖子数据模型**是"富文本分片(typed content blocks) + 多档图片(levelType 1/2/3) + 视频 + 话题 + 精华 + 分享签名"结构，可直接映射到自研库表设计。
4. **AI 痕迹**：`uint32Type=2` 成员被归类为"频道助手/AI 成员"；搜索返回带 `highlightWords` 与 `aiSearchInfo`（AI 检索增强）；CLI 工具里有"问答自动回复/内容巡检"能力（见 skill 参考文档）。
5. 传输上 CLI 直接 POST JSON-RPC `tools/call`，无 SSE/会话，网关无状态——自研服务可参考该"单请求往返"模式简化实现。

## 4. 原始证据文件（本目录）
- `mcp_capture_0.json` get_guild_info｜`mcp_capture_2.json` 版块列表｜`mcp_capture_3.json` 成员列表｜`mcp_capture_4.json` 帖子列表｜`mcp_capture_6.json` 帖子详情｜`mcp_capture_8.json` 评论｜`mcp_capture_9.json` 用户资料｜`mcp_capture_10.json` 全局搜索｜`mcp_capture_11.json` 频道内搜索｜`mcp_capture_12/13.json` 分享解析/官方频道
- `cli_*.json` 对应 CLI 汇总输出（对照用）
- `captured_token.txt`（有效 token，敏感，勿外传）
