"""Pydantic schemas — every user submission passes through here before the
database sees it.

Validation messages stay in Portuguese because they are rendered straight into
the form the visitor is looking at.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .plans import CHAPTERS, GENDERS, PLANS, STATES
from .validators import (
    digits_only,
    is_valid_cnpj,
    is_valid_cpf,
    is_valid_phone,
    is_valid_postal_code,
)

MIN_PASSWORD_LENGTH = 8


class _Base(BaseModel):
    model_config = {"str_strip_whitespace": True, "extra": "ignore"}


class ContactAndAddressMixin(_Base):
    """Fields shared by the individual and company signup forms."""

    mobile: str | None = None
    secondary_phone: str | None = None
    email: EmailStr
    secondary_email: EmailStr | None = None

    postal_code: str | None = None
    street: str | None = Field(default=None, max_length=255)
    number: str | None = Field(default=None, max_length=20)
    district: str | None = Field(default=None, max_length=120)
    state: str | None = None
    city: str | None = Field(default=None, max_length=120)
    address_extra: str | None = Field(default=None, max_length=255)

    login: str = Field(min_length=4, max_length=60)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    password_confirmation: str
    accepted_terms: bool

    @field_validator("mobile", "secondary_phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not is_valid_phone(v):
            raise ValueError("Telefone inválido. Informe DDD + número.")
        return digits_only(v)

    @field_validator("postal_code")
    @classmethod
    def _postal_code(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not is_valid_postal_code(v):
            raise ValueError("CEP inválido.")
        return digits_only(v)

    @field_validator("state")
    @classmethod
    def _state(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.upper()
        if v not in STATES:
            raise ValueError("UF inválida.")
        return v

    @field_validator("login")
    @classmethod
    def _login(cls, v: str) -> str:
        v = v.lower()
        if not v.replace(".", "").replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "O login pode conter apenas letras, números, ponto, hífen e underline."
            )
        return v

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("A senha deve conter ao menos uma letra e um número.")
        return v

    @model_validator(mode="after")
    def _final_checks(self):
        if self.password != self.password_confirmation:
            raise ValueError("As senhas não conferem.")
        if not self.accepted_terms:
            raise ValueError("É necessário aceitar os termos de adesão.")
        return self


class IndividualSignup(ContactAndAddressMixin):
    """Signup form for a student or a working professional."""

    plan_code: str
    name: str = Field(min_length=3, max_length=180)
    cpf: str | None = None
    id_card: str | None = Field(default=None, max_length=20)
    birth_date: date | None = None
    gender: str | None = None
    linkedin: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=180)
    role: str | None = Field(default=None, max_length=120)
    chapter: str | None = None
    mobile: str  # required for individuals

    @field_validator("plan_code")
    @classmethod
    def _plan(cls, v: str) -> str:
        plan = PLANS.get(v)
        if not plan or plan.audience != "PF":
            raise ValueError("Tipo de associado inválido.")
        return v

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not is_valid_cpf(v):
            raise ValueError("CPF inválido.")
        return digits_only(v)

    @field_validator("gender")
    @classmethod
    def _gender(cls, v: str | None) -> str | None:
        if v and v not in GENDERS:
            raise ValueError("Gênero inválido.")
        return v or None

    @field_validator("chapter")
    @classmethod
    def _chapter(cls, v: str | None) -> str | None:
        if v and v not in CHAPTERS:
            raise ValueError("Regional inválida.")
        return v or None


class CompanySignup(ContactAndAddressMixin):
    """Signup form for a member company."""

    plan_code: str
    legal_name: str = Field(min_length=3, max_length=180)
    trade_name: str = Field(min_length=2, max_length=180)
    cnpj: str
    state_registration: str | None = Field(default=None, max_length=30)
    city_registration: str | None = Field(default=None, max_length=30)
    chapter: str
    website: str | None = Field(default=None, max_length=255)

    @field_validator("plan_code")
    @classmethod
    def _plan(cls, v: str) -> str:
        plan = PLANS.get(v)
        if not plan or plan.audience != "PJ":
            raise ValueError("Tipo de associado inválido.")
        return v

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if not is_valid_cnpj(v):
            raise ValueError("CNPJ inválido.")
        return digits_only(v)

    @field_validator("chapter")
    @classmethod
    def _chapter(cls, v: str) -> str:
        if v not in CHAPTERS:
            raise ValueError("Selecione uma regional válida.")
        return v
