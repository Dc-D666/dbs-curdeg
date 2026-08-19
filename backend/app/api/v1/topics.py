"""话题接口：频道话题列表 / 创建（upsert，阶段 3 收尾）。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.community import Community
from app.models.topic import Topic
from app.models.user import User
from app.services.post_service import _require_member

router = APIRouter(tags=["topics"])


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class TopicOut(BaseModel):
    id: int
    community_id: int
    name: str
    created_at: object | None = None

    model_config = {"from_attributes": True}


@router.get("/communities/{community_id}/topics")
def list_topics(community_id: int, db: Session = Depends(get_db)):
    """频道话题列表（公开可见）。"""
    topics = db.execute(
        select(Topic).where(Topic.community_id == community_id).order_by(Topic.id.desc())
    ).scalars().all()
    return ok(data=[TopicOut.model_validate(t) for t in topics])


@router.post("/communities/{community_id}/topics")
def create_topic(
    community_id: int,
    payload: CreateTopicRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建话题（upsert：同名返回已有；需频道成员）。"""
    _require_member(db, community_id, user.id)
    name = payload.name.strip().lstrip("#")
    existing = db.execute(
        select(Topic).where(Topic.community_id == community_id, Topic.name == name)
    ).scalar_one_or_none()
    if existing:
        return ok(data=TopicOut.model_validate(existing), message="话题已存在")
    topic = Topic(community_id=community_id, name=name, creator_id=user.id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return ok(data=TopicOut.model_validate(topic), message="话题已创建")
