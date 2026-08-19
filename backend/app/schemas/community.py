"""频道/版块/成员/身份组相关 Pydantic 模型。"""
from datetime import datetime

from pydantic import BaseModel, Field

# ---------- 请求 ----------


class CreateCommunityRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    profile: str = Field(default="", max_length=255)
    join_setting: int = Field(default=0, ge=0, le=2)  # 0自由 1审核 2邀请


class UpdateCommunityRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    profile: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=255)
    cover_url: str | None = Field(default=None, max_length=255)
    join_setting: int | None = Field(default=None, ge=0, le=2)
    visitor_interact_switch: bool | None = None


class CreateBoardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=255)
    sort: int = Field(default=0)
    allow_post_role_ids: list[int] = Field(default_factory=list)
    allow_anonymous: bool = False


class UpdateBoardRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    sort: int | None = None
    allow_post_role_ids: list[int] | None = None
    allow_anonymous: bool | None = None
    status: int | None = Field(default=None, ge=0, le=2)


class HandleJoinRequest(BaseModel):
    approve: bool  # True=通过 False=驳回


# ---------- 响应 ----------


class BoardOut(BaseModel):
    id: int
    community_id: int
    name: str
    description: str
    sort: int
    allow_post_role_ids: list
    allow_anonymous: bool
    status: int

    model_config = {"from_attributes": True}


class CommunityOut(BaseModel):
    id: int
    number: str
    name: str
    profile: str
    avatar_url: str
    cover_url: str
    member_count: int
    post_count: int
    join_setting: int
    visitor_interact_switch: bool
    owner_id: int
    status: int
    created_at: datetime
    # 视图增强字段
    is_member: bool = False
    my_member_type: int | None = None
    boards: list[BoardOut] = []

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    id: int
    community_id: int
    user_id: int
    nickname: str
    member_type: int
    join_time: datetime
    shutup_expire_at: datetime | None
    is_blocked: bool
    # 冗余用户信息
    username: str = ""
    user_nickname: str = ""
    avatar_url: str = ""

    model_config = {"from_attributes": True}


class JoinRequestOut(BaseModel):
    id: int
    community_id: int
    user_id: int
    status: int
    created_at: datetime
    username: str = ""
    user_nickname: str = ""

    model_config = {"from_attributes": True}
