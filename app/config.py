"""Application settings, loaded from the environment (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Clube de Criativos do Pará"
    app_env: Literal["development", "production"] = "development"
    base_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-key-troque-em-producao"

    database_url: str = "sqlite+pysqlite:///./ccpa.db"

    # Resend
    resend_api_key: str = ""
    mail_from: str = "CCPA <associados@ccpara.com.br>"
    mail_reply_to: str = "criativosdopara@gmail.com"
    mail_bcc_admin: str = ""

    # Payments
    payment_provider: Literal["mock", "asaas", "manual"] = "mock"
    payment_static_link: str = ""

    asaas_api_key: str = ""
    asaas_base_url: str = "https://api.asaas.com/v3"
    asaas_webhook_token: str = ""

    # Bank account shown in the billing e-mail as a Pix/transfer alternative
    bank_name: str = "Caixa Econômica Federal"
    bank_agencia: str = "0000"
    bank_operacao: str = "003"
    bank_conta: str = "00000-0"
    bank_pix_key: str = ""
    bank_titular: str = "Clube de Criativos do Pará"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
