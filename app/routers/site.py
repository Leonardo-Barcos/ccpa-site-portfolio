"""Public pages of the institutional site."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import site_content
from ..config import settings
from ..database import get_db
from ..models import ContactMessage, Event, Post, PostKind
from ..plans import CHAPTERS, PLANS
from ..security import client_ip
from ..services import content
from ..templating import templates

router = APIRouter()


def _page(request: Request, template: str, context: dict, status: int = 200):
    base = {"request": request, "current_path": request.url.path}
    base.update(context)
    return templates.TemplateResponse(request, template, base, status_code=status)


def _site_base_url() -> str:
    return settings.base_url.rstrip("/")


# --------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    news = content.list_posts(db, PostKind.NEWS, limit=4)
    return _page(
        request,
        "site/home.html",
        {
            "featured": news[0] if news else None,
            "news": news[1:4],
            "columns": content.list_posts(db, PostKind.COLUMN, limit=3),
            "events": content.upcoming_events(db, limit=3),
            "plans": list(PLANS.values()),
        },
    )


@router.get("/sobre", response_class=HTMLResponse)
def about(request: Request):
    return _page(request, "site/about.html", {})


# ------------------------------- News -------------------------------------
@router.get("/noticias", response_class=HTMLResponse)
def news_list(
    request: Request,
    categoria: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    return _page(
        request,
        "site/post_list.html",
        {
            "page_title": "Notícias",
            "page_subtitle": "O que acontece na cadeia criativa do Pará.",
            "posts": content.list_posts(db, PostKind.NEWS, category=categoria, search=q),
            "categories": content.categories(db, PostKind.NEWS),
            "active_category": categoria,
            "search": q or "",
            "list_url": "/noticias",
        },
    )


@router.get("/noticias/{slug}", response_class=HTMLResponse)
def news_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    post = content.post_by_slug(db, PostKind.NEWS, slug)
    if not post:
        return _page(request, "site/404.html", {}, status=404)
    return _page(
        request,
        "site/post.html",
        {
            "post": post,
            "body": content.text_to_html(post.body),
            "related": content.related_posts(db, post),
            "back_url": "/noticias",
            "back_label": "Todas as notícias",
        },
    )


# ------------------------------ Columns -----------------------------------
@router.get("/colunas", response_class=HTMLResponse)
def column_list(
    request: Request,
    categoria: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    return _page(
        request,
        "site/post_list.html",
        {
            "page_title": "Colunas",
            "page_subtitle": "Opinião e análise de quem vive a criatividade paraense.",
            "posts": content.list_posts(
                db, PostKind.COLUMN, category=categoria, search=q
            ),
            "categories": content.categories(db, PostKind.COLUMN),
            "active_category": categoria,
            "search": q or "",
            "list_url": "/colunas",
        },
    )


@router.get("/colunas/{slug}", response_class=HTMLResponse)
def column_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    post = content.post_by_slug(db, PostKind.COLUMN, slug)
    if not post:
        return _page(request, "site/404.html", {}, status=404)
    return _page(
        request,
        "site/post.html",
        {
            "post": post,
            "body": content.text_to_html(post.body),
            "related": content.related_posts(db, post),
            "back_url": "/colunas",
            "back_label": "Todas as colunas",
        },
    )


# ------------------------------- Events -----------------------------------
@router.get("/eventos", response_class=HTMLResponse)
def event_list(request: Request, db: Session = Depends(get_db)):
    return _page(
        request,
        "site/events.html",
        {
            "upcoming": content.upcoming_events(db),
            "past": content.past_events(db),
        },
    )


@router.get("/eventos/{slug}", response_class=HTMLResponse)
def event_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    event = content.event_by_slug(db, slug)
    if not event:
        return _page(request, "site/404.html", {}, status=404)
    return _page(
        request,
        "site/event.html",
        {"event": event, "body": content.text_to_html(event.description)},
    )


# -------------------------- Talent directory ------------------------------
@router.get("/talentos", response_class=HTMLResponse)
def talent_directory(
    request: Request,
    q: str | None = None,
    regional: str | None = None,
    db: Session = Depends(get_db),
):
    return _page(
        request,
        "site/talent.html",
        {
            "people": content.talent_directory(db, search=q, chapter=regional),
            "chapters": CHAPTERS,
            "search": q or "",
            "active_chapter": regional or "",
        },
    )


# ------------------------------- Contact ----------------------------------
@router.get("/contato", response_class=HTMLResponse)
def contact_page(request: Request, enviado: int = 0):
    return _page(
        request,
        "site/contact.html",
        {"sent": bool(enviado), "errors": {}, "form": {}},
    )


@router.post("/contato")
async def submit_contact(request: Request, db: Session = Depends(get_db)):
    form = {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in (await request.form()).items()
    }

    # Honeypot: the field is hidden, so only a bot fills it in. Answer with the
    # usual redirect so the bot cannot tell it was caught.
    if form.get("website"):
        return RedirectResponse("/contato?enviado=1", status_code=303)

    errors: dict[str, str] = {}
    if len(form.get("name", "")) < 3:
        errors["name"] = "Informe seu nome."
    if "@" not in form.get("email", "") or "." not in form.get("email", ""):
        errors["email"] = "E-mail inválido."
    if form.get("subject") not in site_content.CONTACT_SUBJECTS:
        errors["subject"] = "Escolha um assunto."
    if len(form.get("message", "")) < 10:
        errors["message"] = "Escreva um pouco mais para a gente entender melhor."

    if errors:
        return _page(
            request,
            "site/contact.html",
            {"sent": False, "errors": errors, "form": form},
            status=422,
        )

    db.add(
        ContactMessage(
            name=form["name"][:180],
            email=form["email"][:255],
            phone=(form.get("phone") or None),
            subject=form["subject"],
            body=form["message"][:5000],
            ip=client_ip(request),
        )
    )
    db.commit()
    return RedirectResponse("/contato?enviado=1", status_code=303)


# ------------------------------ Crawlers ----------------------------------
@router.get("/robots.txt", include_in_schema=False)
def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        f"Sitemap: {_site_base_url()}/sitemap.xml\n"
    )
    return Response(body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)):
    base = _site_base_url()
    urls = [f"{base}{href}" for _, href in site_content.NAV]
    urls.append(f"{base}/associe-se")

    for slug, kind in db.execute(
        select(Post.slug, Post.kind).where(Post.published.is_(True))
    ):
        folder = "noticias" if kind == PostKind.NEWS else "colunas"
        urls.append(f"{base}/{folder}/{slug}")

    for (slug,) in db.execute(select(Event.slug).where(Event.published.is_(True))):
        urls.append(f"{base}/eventos/{slug}")

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    return Response(body, media_type="application/xml")
