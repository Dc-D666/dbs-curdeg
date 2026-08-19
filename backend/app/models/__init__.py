"""ORM 模型包：集中导入所有模型，供 Alembic autogenerate 发现。

每个业务模块一个文件，后续阶段按需新增并在此导入：
  user/community/board/role/member/join_request/topic/post/media/comment/
  like/favorite/follow/feed_strategy/notification/short_link/review/report/
  search_record/ai_config/system_config/op_log/daily_stat
"""
