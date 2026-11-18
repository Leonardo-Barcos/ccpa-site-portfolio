"""Editorial queries, slug generation and the small markup converter."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import EntityType, Event, Member, MemberStatus, Post, PostKind


# --------------------------------------------------------------------------
#  Slugs
# --------------------------------------------------------------------------
def slugify(text: str) -> str:
    stripped = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", stripped).strip("-").lower()
    return cleaned[:180] or "sem-titulo"


def unique_slug(db: Session, model, text: str, ignore_id: str | None = None) -> str:
    """Append -2, -3... when the slug is already taken.

    Two posts with the same headline are normal over a few years; two rows
    with the same slug would be a crash on save.
    """
    base = slugify(text)
    candidate = base
    counter = 2
    while True:
        query = select(model).where(model.slug == candidate)
        if ignore_id:
            query = query.where(model.id != ignore_id)
        if db.scalars(query).first() is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


# --------------------------------------------------------------------------
#  Text to HTML
# --------------------------------------------------------------------------
#  A deliberately small Markdown subset, written by hand. The input is escaped
#  BEFORE any conversion runs, so even a compromised dashboard account cannot
#  inject HTML into the public site — which a general-purpose Markdown library
#  would happily allow.
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    # Only http(s) links become anchors, which rules out javascript: URLs.
    text = _LINK.sub(r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def text_to_html(text: str) -> str:
    """Convert dashboard copy into safe HTML.

    Supports ## and ### headings, - lists, > quotes, **bold**, *italic* and
    [text](url). Everything else becomes a paragraph.
    """
    out: list[str] = []
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()

        if not line:
            close_list()
            continue
        if line.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("> "):
            close_list()
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line.startswith("- "):
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{_inline(line[2:])}</li>")
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")

    close_list()
    return "\n".join(out)


# --------------------------------------------------------------------------
#  Posts
# --------------------------------------------------------------------------
def list_posts(
    db: Session,
    kind: PostKind,
    *,
    limit: int | None = None,
    category: str | None = None,
    search: str | None = None,
) -> list[Post]:
    query = (
        select(Post)
        .where(Post.kind == kind, Post.published.is_(True))
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
    )
    if category:
        query = query.where(Post.category == category)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Post.title).like(pattern),
                func.lower(Post.summary).like(pattern),
                func.lower(Post.body).like(pattern),
            )
        )
    if limit:
        query = query.limit(limit)
    return list(db.scalars(query))


def post_by_slug(db: Session, kind: PostKind, slug: str) -> Post | None:
    return db.scalars(
        select(Post).where(Post.kind == kind, Post.slug == slug, Post.published.is_(True))
    ).first()


def categories(db: Session, kind: PostKind) -> list[str]:
    rows = db.scalars(
        select(Post.category)
        .where(Post.kind == kind, Post.published.is_(True), Post.category.isnot(None))
        .distinct()
        .order_by(Post.category)
    )
    return [c for c in rows if c]


def related_posts(db: Session, post: Post, limit: int = 3) -> list[Post]:
    return list(
        db.scalars(
            select(Post)
            .where(
                Post.kind == post.kind,
                Post.published.is_(True),
                Post.id != post.id,
            )
            .order_by(Post.published_at.desc().nullslast())
            .limit(limit)
        )
    )


# --------------------------------------------------------------------------
#  Events
# --------------------------------------------------------------------------
def upcoming_events(db: Session, limit: int | None = None) -> list[Event]:
    query = (
        select(Event)
        .where(Event.published.is_(True), Event.starts_at >= datetime.now(UTC))
        .order_by(Event.starts_at.asc())
    )
    if limit:
        query = query.limit(limit)
    return list(db.scalars(query))


def past_events(db: Session, limit: int = 12) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.published.is_(True), Event.starts_at < datetime.now(UTC))
            .order_by(Event.starts_at.desc())
            .limit(limit)
        )
    )


def event_by_slug(db: Session, slug: str) -> Event | None:
    return db.scalars(
        select(Event).where(Event.slug == slug, Event.published.is_(True))
    ).first()


# --------------------------------------------------------------------------
#  Talent directory
# --------------------------------------------------------------------------
def talent_directory(
    db: Session,
    *,
    search: str | None = None,
    chapter: str | None = None,
    limit: int = 60,
) -> list[Member]:
    """Active individual members, searchable by whoever is hiring.

    Fed by the membership table rather than a separate profile: paying members
    are the directory, which is also one more reason to join. The template
    decides what is shown — contact details never are.
    """
    query = (
        select(Member)
        .where(
            Member.status == MemberStatus.ACTIVE,
            Member.entity_type == EntityType.PF,
        )
        .order_by(Member.name.asc())
        .limit(limit)
    )
    if chapter:
        query = query.where(Member.chapter == chapter)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Member.name).like(pattern),
                func.lower(func.coalesce(Member.role, "")).like(pattern),
                func.lower(func.coalesce(Member.company, "")).like(pattern),
            )
        )
    return list(db.scalars(query))
