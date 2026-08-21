"""帖子媒体附件业务（文档⑦，P0）：创建/列表/删除。

附件记录携带完整元数据（尺寸/大小/时长/排序），与 posts.images(展示 URL) 互补。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import NotFoundError, PermissionError_
from app.models.attachment import Attachment
from app.models.member import MEMBER_ADMIN, MEMBER_OWNER, Member
from app.models.post import Post, POST_STATUS_NORMAL
from app.models.user import User


def create_attachment(
    db: Session,
    post: Post,
    user: User,
    *,
    media_type: int,
    url: str,
    thumb_url: str = "",
    width: int = 0,
    height: int = 0,
    file_size: int = 0,
    duration: int = 0,
) -> Attachment:
    """绑定附件到帖子（需为频道成员，作者或管理者）。"""
    member = db.execute(
        select(Member).where(Member.community_id == post.community_id, Member.user_id == user.id)
    ).scalar_one_or_none()
    is_admin = member is not None and member.member_type in (MEMBER_OWNER, MEMBER_ADMIN)
    if post.author_id != user.id and not is_admin:
        raise PermissionError_("无权给该帖子添加附件")
    # 排序号用 MAX+1，避免并发下 list 计数产生重复序号
    next_sort = db.execute(
        select(func.max(Attachment.sort_order)).where(Attachment.post_id == post.id)
    ).scalar_one()
    att = Attachment(
        post_id=post.id,
        media_type=media_type,
        url=url,
        thumb_url=thumb_url,
        width=width,
        height=height,
        file_size=file_size,
        duration=duration,
        sort_order=(next_sort or 0) + 1,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def list_attachments(db: Session, post_id: int) -> list[Attachment]:
    """帖子附件列表（按排序号正序）。"""
    return list(
        db.execute(
            select(Attachment)
            .where(Attachment.post_id == post_id)
            .order_by(Attachment.sort_order, Attachment.id)
        ).scalars().all()
    )


def delete_attachment(db: Session, user: User, attachment_id: int) -> None:
    """删除附件（作者或频道主/管理员）。"""
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise NotFoundError("附件不存在")
    post = db.get(Post, att.post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    member = db.execute(
        select(Member).where(Member.community_id == post.community_id, Member.user_id == user.id)
    ).scalar_one_or_none()
    is_admin = member is not None and member.member_type in (MEMBER_OWNER, MEMBER_ADMIN)
    if post.author_id != user.id and not is_admin:
        raise PermissionError_("无权删除该附件")
    db.delete(att)
    db.commit()


def _get_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.status != POST_STATUS_NORMAL:
        raise NotFoundError("帖子不存在")
    return post
