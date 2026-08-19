"""仿腾讯频道 API 入口（骨架）。

后续按模块拆分：
  app/api/auth.py         账号体系（注册/登录/JWT）
  app/api/community.py    频道/版块
  app/api/content.py      发帖/评论/点赞
  app/api/interact.py     关注/搜索/通知
  app/api/ai.py           AI 帮写/审核/问答
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="仿腾讯频道 API",
    version="0.1.0",
    description="Web + Android 双端共用接口",
)

# 开发期放开 CORS，上线前收紧为前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    """存活探针：nginx 与部署脚本用它判断服务是否正常。"""
    return {"status": "ok", "service": "channel-api", "version": "0.1.0"}


@app.get("/api/v1/ping")
def ping():
    """前后端连通性测试。"""
    return {"message": "pong"}
