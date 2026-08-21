"""话题接口（文档⑩话题标签管理，P0）：列表/详情/创建/编辑/删除/热度排序。

- 列表默认按热度降序（heat_value desc），可选 sort=latest 按创建倒序
- 创建 upsert（同名返回已有）；编辑/删除需频道主或管理员（member_manage 权限）
- 删除软删（status=1），帖子关联的话题随之下架
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import require_perms
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.topic import Topic
from app.models.user import User
from app.services.post_service import _require_member

router = APIRouter(tags=["topics"])


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    description: str = Field(default="", max_length=255)
    cover_url: str = Field(default="", max_length=255)
    rules: str = Field(default="", max_length=500)


class UpdateTopicRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=255)
    cover_url: str | None = Field(default=None, max_length=255)
    rules: str | None = Field(default=None, max_length=500)


class TopicOut(BaseModel):
    id: int
    community_id: int
    name: str
    description: str = ""
    cover_url: str = ""
    rules: str = ""
    post_count: int = 0
    heat_value: int = 0
    status: int = 0
    created_at: object | None = None

    model_config = {"from_attributes": True}


@router.get("/communities/{community_id}/topics")
def list_topics(
    community_id: int,
    sort: str = Query("hot", pattern="^(hot|latest)$"),
    db: Session = Depends(get_db),
):
    """频道话题列表（公开可见），默认按热度降序。"""
    stmt = select(Topic).where(Topic.community_id == community_id, Topic.status == 0)
    stmt = stmt.order_by(Topic.heat_value.desc(), Topic.id.desc()) if sort == "hot" else stmt.order_by(Topic.id.desc())
    topics = db.execute(stmt).scalars().all()
    return ok(data=[TopicOut.model_validate(t) for t in topics])


@router.get("/communities/{community_id}/topics/{topic_id}")
def get_topic(
    community_id: int,
    topic_id: int,
    db: Session = Depends(get_db),
):
    """话题详情（公开可见）。"""
    topic = _get_topic(db, community_id, topic_id)
    return ok(data=TopicOut.model_validate(topic))


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
    topic = Topic(
        community_id=community_id,
        name=name,
        description=payload.description,
        cover_url=payload.cover_url,
        rules=payload.rules,
        creator_id=user.id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return ok(data=TopicOut.model_validate(topic), message="话题已创建")


@router.put("/communities/{community_id}/topics/{topic_id}")
def update_topic(
    community_id: int,
    topic_id: int,
    payload: UpdateTopicRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑话题（需 member_manage 权限）：名称/描述/封面/规则。"""
    topic = _get_topic(db, community_id, topic_id)
    require_perms(db, community_id, user, "member_manage")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        data["name"] = data["name"].strip().lstrip("#")
    for k, v in data.items():
        setattr(topic, k, v)
    db.commit()
    db.refresh(topic)
    return ok(data=TopicOut.model_validate(topic), message="话题已更新")


@router.delete("/communities/{community_id}/topics/{topic_id}")
def delete_topic(
    community_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除话题（软删，需 member_manage 权限）；关联帖子保留但 topic_id 置空。"""
    topic = _get_topic(db, community_id, topic_id)
    require_perms(db, community_id, user, "member_manage")
    topic.status = 1
    from app.models.post import Post

    db.execute(update(Post).where(Post.topic_id == topic.id).values(topic_id=None))
    db.commit()
    return ok(message="话题已删除")


def _get_topic(db: Session, community_id: int, topic_id: int) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None or topic.community_id != community_id or topic.status != 0:
        raise NotFoundError("话题不存在")
    return topic
