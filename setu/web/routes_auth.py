"""Accounts, consent and withdrawal (E-08, P-ETH-04/05, data-model.md §5)."""
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import auth, consent_forms
from .deps import COOKIE, CurrentUser, ResearcherOrAdmin
from .errors import ApiError

router = APIRouter()


class Register(BaseModel):
    invite_code: str = Field(min_length=1, max_length=32)
    passphrase: str = Field(min_length=1, max_length=auth.MAX_PASSPHRASE)


class Login(BaseModel):
    handle: str = Field(min_length=1, max_length=16)
    passphrase: str = Field(min_length=1, max_length=auth.MAX_PASSPHRASE)


class ConsentIn(BaseModel):
    form_version: str = Field(max_length=32)
    scopes: list[str] = Field(min_length=1, max_length=8)


class InviteIn(BaseModel):
    role: str
    cohort: str | None = Field(default=None, max_length=64)


def _set_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, httponly=True, secure=request.app.state.cookie_secure, samesite="lax",
                        max_age=auth.SESSION_DAYS * 86400, path="/")


@router.post("/auth/register", status_code=201)
def register(body: Register, request: Request, response: Response):
    if auth.passphrase_problem(body.passphrase):
        raise ApiError("weak_passphrase")
    with request.app.state.db.tx() as c:
        redeemed = auth.redeem_invite(c, body.invite_code, body.passphrase)
        if redeemed is None:
            raise ApiError("invite_invalid")
        learner_id, handle = redeemed
        token, _ = auth.open_session(c, learner_id)
    _set_cookie(request, response, token)
    return {"learner_id": str(learner_id), "handle": handle}


@router.post("/auth/login", status_code=204)
def login(body: Login, request: Request, response: Response):
    with request.app.state.db.tx() as c:
        if auth.is_locked(c, body.handle):
            raise ApiError("locked", 429)
        learner_id = auth.check_login(c, body.handle, body.passphrase)
        token = auth.open_session(c, learner_id)[0] if learner_id else None
    if token is None:  # the failed attempt above is committed before refusing
        raise ApiError("auth_failed", 401)
    _set_cookie(request, response, token)
    response.status_code = 204
    return response


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: CurrentUser):
    with request.app.state.db.tx() as c:
        auth.revoke_session(c, user.session_id)
    response.delete_cookie(COOKIE, path="/")
    response.status_code = 204
    return response


def _active_consent(c, learner_id):
    row = c.execute(text("SELECT form_version, scope FROM consent WHERE learner_id = :l AND withdrawn_at IS NULL "
                         "ORDER BY signed_at DESC LIMIT 1"), {"l": learner_id}).first()
    return {"form_version": row.form_version, "scopes": list(row.scope)} if row else None


@router.get("/me")
def me(request: Request, user: CurrentUser):
    with request.app.state.db.tx() as c:
        consent = _active_consent(c, user.learner_id)
    return {"learner_id": str(user.learner_id), "handle": user.handle, "role": user.role, "consent": consent}


@router.get("/consent")
def consent_form(_user: CurrentUser):
    form = consent_forms.FORMS[consent_forms.CURRENT]
    return {"form_version": consent_forms.CURRENT, "scopes": list(form["scopes"]), "text_key": form["text_key"]}


@router.post("/consent", status_code=204)
def give_consent(body: ConsentIn, request: Request, response: Response, user: CurrentUser):
    form = consent_forms.FORMS.get(body.form_version)
    if form is None or not set(body.scopes) <= set(form["scopes"]) or len(set(body.scopes)) != len(body.scopes):
        raise ApiError("validation")
    if not consent_forms.signable(request.app.state, body.form_version):
        raise ApiError("consent_text_pending", 409)
    with request.app.state.db.tx() as c:
        c.execute(text("INSERT INTO consent (learner_id, form_version, scope) VALUES (:l, :f, :s)"),
                  {"l": user.learner_id, "f": body.form_version, "s": body.scopes})
    response.status_code = 204
    return response


def _withdraw(request: Request, learner_id: UUID) -> None:
    with request.app.state.db.tx() as c:
        c.execute(text("SELECT setu_withdraw_consent(:l)"), {"l": learner_id})


@router.post("/consent/withdraw", status_code=204)
def withdraw_own(request: Request, response: Response, user: CurrentUser):
    _withdraw(request, user.learner_id)
    response.delete_cookie(COOKIE, path="/")
    response.status_code = 204
    return response


@router.post("/research/invites", status_code=201)
def make_invite(body: InviteIn, request: Request, user: ResearcherOrAdmin):
    if body.role not in auth.INVITE_RIGHTS[user.role]:
        raise ApiError("forbidden", 403)
    code = auth.create_invite(request.app.state.db, role=body.role, cohort=body.cohort, created_by=user.learner_id)
    return {"invite_code": code, "role": body.role}


@router.post("/research/participants/{learner_id}/withdraw", status_code=204)
def withdraw_participant(learner_id: UUID, request: Request, response: Response,
                         _user: ResearcherOrAdmin):
    _withdraw(request, learner_id)
    response.status_code = 204
    return response
