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
from app.models.user_follow import UserFollow
from app.models.favorite import Favorite
from app.models.attachment import Attachment
from app.models.topic import Topic
from app.models.op_log import OpLog
from app.models.search_record import SearchRecord
from app.models.sensitive_word import SensitiveWord
from app.models.notification import Notification
from app.models.feed_strategy import FeedStrategy
from app.models.short_link import ShortLink
from app.models.review import Review
from app.models.report import Report
from app.models.ai_config import AiConfig
from app.models.ai_call_log import AiCallLog
from app.models.system_config import SystemConfig
from app.models.daily_stat import DailyStat

__all__ = [
    "User", "Community", "Board", "Role", "Member", "JoinRequest", "Post",
    "Comment", "Like", "Follow", "UserFollow", "Favorite", "Attachment", "Topic",
    "OpLog", "SearchRecord", "SensitiveWord", "Notification", "FeedStrategy",
    "ShortLink", "Review", "Report", "AiConfig", "AiCallLog", "SystemConfig",
    "DailyStat",
]
