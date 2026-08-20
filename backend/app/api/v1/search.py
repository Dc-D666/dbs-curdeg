"""搜索接口（阶段 4）：关键词搜索（高亮）+ 热门搜索词。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_optional
from app.core.ratelimit import rate_limit
from app.core.response import ok
from app.db import get_db
from app.models.user import User
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/posts")
def search_posts(
    q: str = Query(..., min_length=1, max_length=64, description="搜索关键词"),
    community_id: int | None = Query(None, description="限定频道（可选）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    _=Depends(rate_limit("search_posts", limit=60, window=60)),
):
    """关键词搜索帖子（游客可用），标题/摘要带 <em class="hl"> 高亮。"""
    return ok(
        data=search_service.search_posts(
            db, q, page, page_size,
            current_user_id=user.id if user else None,
            community_id=community_id,
        )
    )


@router.get("/hot")
def hot_keywords(
    db: Session = Depends(get_db),
    _=Depends(rate_limit("search_hot", limit=120, window=60)),
):
    """热门搜索词（近 7 天 TOP10）。"""
    return ok(data=search_service.hot_keywords(db))
