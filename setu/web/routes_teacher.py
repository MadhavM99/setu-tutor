"""Teacher console I (slice 4.1): native review of content and the unsure queue (X-TCH-01/04, F3, gate G3).

Only accounts with the `teacher` role reach these pages; every write goes through `ContentReviewer` (content role)
or the OutcomeWriter (a signed `TeacherResolution`), and both re-check the role in the database. Pages are Hindi;
Telugu is shown in Telugu script. Reason codes and model-drafted provenance are shown as Hindi labels.
"""
import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.store.content_review import KINDS, ContentReviewer, ReviewRefused
from setu.store.outcome_writer import ResolutionRefused
from setu.store.resolution import MIN_KEY_BYTES, TeacherResolution

from .routes_ui import form_data, optional_user, render

router = APIRouter()
QUEUE_LIMIT = 50
MODEL_MARKERS = ("language model", "claude", "drafted by", "ai)", "(ai")


def _teacher(request):
    user = optional_user(request)
    if user is None:
        return None, RedirectResponse("/login", status_code=303)
    if user.role != "teacher":
        return None, render(request, "learner/message.html", title_key="page.forbidden", user=user,
                            message_key="err.forbidden", status=403)
    return user, None


def _reviewer(request) -> ContentReviewer:
    if getattr(request.app.state, "reviewer", None) is None:
        request.app.state.reviewer = ContentReviewer.from_environment(fallback=request.app.state.db.engine)
    return request.app.state.reviewer


def model_drafted(provenance) -> bool:
    blob = str(provenance or "").lower()
    return any(m in blob for m in MODEL_MARKERS)


@router.get("/teacher", response_class=HTMLResponse)
def teacher_home(request: Request):
    user, deny = _teacher(request)
    if deny:
        return deny
    return render(request, "teacher/home.html", title_key="page.teacher", user=user)


# ---------------------------------------------------------------- content review


@router.get("/teacher/review", response_class=HTMLResponse)
def review_home(request: Request):
    user, deny = _teacher(request)
    if deny:
        return deny
    return render(request, "teacher/review_home.html", title_key="page.review", user=user,
                  counts=_reviewer(request).pending_counts())


@router.get("/teacher/review/{kind}", response_class=HTMLResponse)
def review_list(request: Request, kind: str, message: str | None = None):
    user, deny = _teacher(request)
    if deny:
        return deny
    if kind not in KINDS:
        return RedirectResponse("/teacher/review", status_code=303)
    rows = _reviewer(request).pending(kind, user.learner_id)
    return render(request, "teacher/review_list.html", title_key="page.review", user=user, kind=kind, k=KINDS[kind],
                  rows=[{**r, "drafted": model_drafted(r["provenance"])} for r in rows], message_key=message)


def _detail(request, user, kind, item_id, message=None, status=200):
    rec = _reviewer(request).record(kind, item_id)
    if rec is None:
        return RedirectResponse(f"/teacher/review/{kind}", status_code=303)
    me = f"teacher:{user.learner_id}"
    return render(request, "teacher/review_item.html", title_key="page.review", user=user, kind=kind, k=KINDS[kind],
                  rec=rec, drafted=model_drafted(rec["provenance"]), message_key=message, status=status,
                  mine=any(a.get("reviewer") == me for a in rec["approvals"] or []))


@router.get("/teacher/review/{kind}/item", response_class=HTMLResponse)
def review_item(request: Request, kind: str, id: str):
    user, deny = _teacher(request)
    if deny:
        return deny
    if kind not in KINDS:
        return RedirectResponse("/teacher/review", status_code=303)
    return _detail(request, user, kind, id)


@router.post("/teacher/review/{kind}/item", response_class=HTMLResponse)
async def review_decide(request: Request, kind: str):
    user, deny = _teacher(request)
    if deny:
        return deny
    data = await form_data(request)
    item_id = str(data.get("id", ""))
    if kind not in KINDS:
        return RedirectResponse("/teacher/review", status_code=303)
    try:
        _reviewer(request).review(kind, item_id, user.learner_id, decision=str(data.get("decision", "")),
                                  native=bool(data.get("native")), content_hash=str(data.get("content_hash", "")),
                                  comment_hi=str(data.get("comment_hi", "")).strip()[:500] or None)
    except ReviewRefused as e:
        return _detail(request, user, kind, item_id, message=e.key, status=409)
    return _detail(request, user, kind, item_id, message="tch.saved")


@router.post("/teacher/review/{kind}/batch", response_class=HTMLResponse)
async def review_batch(request: Request, kind: str):
    """Approve several records at once: one review per record, each of the version listed on the page."""
    user, deny = _teacher(request)
    if deny:
        return deny
    if kind not in KINDS:
        return RedirectResponse("/teacher/review", status_code=303)
    data = await form_data(request)
    picks = data.get("pick", [])
    picks = [picks] if isinstance(picks, str) else list(picks)
    refused = 0
    for pick in picks:
        item_id, _, content_hash = str(pick).rpartition("|")
        try:
            _reviewer(request).review(kind, item_id, user.learner_id, decision="approve",
                                      native=bool(data.get("native")), content_hash=content_hash)
        except ReviewRefused:
            refused += 1
    return review_list(request, kind, message="tch.batch_some_refused" if refused else "tch.saved")


# ---------------------------------------------------------------- the unsure queue (F3)

_QUEUE = """
SELECT q.id, q.created_at, a.raw_text, v.reason_code, v.kind AS verdict_kind, e.kind AS exchange_kind, e.shown_text,
       e.task, iv.correct_form, iv.wrong_form,
       coalesce((SELECT array_agg(av.form ORDER BY av.form) FROM learner_accepted_variant av
                  WHERE av.item_version_id = iv.id), '{}') AS variants,
       (SELECT l.replies FROM scene_line l WHERE l.scene_id = e.task->>'scene_id'
         AND l.n = (e.task->>'line')::int) AS scene_replies
  FROM teacher_queue_item q JOIN verdict v ON v.id = q.verdict_id JOIN attempt a ON a.id = v.attempt_id
  JOIN exchange e ON e.id = a.exchange_id LEFT JOIN item_version iv ON iv.id = e.item_version_id
 WHERE q.status = 'open' ORDER BY q.created_at DESC LIMIT :n"""


def reason_key(code: str | None) -> str:
    code = code or ""
    if code.startswith("input_"):
        return "tch.reason.unreadable"
    if code.startswith("romanised"):
        return "tch.reason.romanised"
    if code in ("no_key_idea", "ideas_without_relation"):
        return "tch.reason.explanation"
    if code == "unknown_form":
        return "tch.reason.unknown_form"
    return "tch.reason.other"


def _accepted(row) -> list[str]:
    forms = [f for f in [row.correct_form, *(row.variants or [])] if f]
    forms += list(row.scene_replies or [])
    task = row.task or {}
    if task.get("expected"):
        forms.append(task["expected"])
    return list(dict.fromkeys(forms))


def _queue_page(request, user, message=None, status=200):
    with request.app.state.db.tx() as c:
        rows = c.execute(text(_QUEUE), {"n": QUEUE_LIMIT}).all()
    items = [{"id": r.id, "answer": r.raw_text, "shown": r.shown_text if r.exchange_kind != "own" else None,
              "goal": r.shown_text if r.exchange_kind == "own" else None, "accepted": _accepted(r),
              "reason_key": reason_key(r.reason_code), "explanation": r.verdict_kind == "explanation"}
             for r in rows]
    return render(request, "teacher/queue.html", title_key="page.queue", user=user, items=items,
                  message_key=message, status=status)


@router.get("/teacher/queue", response_class=HTMLResponse)
def queue(request: Request):
    user, deny = _teacher(request)
    if deny:
        return deny
    return _queue_page(request, user)


@router.post("/teacher/queue/settle", response_class=HTMLResponse)
async def settle(request: Request):
    user, deny = _teacher(request)
    if deny:
        return deny
    data = await form_data(request)
    try:
        qid = uuid.UUID(str(data.get("queue_item_id")))
    except ValueError:
        return _queue_page(request, user, message="tch.bad_request", status=400)
    outcome = str(data.get("outcome", ""))
    if outcome not in ("correct", "partial", "wrong"):
        return _queue_page(request, user, message="tch.bad_request", status=400)
    key = os.environ.get("SETU_RESOLUTION_KEY", "").encode()
    if len(key) < MIN_KEY_BYTES:
        return _queue_page(request, user, message="tch.no_key", status=503)
    note = str(data.get("note_hi", "")).strip()[:500] or None
    resolution = TeacherResolution.sign(key=key, queue_item_id=qid, teacher_id=user.learner_id, outcome=outcome,
                                        note_hi=note)
    try:
        request.app.state.writer.apply_resolution(resolution)
    except ResolutionRefused:
        return _queue_page(request, user, message="tch.already_settled", status=409)
    return _queue_page(request, user, message="tch.settled")
