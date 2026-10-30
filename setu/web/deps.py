"""Request dependencies: the signed-in user and role guards (E-08)."""
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from . import auth
from .errors import ApiError

COOKIE = "setu_session"


@dataclass(frozen=True)
class User:
    learner_id: UUID
    handle: str
    role: str
    session_id: UUID


def current_user(request: Request) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise ApiError("not_signed_in", 401)
    with request.app.state.db.tx() as c:
        row = auth.session_user(c, token)
    if row is None:
        raise ApiError("not_signed_in", 401)
    return User(row.learner_id, row.handle, row.role, row.session_id)


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: str):
    def guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError("forbidden", 403)
        return user

    return guard


ResearcherOrAdmin = Annotated[User, Depends(require_role("researcher", "admin"))]
