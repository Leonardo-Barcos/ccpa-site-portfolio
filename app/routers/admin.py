"""Publishing dashboard: login, content, messages and the member list.

How this area is protected:
  * signed session cookie, HttpOnly and SameSite=Lax (see security.py);
  * a CSRF token on every POST;
  * Argon2id password hashes;
  * `Depends(require_login)` on every route, so none can be left open by
    forgetting a decorator.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AdminUser,
    ContactMessage,
    Event,
    Member,
    MemberStatus,
    Payment,
    PaymentStatus,
    Post,
    PostKind,
)
from ..plans import CHAPTERS, PLANS
from ..security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    csrf_matches,
    new_csrf_token,
    read_session_token,
    verify_password,
)
from ..services.content import unique_slug
from ..templating import templates

router = APIRouter(prefix="/admin")


# --------------------------------------------------------------------------
#  Authentication
# --------------------------------------------------------------------------
def current_user(request: Request, db: Session = Depends(get_db)) -> AdminUser | None:
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    if not user_id:
        return None
    user = db.get(AdminUser, user_id)
    return user if user and user.active else None


class LoginRequired(Exception):
    """Raised by the dependency; the app turns it into a redirect."""


def require_login(user: AdminUser | None = Depends(current_user)) -> AdminUser:
    if user is None:
        raise LoginRequired()
    return user


def check_csrf(request: Request, submitted: str | None) -> None:
    if not csrf_matches(request.cookies.get(CSRF_COOKIE), submitted):
        raise HTTPException(
            status_code=403, detail="Sessão expirada. Recarregue a página."
        )


def _screen(
    request: Request, template: str, context: dict, status: int = 200
) -> HTMLResponse:
    base = {"request": request, "current_path": request.url.path}
    base.update(context)
    response = templates.TemplateResponse(request, template, base, status_code=status)
    if not request.cookies.get(CSRF_COOKIE):
        response.set_cookie(
            CSRF_COOKIE,
            context.get("csrf", ""),
            # Readable by design: the form has to echo it back. The protection
            # is that a cross-site attacker cannot read the cookie to copy it.
            httponly=False,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=SESSION_MAX_AGE,
        )
    return response


def _csrf(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE) or new_csrf_token()


# --------------------------------- Login ----------------------------------
@router.get("/entrar", response_class=HTMLResponse)
def login_page(request: Request, user: AdminUser | None = Depends(current_user)):
    if user:
        return RedirectResponse("/admin", status_code=303)
    return _screen(request, "admin/login.html", {"error": None, "csrf": _csrf(request)})


@router.post("/entrar")
async def do_login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    check_csrf(request, form.get("csrf"))

    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    user = db.scalars(
        select(AdminUser).where(func.lower(AdminUser.email) == email)
    ).first()

    # One generic message for every failure: never reveal whether the address
    # exists, which would turn the login form into an account enumerator.
    if not user or not user.active or not verify_password(user.password_hash, password):
        return _screen(
            request,
            "admin/login.html",
            {"error": "E-mail ou senha incorretos.", "csrf": _csrf(request)},
            status=401,
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=SESSION_MAX_AGE,
    )
    return response


@router.post("/sair")
async def do_logout(request: Request):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    response = RedirectResponse("/admin/entrar", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# --------------------------------------------------------------------------
#  Overview
# --------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    def count(model, *conditions) -> int:
        query = select(func.count()).select_from(model)
        for condition in conditions:
            query = query.where(condition)
        return db.scalar(query) or 0

    return _screen(
        request,
        "admin/dashboard.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "tiles": [
                (
                    "Associados ativos",
                    count(Member, Member.status == MemberStatus.ACTIVE),
                    "/admin/associados",
                ),
                (
                    "Aguardando pagamento",
                    count(Member, Member.status == MemberStatus.AWAITING_PAYMENT),
                    "/admin/associados",
                ),
                (
                    "Mensagens não lidas",
                    count(ContactMessage, ContactMessage.read.is_(False)),
                    "/admin/mensagens",
                ),
                (
                    "Publicações no ar",
                    count(Post, Post.published.is_(True)),
                    "/admin/posts",
                ),
            ],
            "recent_members": list(
                db.scalars(select(Member).order_by(Member.created_at.desc()).limit(6))
            ),
            "recent_messages": list(
                db.scalars(
                    select(ContactMessage)
                    .order_by(ContactMessage.created_at.desc())
                    .limit(5)
                )
            ),
        },
    )


# --------------------------------------------------------------------------
#  News and columns
# --------------------------------------------------------------------------
def _kind_from(value: str) -> PostKind:
    return PostKind.COLUMN if value == "COLUMN" else PostKind.NEWS


@router.get("/posts", response_class=HTMLResponse)
def post_list(
    request: Request,
    tipo: str = "NEWS",
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    kind = _kind_from(tipo)
    return _screen(
        request,
        "admin/posts.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "kind": kind,
            "posts": list(
                db.scalars(
                    select(Post).where(Post.kind == kind).order_by(Post.created_at.desc())
                )
            ),
        },
    )


@router.get("/posts/novo", response_class=HTMLResponse)
def new_post(
    request: Request, tipo: str = "NEWS", user: AdminUser = Depends(require_login)
):
    return _screen(
        request,
        "admin/post_form.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "post": None,
            "kind": _kind_from(tipo),
            "errors": {},
            "form": {"author": user.name},
        },
    )


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def edit_post(
    request: Request,
    post_id: str,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post:
        return RedirectResponse("/admin/posts", status_code=303)
    return _screen(
        request,
        "admin/post_form.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "post": post,
            "kind": post.kind,
            "errors": {},
            "form": {},
        },
    )


@router.post("/posts/salvar")
async def save_post(
    request: Request,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    form = {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in (await request.form()).items()
    }
    check_csrf(request, form.get("csrf"))

    kind = _kind_from(form.get("kind", "NEWS"))
    post = db.get(Post, form["post_id"]) if form.get("post_id") else None

    errors: dict[str, str] = {}
    if len(form.get("title", "")) < 5:
        errors["title"] = "Título muito curto."
    if len(form.get("summary", "")) < 15:
        errors["summary"] = "Escreva um resumo de pelo menos 15 caracteres."
    if len(form.get("body", "")) < 30:
        errors["body"] = "O texto está muito curto."
    if not form.get("author"):
        errors["author"] = "Informe quem assina."

    if errors:
        return _screen(
            request,
            "admin/post_form.html",
            {
                "user": user,
                "csrf": _csrf(request),
                "post": post,
                "kind": kind,
                "errors": errors,
                "form": form,
            },
            status=422,
        )

    publish = form.get("published") == "on"

    if post is None:
        post = Post(kind=kind)
        db.add(post)

    post.title = form["title"][:200]
    post.summary = form["summary"][:320]
    post.body = form["body"]
    post.author = form["author"][:120]
    post.category = form.get("category") or None
    post.image_url = form.get("image_url") or None
    post.slug = unique_slug(db, Post, form["title"], ignore_id=post.id)

    # The publication date is stamped the first time the post goes live, so
    # editing an old article later does not move it to the top of the list.
    if publish and not post.published_at:
        post.published_at = datetime.now(UTC)
    post.published = publish

    db.commit()
    return RedirectResponse(f"/admin/posts?tipo={kind.value}", status_code=303)


@router.post("/posts/{post_id}/excluir")
async def delete_post(
    request: Request,
    post_id: str,
    user: AdminUser = Depends(require_login),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    post = db.get(Post, post_id)
    kind = post.kind.value if post else "NEWS"
    if post:
        db.delete(post)
        db.commit()
    return RedirectResponse(f"/admin/posts?tipo={kind}", status_code=303)


# --------------------------------------------------------------------------
#  Events
# --------------------------------------------------------------------------
@router.get("/eventos", response_class=HTMLResponse)
def event_list(
    request: Request,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    return _screen(
        request,
        "admin/events.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "events": list(db.scalars(select(Event).order_by(Event.starts_at.desc()))),
        },
    )


@router.get("/eventos/novo", response_class=HTMLResponse)
def new_event(request: Request, user: AdminUser = Depends(require_login)):
    return _screen(
        request,
        "admin/event_form.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "event": None,
            "chapters": CHAPTERS,
            "errors": {},
            "form": {},
        },
    )


@router.get("/eventos/{event_id}", response_class=HTMLResponse)
def edit_event(
    request: Request,
    event_id: str,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        return RedirectResponse("/admin/eventos", status_code=303)
    return _screen(
        request,
        "admin/event_form.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "event": event,
            "chapters": CHAPTERS,
            "errors": {},
            "form": {},
        },
    )


@router.post("/eventos/salvar")
async def save_event(
    request: Request,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    form = {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in (await request.form()).items()
    }
    check_csrf(request, form.get("csrf"))

    event = db.get(Event, form["event_id"]) if form.get("event_id") else None

    errors: dict[str, str] = {}
    if len(form.get("title", "")) < 5:
        errors["title"] = "Título muito curto."
    if len(form.get("summary", "")) < 15:
        errors["summary"] = "Escreva um resumo de pelo menos 15 caracteres."
    if not form.get("venue"):
        errors["venue"] = "Informe o local."

    starts_at = None
    try:
        starts_at = datetime.fromisoformat(form["starts_at"]).replace(tzinfo=UTC)
    except (KeyError, ValueError):
        errors["starts_at"] = "Informe data e hora de início."

    if errors:
        return _screen(
            request,
            "admin/event_form.html",
            {
                "user": user,
                "csrf": _csrf(request),
                "event": event,
                "chapters": CHAPTERS,
                "errors": errors,
                "form": form,
            },
            status=422,
        )

    if event is None:
        event = Event()
        db.add(event)

    event.title = form["title"][:200]
    event.summary = form["summary"][:320]
    event.description = form.get("description", "")
    event.starts_at = starts_at
    event.venue = form["venue"][:200]
    event.city = form.get("city") or None
    event.chapter = form.get("chapter") or None
    event.signup_url = form.get("signup_url") or None
    event.image_url = form.get("image_url") or None
    event.free = form.get("free") == "on"
    event.published = form.get("published") == "on"
    event.slug = unique_slug(db, Event, form["title"], ignore_id=event.id)

    db.commit()
    return RedirectResponse("/admin/eventos", status_code=303)


@router.post("/eventos/{event_id}/excluir")
async def delete_event(
    request: Request,
    event_id: str,
    user: AdminUser = Depends(require_login),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    event = db.get(Event, event_id)
    if event:
        db.delete(event)
        db.commit()
    return RedirectResponse("/admin/eventos", status_code=303)


# --------------------------------------------------------------------------
#  Contact inbox
# --------------------------------------------------------------------------
@router.get("/mensagens", response_class=HTMLResponse)
def message_inbox(
    request: Request,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    return _screen(
        request,
        "admin/messages.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "messages": list(
                db.scalars(
                    select(ContactMessage)
                    .order_by(ContactMessage.created_at.desc())
                    .limit(200)
                )
            ),
        },
    )


@router.post("/mensagens/{message_id}/lida")
async def toggle_message_read(
    request: Request,
    message_id: str,
    user: AdminUser = Depends(require_login),  # noqa: ARG001
    db: Session = Depends(get_db),
):
    form = await request.form()
    check_csrf(request, form.get("csrf"))
    message = db.get(ContactMessage, message_id)
    if message:
        message.read = not message.read
        db.commit()
    return RedirectResponse("/admin/mensagens", status_code=303)


# --------------------------------------------------------------------------
#  Members
# --------------------------------------------------------------------------
@router.get("/associados", response_class=HTMLResponse)
def member_list(
    request: Request,
    status: str | None = None,
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    query = select(Member).order_by(Member.created_at.desc())
    if status in MemberStatus.__members__:
        query = query.where(Member.status == MemberStatus[status])

    members = list(db.scalars(query.limit(300)))
    paid_ids = {
        payment.member_id
        for payment in db.scalars(
            select(Payment).where(Payment.status == PaymentStatus.CONFIRMED)
        )
    }

    return _screen(
        request,
        "admin/members.html",
        {
            "user": user,
            "csrf": _csrf(request),
            "members": members,
            "paid_ids": paid_ids,
            "plans": PLANS,
            "active_status": status or "",
            "status_options": list(MemberStatus),
        },
    )
