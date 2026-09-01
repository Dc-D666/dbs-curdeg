"""版块接口：CRUD/排序/隐藏。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.core.response import NotFoundError, ok
from app.db import get_db
from app.models.board import Board
from app.models.community import Community
from app.models.user import User
from app.schemas.community import CreateBoardRequest, UpdateBoardRequest
from app.services import community_service

router = APIRouter(prefix="/communities/{community_id}/boards", tags=["boards"])


def _get_community(db: Session, community_id: int) -> Community:
    community = db.get(Community, community_id)
    if community is None or community.status != 0:
        raise NotFoundError("频道不存在")
    return community


@router.post("")
def create_board(
    community_id: int,
    payload: CreateBoardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增版块（仅 owner）。"""
    community = _get_community(db, community_id)
    return ok(data=community_service.create_board(db, community, user, payload), message="版块创建成功")


@router.get("")
def list_boards(
    community_id: int,
    include_all: bool = Query(False, description="管理员后台：包含已关闭板块"),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """版块列表（公开）。include_all=true 时返回全部（含已关闭，供管理后台显示）。"""
    community = _get_community(db, community_id)
    if include_all:
        from app.core.permissions import PERM_MEMBER_MANAGE, require_perms
        require_perms(db, community_id, user, PERM_MEMBER_MANAGE)
        boards = community_service.all_boards(db, community)
        return ok(data=boards)
    boards = community_service.community_out(db, community, None).boards
    return ok(data=boards)


@router.put("/{board_id}")
def update_board(
    community_id: int,
    board_id: int,
    payload: UpdateBoardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """编辑版块（仅 owner）。"""
    community = _get_community(db, community_id)
    board = db.get(Board, board_id)
    if board is None or board.community_id != community_id:
        raise NotFoundError("版块不存在")
    return ok(data=community_service.update_board(db, community, user, board, payload))


@router.delete("/{board_id}")
def delete_board(
    community_id: int,
    board_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除版块（仅 owner，软删）。"""
    community = _get_community(db, community_id)
    board = db.get(Board, board_id)
    if board is None or board.community_id != community_id:
        raise NotFoundError("版块不存在")
    community_service.delete_board(db, community, user, board)
    return ok(message="版块已删除")
