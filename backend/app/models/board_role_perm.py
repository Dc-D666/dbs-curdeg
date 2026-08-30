"""版块发帖身份组白名单（08-29 二轮审查规范化：boards.allow_post_role_ids JSON → 关系表）。

原 JSON 数组存身份组 ID 列表：无法挂外键（role 删除后悬空 ID）、无法反查
（"该身份组被哪些版块引用"）。拆关系表后：
- 引用完整性：role 删除 → 级联清理引用行（ondelete CASCADE）
- 复合主键 (board_id, role_id) 天然防重
- 版块无白名单行 = 所有人可发帖（与原 allow_post_role_ids=[] 语义一致）
"""
from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BoardRolePerm(Base):
    __tablename__ = "board_role_perms"

    board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
