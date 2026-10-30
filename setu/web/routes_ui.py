"""Server-rendered Hindi pages (sign-in, registration, home, consent, teacher room).

They call the same account functions as the JSON API. Every word comes from the catalog; a missing or pending key
raises, so a page never falls back to other text (localisation-hindi-ui.md §1).
"""
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from . import auth, consent_forms
from .deps import COOKIE, User
from .routes_auth import _set_cookie

router = APIRouter()


def render(request: Request, template: str, *, title_key: str, status: int = 200, **ctx) -> HTMLResponse:
    html = request.app.state.templates.get_template(template).render(title_key=title_key, **ctx)
    return HTMLResponse(html, status_code=status)


def optional_user(request: Request) -> User | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    with request.app.state.db.tx() as c:
        row = auth.session_user(c, token)
    return User(row.learner_id, row.handle, row.role, row.session_id) if row else None


async def form_data(request: Request) -> dict:
    body = (await request.body()).decode("utf-8", errors="replace")
    return {k: v if len(v) > 1 else v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def _active_consent(request: Request, user: User):
    with request.app.state.db.tx() as c:
        return c.execute(text("SELECT form_version, scope FROM consent WHERE learner_id = :l AND withdrawn_at IS NULL "
                              "ORDER BY signed_at DESC LIMIT 1"), {"l": user.learner_id}).first()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return render(request, "learner/home.html", title_key="page.home", user=user,
                  consent=_active_consent(request, user))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "learner/login.html", title_key="page.login", user=None)


@router.post("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    data = await form_data(request)
    handle, passphrase = str(data.get("handle", ""))[:16], str(data.get("passphrase", ""))[:auth.MAX_PASSPHRASE]
    with request.app.state.db.tx() as c:
        if auth.is_locked(c, handle):
            return render(request, "learner/login.html", title_key="page.login", user=None,
                          error_key="err.locked", status=429)
        learner_id = auth.check_login(c, handle, passphrase)
        token = auth.open_session(c, learner_id)[0] if learner_id else None
    if token is None:
        return render(request, "learner/login.html", title_key="page.login", user=None,
                      error_key="err.auth_failed", status=401)
    response = RedirectResponse("/", status_code=303)
    _set_cookie(request, response, token)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return render(request, "learner/register.html", title_key="page.register", user=None)


@router.post("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    data = await form_data(request)
    code, passphrase = str(data.get("invite_code", ""))[:32], str(data.get("passphrase", ""))[:auth.MAX_PASSPHRASE]
    if auth.passphrase_problem(passphrase):
        return render(request, "learner/register.html", title_key="page.register", user=None,
                      error_key="err.weak_passphrase", status=400)
    with request.app.state.db.tx() as c:
        redeemed = auth.redeem_invite(c, code, passphrase)
        token = auth.open_session(c, redeemed[0])[0] if redeemed else None
    if redeemed is None:
        return render(request, "learner/register.html", title_key="page.register", user=None,
                      error_key="err.invite_invalid", status=400)
    response = render(request, "learner/registered.html", title_key="page.register", user=None, handle=redeemed[1])
    _set_cookie(request, response, token)
    return response


@router.post("/logout")
def logout_form(request: Request):
    user = optional_user(request)
    if user:
        with request.app.state.db.tx() as c:
            auth.revoke_session(c, user.session_id)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response


@router.get("/consent", response_class=HTMLResponse)
def consent_page(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    form = consent_forms.FORMS[consent_forms.CURRENT]
    catalog = request.app.state.catalog
    return render(request, "learner/consent.html", title_key="page.consent", user=user,
                  consent=_active_consent(request, user), scopes=form["scopes"], form_text_key=form["text_key"],
                  form_text_pending=catalog.is_pending(form["text_key"]) or not catalog.has(form["text_key"]))


@router.get("/teacher", response_class=HTMLResponse)
def teacher_home(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.role not in ("teacher", "admin"):
        return render(request, "learner/message.html", title_key="page.forbidden", user=user,
                      message_key="err.forbidden", status=403)
    return render(request, "teacher/home.html", title_key="page.teacher", user=user)


@router.post("/consent", response_class=HTMLResponse)
async def consent_form_submit(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    form = consent_forms.FORMS[consent_forms.CURRENT]
    if not consent_forms.signable(request.app.state, consent_forms.CURRENT):
        # Fail closed: an unapproved form cannot be signed even by posting directly (gate G4).
        return render(request, "learner/message.html", title_key="page.consent", user=user,
                      message_key="consent.pending", status=409)
    data = await form_data(request)
    scopes = data.get("scopes", [])
    scopes = [scopes] if isinstance(scopes, str) else list(scopes)
    if not scopes or not set(scopes) <= set(form["scopes"]):
        return render(request, "learner/message.html", title_key="page.consent", user=user,
                      message_key="err.validation", status=400)
    with request.app.state.db.tx() as c:
        c.execute(text("INSERT INTO consent (learner_id, form_version, scope) VALUES (:l, :f, :s)"),
                  {"l": user.learner_id, "f": consent_forms.CURRENT, "s": sorted(set(scopes))})
    return RedirectResponse("/consent", status_code=303)


@router.post("/consent/withdraw")
def consent_withdraw_submit(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        c.execute(text("SELECT setu_withdraw_consent(:l)"), {"l": user.learner_id})
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response
