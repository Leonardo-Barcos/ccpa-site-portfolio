"""End-to-end tests for the signup flow."""

import os
import tempfile

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tempfile.gettempdir()}/ccpa_test.db"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["RESEND_API_KEY"] = ""  # keeps the tests from sending real mail

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.validators import is_valid_cnpj, is_valid_cpf  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


INDIVIDUAL = {
    "plan_code": "PROFISSIONAL",
    "name": "Maria da Silva Souza",
    "cpf": "111.444.777-35",
    "mobile": "(91) 98888-7777",
    "email": "maria@exemplo.com.br",
    "chapter": "Belém",
    "state": "PA",
    "city": "Belém",
    "postal_code": "66000-000",
    "login": "maria.silva",
    "password": "senha1234",
    "password_confirmation": "senha1234",
    "accepted_terms": "on",
}

COMPANY = {
    "plan_code": "EMPRESA",
    "legal_name": "Agência Criativa Ltda",
    "trade_name": "Agência Criativa",
    "cnpj": "11.222.333/0001-81",
    "chapter": "Santarém",
    "email": "contato@agencia.com.br",
    "login": "agencia.criativa",
    "password": "senha1234",
    "password_confirmation": "senha1234",
    "accepted_terms": "on",
}


# ----------------------------- validators ---------------------------------
def test_cpf_validator():
    assert is_valid_cpf("111.444.777-35")
    assert not is_valid_cpf("111.444.777-00")
    assert not is_valid_cpf("11111111111")  # repeated digits pass the maths


def test_cnpj_validator():
    assert is_valid_cnpj("11.222.333/0001-81")
    assert not is_valid_cnpj("11.222.333/0001-00")


# ------------------------------- pages ------------------------------------
def test_signup_page_serves_both_forms(client):
    response = client.get("/associe-se")
    assert response.status_code == 200
    assert 'action="/associe-se/pf"' in response.text
    assert 'action="/associe-se/pj"' in response.text
    for chapter in ("Belém", "Paragominas", "Santarém"):
        assert chapter in response.text


def test_security_headers_are_present(client):
    response = client.get("/associe-se")
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers


# ----------------------------- happy path ---------------------------------
def test_individual_signup_creates_charge_and_redirects(client):
    response = client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/associe-se/sucesso/")

    page = client.get(location)
    assert page.status_code == 200
    assert "Cadastro recebido" in page.text
    assert "/pagamento/simulado/" in page.text


def test_company_signup(client):
    response = client.post("/associe-se/pj", data=COMPANY, follow_redirects=False)
    assert response.status_code == 303


def test_confirmed_payment_activates_the_member(client):
    response = client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    member_id = response.headers["location"].rsplit("/", 1)[-1]

    client.post(f"/pagamento/simulado/{member_id}/confirmar", follow_redirects=False)
    page = client.get(f"/associe-se/sucesso/{member_id}")
    assert "Associação confirmada" in page.text


# ----------------------------- validation ---------------------------------
@pytest.mark.parametrize(
    "field,value,expected_text",
    [
        ("cpf", "111.444.777-00", "CPF inválido"),
        ("email", "nao-e-email", "Confira os campos"),
        ("password", "curta1", "Confira os campos"),
        ("mobile", "123", "Telefone inválido"),
    ],
)
def test_individual_form_rejects_bad_input(client, field, value, expected_text):
    data = {**INDIVIDUAL, field: value}
    if field == "password":
        data["password_confirmation"] = value
    response = client.post("/associe-se/pf", data=data)
    assert response.status_code == 422
    assert expected_text in response.text


def test_password_confirmation_must_match(client):
    response = client.post(
        "/associe-se/pf", data={**INDIVIDUAL, "password_confirmation": "outra1234"}
    )
    assert response.status_code == 422
    assert "não conferem" in response.text


def test_terms_are_mandatory(client):
    data = {k: v for k, v in INDIVIDUAL.items() if k != "accepted_terms"}
    response = client.post("/associe-se/pf", data=data)
    assert response.status_code == 422
    assert "termos de adesão" in response.text


def test_company_form_rejects_bad_cnpj(client):
    response = client.post(
        "/associe-se/pj", data={**COMPANY, "cnpj": "11.222.333/0001-00"}
    )
    assert response.status_code == 422
    assert "CNPJ inválido" in response.text


def test_company_chapter_is_mandatory(client):
    response = client.post("/associe-se/pj", data={**COMPANY, "chapter": ""})
    assert response.status_code == 422


def test_duplicate_email_is_rejected(client):
    client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    response = client.post(
        "/associe-se/pf", data={**INDIVIDUAL, "login": "outro.login", "cpf": ""}
    )
    assert response.status_code == 409
    assert "já existe uma associação" in response.text.lower()


def test_duplicate_login_is_rejected(client):
    client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    response = client.post(
        "/associe-se/pf",
        data={**INDIVIDUAL, "email": "outra@exemplo.com", "cpf": ""},
    )
    assert response.status_code == 409
    assert "login já está em uso" in response.text.lower()


def test_password_is_never_stored_in_plain_text(client):
    from sqlalchemy.orm import Session

    from app.models import Member

    client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    with Session(engine) as db:
        member = db.query(Member).first()
        assert member.password_hash.startswith("$argon2")
        assert INDIVIDUAL["password"] not in member.password_hash


def test_welcome_email_attempt_is_logged(client):
    from sqlalchemy.orm import Session

    from app.models import EmailLog

    client.post("/associe-se/pf", data=INDIVIDUAL, follow_redirects=False)
    with Session(engine) as db:
        entry = db.query(EmailLog).first()
        assert entry is not None
        assert entry.template == "welcome"


def test_webhook_rejects_a_bad_token(monkeypatch, client):
    from app.config import settings

    monkeypatch.setattr(settings, "payment_provider", "asaas")
    monkeypatch.setattr(settings, "asaas_webhook_token", "segredo")
    response = client.post(
        "/webhooks/pagamento",
        json={"event": "PAYMENT_CONFIRMED"},
        headers={"asaas-access-token": "errado"},
    )
    assert response.status_code == 401


def test_empty_optional_fields_do_not_break_the_form(client):
    """Regression: HTML posts "" for untouched fields, which must not be
    parsed as an invalid date or e-mail."""
    data = {
        **INDIVIDUAL,
        "birth_date": "",
        "secondary_email": "",
        "id_card": "",
        "secondary_phone": "",
        "linkedin": "",
        "gender": "",
    }
    response = client.post("/associe-se/pf", data=data, follow_redirects=False)
    assert response.status_code == 303


def test_error_messages_are_in_portuguese(client):
    data = {k: v for k, v in INDIVIDUAL.items() if k != "name"}
    response = client.post("/associe-se/pf", data=data)
    assert "Campo obrigatório" in response.text
