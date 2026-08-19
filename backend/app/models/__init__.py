"""ORM 模型包：集中导入所有模型，供 Alembic autogenerate 发现。

每个业务模块一个文件，后续阶段按需新增并在此导入：
  topic/post/media/comment/like/favorite/follow/feed_strategy/notification/
  short_link/review/report/search_record/ai_config/system_config/op_log/daily_stat
"""
from app.models.user import User
from app.models.community import Community
from app.models.board import Board
from app.models.role import Role
from app.models.member import Member
from app.models.join_request import JoinRequest
from app.models.post import Post
from app.models.comment import Comment
from app.models.like import Like
from app.models.follow import Follow
from app.models.topic import Topic

__all__ = ["User", "Community", "Board", "Role", "Member", "JoinRequest", "Post", "Comment", "Like", "Follow", "Topic"]
