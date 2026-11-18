"""Tests for the public site and the publishing dashboard."""

import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tempfile.gettempdir()}/ccpa_site.db"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["RESEND_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser, Event, Post, PostKind  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.content import slugify, text_to_html  # noqa: E402

ADMIN_PASSWORD = "senha-do-teste-123"


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_email():
    with Session(engine) as db:
        user = AdminUser(
            name="Maria Diretoria",
            email="diretoria@ccpara.com.br",
            password_hash=hash_password(ADMIN_PASSWORD),
        )
        db.add(user)
        db.commit()
        return user.email


@pytest.fixture
def logged_in(client, admin_email):
    """A client already authenticated, plus its CSRF token."""
    client.get("/admin/entrar")
    csrf = client.cookies.get("ccpa_csrf")
    response = client.post(
        "/admin/entrar",
        data={"email": admin_email, "password": ADMIN_PASSWORD, "csrf": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client, csrf


def make_post(published=True, kind=PostKind.NEWS, title="Notícia de teste"):
    with Session(engine) as db:
        post = Post(
            kind=kind,
            slug=slugify(title),
            title=title,
            summary="Resumo suficientemente longo para o teste.",
            body="## Título\n\nCorpo do texto.",
            author="Redação",
            category="Mercado",
            published=published,
            published_at=datetime.now(UTC) if published else None,
        )
        db.add(post)
        db.commit()
        return post.slug


# ============================ Public pages ================================
@pytest.mark.parametrize(
    "path",
    ["/", "/sobre", "/noticias", "/colunas", "/eventos", "/talentos", "/contato"],
)
def test_public_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "Clube de Criativos do Pará" in response.text


def test_nav_marks_the_current_page(client):
    response = client.get("/sobre")
    assert 'href="/sobre"' in response.text
    assert 'aria-current="page"' in response.text


def test_unknown_path_renders_the_branded_404(client):
    response = client.get("/pagina-que-nao-existe")
    assert response.status_code == 404
    assert "Essa página não existe" in response.text


def test_sitemap_lists_published_content(client):
    slug = make_post()
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert f"/noticias/{slug}" in response.text


def test_robots_disallows_the_dashboard(client):
    assert "Disallow: /admin" in client.get("/robots.txt").text


# =============================== Content ==================================
def test_published_post_appears_in_the_list_and_on_its_page(client):
    slug = make_post(title="Encontro de negócios em Belém")
    assert "Encontro de negócios em Belém" in client.get("/noticias").text

    detail = client.get(f"/noticias/{slug}")
    assert detail.status_code == 200
    assert "Corpo do texto." in detail.text


def test_draft_is_invisible_to_the_public(client):
    slug = make_post(published=False, title="Rascunho secreto")
    assert "Rascunho secreto" not in client.get("/noticias").text
    assert client.get(f"/noticias/{slug}").status_code == 404


def test_search_filters_by_title(client):
    make_post(title="Design paraense em alta")
    make_post(title="Fotografia no interior")
    response = client.get("/noticias?q=design")
    assert "Design paraense em alta" in response.text
    assert "Fotografia no interior" not in response.text


def test_columns_do_not_leak_into_news(client):
    make_post(kind=PostKind.COLUMN, title="Coluna de opinião")
    assert "Coluna de opinião" not in client.get("/noticias").text
    assert "Coluna de opinião" in client.get("/colunas").text


def test_upcoming_and_past_events_are_separated(client):
    with Session(engine) as db:
        db.add(
            Event(
                slug="evento-futuro",
                title="Encontro que ainda vai acontecer",
                summary="Resumo do evento futuro para o teste.",
                description="Descrição.",
                starts_at=datetime.now(UTC) + timedelta(days=10),
                venue="Sede",
                published=True,
            )
        )
        db.add(
            Event(
                slug="evento-passado",
                title="Encontro que já aconteceu",
                summary="Resumo do evento passado para o teste.",
                description="Descrição.",
                starts_at=datetime.now(UTC) - timedelta(days=10),
                venue="Sede",
                published=True,
            )
        )
        db.commit()

    response = client.get("/eventos")
    assert "Encontro que ainda vai acontecer" in response.text
    assert "Encontro que já aconteceu" in response.text
    assert client.get("/eventos/evento-futuro").status_code == 200


# =========================== Text conversion ==============================
def test_text_to_html_handles_the_basics():
    html = text_to_html("## Título\n\n- um\n- dois\n\n**forte** e *leve*")
    assert "<h2>Título</h2>" in html
    assert html.count("<li>") == 2
    assert "<strong>forte</strong>" in html
    assert "<em>leve</em>" in html


def test_text_to_html_neutralises_script_tags():
    """Even a compromised dashboard account cannot inject HTML into the site."""
    html = text_to_html('<script>alert("xss")</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_only_http_links_become_anchors():
    assert 'href="https://exemplo.com"' in text_to_html("[ok](https://exemplo.com)")
    # A dangerous scheme is left as literal text, with no href at all.
    output = text_to_html("[x](javascript:alert(1))")
    assert "<a " not in output
    assert "href=" not in output


# =============================== Contact ==================================
def test_contact_form_stores_the_message(client):
    from app.models import ContactMessage

    data = {
        "name": "João da Silva",
        "email": "joao@exemplo.com",
        "subject": "Quero me associar",
        "message": "Gostaria de saber mais sobre as categorias de associação.",
    }
    response = client.post("/contato", data=data, follow_redirects=False)
    assert response.status_code == 303

    with Session(engine) as db:
        assert db.query(ContactMessage).count() == 1


def test_contact_form_rejects_bad_input(client):
    response = client.post("/contato", data={"name": "Jo", "email": "nao-e-email"})
    assert response.status_code == 422
    assert "E-mail inválido" in response.text


def test_contact_honeypot_silently_drops_bots(client):
    from app.models import ContactMessage

    data = {
        "name": "Robô Spam",
        "email": "spam@exemplo.com",
        "subject": "Outro assunto",
        "message": "compre seguidores agora mesmo neste link",
        "website": "http://spam.example",
    }
    client.post("/contato", data=data, follow_redirects=False)
    with Session(engine) as db:
        assert db.query(ContactMessage).count() == 0


# ============================== Dashboard =================================
def test_dashboard_requires_login(client):
    for path in ["/admin", "/admin/posts", "/admin/eventos", "/admin/associados"]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/entrar"


def test_login_fails_with_a_wrong_password(client, admin_email):
    client.get("/admin/entrar")
    csrf = client.cookies.get("ccpa_csrf")
    response = client.post(
        "/admin/entrar",
        data={"email": admin_email, "password": "errada", "csrf": csrf},
    )
    assert response.status_code == 401
    assert "incorretos" in response.text


def test_login_does_not_reveal_whether_an_account_exists(client, admin_email):
    client.get("/admin/entrar")
    csrf = client.cookies.get("ccpa_csrf")
    unknown = client.post(
        "/admin/entrar",
        data={"email": "ninguem@exemplo.com", "password": "x", "csrf": csrf},
    )
    known = client.post(
        "/admin/entrar",
        data={"email": admin_email, "password": "errada", "csrf": csrf},
    )
    assert unknown.status_code == known.status_code == 401


def test_login_without_csrf_is_refused(client, admin_email):
    response = client.post(
        "/admin/entrar", data={"email": admin_email, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 403


def test_login_opens_the_dashboard(logged_in):
    client, _ = logged_in
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Visão geral" in response.text


def test_publishing_from_the_dashboard_shows_it_on_the_site(logged_in):
    client, csrf = logged_in
    response = client.post(
        "/admin/posts/salvar",
        data={
            "csrf": csrf,
            "kind": "NEWS",
            "title": "Publicado pelo painel",
            "summary": "Resumo criado no teste do painel administrativo.",
            "body": "Texto com tamanho suficiente para passar na validação.",
            "author": "Maria Diretoria",
            "category": "Comunidade",
            "published": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Publicado pelo painel" in client.get("/noticias").text


def test_saving_without_publishing_keeps_it_as_a_draft(logged_in):
    client, csrf = logged_in
    client.post(
        "/admin/posts/salvar",
        data={
            "csrf": csrf,
            "kind": "NEWS",
            "title": "Ainda não publicado",
            "summary": "Resumo criado no teste do painel administrativo.",
            "body": "Texto com tamanho suficiente para passar na validação.",
            "author": "Maria Diretoria",
        },
        follow_redirects=False,
    )
    assert "Ainda não publicado" not in client.get("/noticias").text
    assert "Ainda não publicado" in client.get("/admin/posts?tipo=NEWS").text


def test_saving_a_post_without_csrf_is_refused(logged_in):
    client, _ = logged_in
    response = client.post(
        "/admin/posts/salvar",
        data={
            "kind": "NEWS",
            "title": "Tentativa sem token",
            "summary": "Resumo criado no teste do painel administrativo.",
            "body": "Texto com tamanho suficiente para passar na validação.",
            "author": "Maria",
            "csrf": "token-falso",
        },
    )
    assert response.status_code == 403


def test_identical_titles_get_different_slugs(logged_in):
    client, csrf = logged_in
    payload = {
        "csrf": csrf,
        "kind": "NEWS",
        "title": "Mesmo título",
        "summary": "Resumo criado no teste do painel administrativo.",
        "body": "Texto com tamanho suficiente para passar na validação.",
        "author": "Maria",
        "published": "on",
    }
    client.post("/admin/posts/salvar", data=payload, follow_redirects=False)
    client.post("/admin/posts/salvar", data=payload, follow_redirects=False)

    with Session(engine) as db:
        slugs = [p.slug for p in db.query(Post).all()]
    assert len(slugs) == len(set(slugs)) == 2


def test_logout_ends_the_session(logged_in):
    client, csrf = logged_in
    client.post("/admin/sair", data={"csrf": csrf}, follow_redirects=False)
    assert client.get("/admin", follow_redirects=False).status_code == 303


# ========================== Talent directory ==============================
def _add_member(**overrides):
    from app.models import EntityType, Member, MemberStatus

    defaults = {
        "entity_type": EntityType.PF,
        "plan_code": "PROFISSIONAL",
        "name": "Ativo Silva",
        "email": "ativo@exemplo.com",
        "login": "ativo",
        "password_hash": "x",
        "status": MemberStatus.ACTIVE,
    }
    defaults.update(overrides)
    with Session(engine) as db:
        db.add(Member(**defaults))
        db.commit()


def test_directory_lists_only_active_members(client):
    from app.models import MemberStatus

    _add_member(role="Diretor de arte", chapter="Belém")
    _add_member(
        name="Pendente Souza",
        email="pendente@exemplo.com",
        login="pendente",
        status=MemberStatus.AWAITING_PAYMENT,
    )

    response = client.get("/talentos")
    assert "Ativo Silva" in response.text
    assert "Pendente Souza" not in response.text


def test_directory_never_exposes_contact_details(client):
    _add_member(
        email="segredo@exemplo.com",
        mobile="91988887777",
        document="11144477735",
    )

    response = client.get("/talentos")
    assert "segredo@exemplo.com" not in response.text
    assert "91988887777" not in response.text
    assert "11144477735" not in response.text


def test_timezone_survives_a_missing_tzdata(monkeypatch):
    """Regression: on Windows without tzdata the app must still start."""
    import zoneinfo

    from app import templating

    def raise_missing(*args, **kwargs):
        raise zoneinfo.ZoneInfoNotFoundError("tzdata missing")

    monkeypatch.setattr(templating, "ZoneInfo", raise_missing)
    tz = templating._para_timezone()

    moment = datetime(2026, 3, 10, 15, 0, tzinfo=UTC).astimezone(tz)
    assert moment.hour == 12  # UTC-3


def test_home_renders_the_featured_post_fully(client):
    """Regression: Jinja renders an unknown variable as an empty string, so a
    renamed attribute leaves a silently blank card instead of an error."""
    make_post(title="Manchete em destaque na home")

    html = client.get("/").text
    assert "Manchete em destaque na home" in html
    assert "Resumo suficientemente longo para o teste." in html
    assert "Redação" in html


def test_event_row_renders_venue_and_date(client):
    """Same class of bug on the events list."""
    with Session(engine) as db:
        db.add(
            Event(
                slug="encontro-com-local",
                title="Encontro com local definido",
                summary="Resumo do evento para o teste de renderização.",
                description="Descrição.",
                starts_at=datetime.now(UTC) + timedelta(days=5),
                venue="Sede do CCPA",
                city="Belém",
                published=True,
            )
        )
        db.commit()

    html = client.get("/eventos").text
    assert "Encontro com local definido" in html
    assert "Sede do CCPA" in html
    assert "Belém" in html


def test_every_page_says_it_is_not_the_official_site(client):
    """Public portfolio copy: the club authorised it on the condition that it
    is clearly marked as an inspiration, not the official site."""
    for path in ("/", "/sobre", "/associe-se", "/admin/entrar"):
        page = client.get(path)
        assert "não é o site oficial" in page.text, path
        assert 'content="noindex, nofollow"' in page.text, path
