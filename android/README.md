# ChannelApp（Android 端 · 阶段 9 脚手架）

仿腾讯频道课设的 Android 客户端：**Kotlin + Jetpack Compose + Material3 + Retrofit**，
与 Web 端共用同一套 FastAPI API（https://guild.weaxi.cn/api/v1）。

## 已实现（代码层面，需 Android Studio 验证构建）

- **工程**：AGP 8.5.2 + Kotlin 2.0.21 + Compose BOM 2024.09（minSdk 26 / targetSdk 35）
- **数据层**：Retrofit + Gson（snake_case 映射）、OkHttp 拦截器自动带 Bearer token、
  DataStore 持久化 access/refresh token
- **页面**：登录/注册（邮箱验证码）→ 首页帖子流（最新/热门 + 无限加载）→
  帖子详情（富文本分片渲染/图片/评论/点赞）→ 通知中心（未读角标）→ 我的（资料/退出）

## 如何构建运行

1. 安装 Android Studio（Ladybug 或更新）→ Open → 选择本 `android/` 目录
2. Gradle 同步（首次会自动下载依赖，需科学上网或配置镜像）
3. `app` 配置里改 `BASE_URL`（`data/ApiClient.kt`）：线上 `https://guild.weaxi.cn/api/v1/`，
   本地调试 `http://10.0.2.2:8000/api/v1/`（需在 manifest 开 `usesCleartextTraffic`）
4. 连接模拟器/真机 → Run

## 待办（阶段 9~10 收尾）

- [ ] Android Studio 首次构建验证 + 修编译错误
- [ ] WebSocket 通知实时化（okhttp WebSocket 接 `/ws`，当前为进入页面拉取）
- [ ] 发帖页（RichEditor 简化版 + AI 帮写）、频道页、搜索页
- [ ] AI 问答浮窗
- [ ] APK 打包 + 双端联调验收

## 说明

- 本项目目录**不参与服务器部署**（Docker build context 仅 backend/frontend/deploy），
  push 不会影响线上站点。
- 提交时注意 android/.gitignore 已排除 build/.gradle/local.properties。
