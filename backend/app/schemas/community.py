"""频道/版块/成员/身份组相关 Pydantic 模型。"""
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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


class UpdateCommunityStatusRequest(BaseModel):
    status: int = Field(ge=0, le=2)  # 0正常 1关闭 2违规封禁


# ---------- 身份组（阶段 4） ----------


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    color: str = Field(default="#1a73e8")
    level: int = Field(default=0, ge=0)  # 等级身份门槛（仅 is_level_role 生效）
    perms: list[str] = Field(default_factory=list)
    is_level_role: bool = False  # 等级身份：成员活跃等级 ≥ level 自动授予

    @field_validator("color")
    @classmethod
    def _normalize_color(cls, v: str) -> str:
        """宽容颜色格式：rgb()/rgba()/#RRGGBBAA 统一归一化为 #RRGGBB。"""
        v = v.strip()
        m = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", v, re.IGNORECASE)
        if m:
            return "#" + "".join(f"{int(x) & 255:02x}" for x in m.groups())
        m = re.fullmatch(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?", v)
        if m:
            return "#" + m.group(1).lower()
        raise ValueError("颜色格式不正确（支持 #RRGGBB 或 rgb(r,g,b)）")


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    color: str | None = Field(default=None)
    level: int | None = Field(default=None, ge=0)
    perms: list[str] | None = None
    is_level_role: bool | None = None

    @field_validator("color")
    @classmethod
    def _normalize_color(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return CreateRoleRequest._normalize_color(v)


class MoveRoleRequest(BaseModel):
    direction: str = Field(pattern="^(up|down)$")  # 上移/下移（排序即权重）


class AssignRoleRequest(BaseModel):
    role_id: int | None = None  # None = 清除身份


class RoleOut(BaseModel):
    id: int
    community_id: int
    name: str
    color: str
    level: int
    sort: int
    perms: list
    is_default: bool
    is_level_role: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OpLogOut(BaseModel):
    id: int
    action: str
    target_type: str
    target_id: int | None
    detail: dict | None
    request_params: dict | None = None
    response_result: dict | None = None
    created_at: datetime
    operator_nickname: str = ""  # 视图增强

    model_config = {"from_attributes": True}


# ---------- 响应 ----------


class BoardOut(BaseModel):
    id: int
    community_id: int
    name: str
    description: str
    sort: int
    allow_post_role_ids: list = Field(default_factory=list)  # 由 board_role_perms 关系表聚合回填
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
    level: int = 1                       # 活跃等级（互动增长）
    join_time: datetime
    shutup_expire_at: datetime | None
    is_blocked: bool
    role_id: int | None = None   # 身份组（阶段 4）
    role_name: str = ""
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
