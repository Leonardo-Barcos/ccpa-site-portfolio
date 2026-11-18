"""Full pre-deploy verification — this project's `npm run build`.

Python is not compiled, so there is no build step that fails when the code is
wrong: a bad import or a `{% endblok %}` in a template only surfaces when
somebody opens the page. This script tries to break the application on
purpose instead: it imports everything, compiles every template, runs the
tests and actually starts the server.

    python check.py

Exits 0 when everything passes and 1 when anything fails, which is what lets
the pre-commit hook and GitHub Actions block a broken deploy.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

GREEN, RED, YELLOW, GREY, RESET = (
    "\033[32m",
    "\033[31m",
    "\033[33m",
    "\033[90m",
    "\033[0m",
)
if os.name == "nt":  # enables ANSI colours on older PowerShell
    os.system("")

failures: list[str] = []
warnings: list[str] = []


def heading(text: str) -> None:
    print(f"\n{GREY}{'─' * 62}{RESET}\n  {text}")


def ok(text: str) -> None:
    print(f"  {GREEN}OK{RESET}     {text}")


def fail(stage: str, text: str) -> None:
    print(f"  {RED}FALHOU{RESET} {text}")
    failures.append(stage)


def warn(text: str) -> None:
    print(f"  {YELLOW}AVISO{RESET}  {text}")
    warnings.append(text)


def run(command: list[str]) -> tuple[int, str]:
    process = subprocess.run(command, capture_output=True, text=True)
    return process.returncode, (process.stdout + process.stderr).strip()


# --------------------------------------------------------------------------
# 1. Dependencies installed and mutually compatible
# --------------------------------------------------------------------------
def check_dependencies() -> None:
    heading("1/6  Dependências")
    code, output = run([sys.executable, "-m", "pip", "check"])
    if code == 0:
        ok("nenhum conflito de versão entre os pacotes")
    else:
        fail("dependências", "pip check reclamou:")
        print(f"{GREY}{output}{RESET}")


# --------------------------------------------------------------------------
# 2. Static analysis — catches what a compiler would: undefined names, dead
#    imports, unused variables, f-strings with no placeholder
# --------------------------------------------------------------------------
def check_lint() -> None:
    heading("2/6  Análise estática (ruff)")
    code, output = run([sys.executable, "-m", "ruff", "check", "."])
    if "No module named" in output:
        warn("ruff não instalado — rode: pip install -r requirements-dev.txt")
        return
    if code == 0:
        ok("nenhum problema encontrado no código")
    else:
        fail("lint", "o ruff encontrou problemas:")
        print(f"{GREY}{output}{RESET}")
        print(f"{GREY}  (muitos deles se corrigem com: ruff check --fix .){RESET}")

    code, output = run([sys.executable, "-m", "ruff", "format", "--check", "."])
    if code == 0:
        ok("formatação consistente")
    else:
        warn("arquivos fora do padrão de formatação — rode: ruff format .")


# --------------------------------------------------------------------------
# 3. Templates — a Jinja error only fires when the page is opened, so every
#    template gets compiled here
# --------------------------------------------------------------------------
def check_templates() -> None:
    heading("3/6  Templates")
    from jinja2 import TemplateSyntaxError

    # The REAL application environment, with our filters and globals
    # registered — a bare one would report our own filters as missing.
    from app.templating import templates

    folder = ROOT / "app" / "templates"
    env = templates.env
    files = sorted(folder.rglob("*.html"))

    if not files:
        fail("templates", "nenhum template encontrado em app/templates")
        return

    broken = 0
    for path in files:
        name = path.relative_to(folder).as_posix()
        try:
            env.get_template(name)
        except TemplateSyntaxError as error:
            fail("templates", f"{name}, linha {error.lineno}: {error.message}")
            broken += 1
        except Exception as error:  # noqa: BLE001
            fail("templates", f"{name}: {error}")
            broken += 1

    if not broken:
        ok(f"{len(files)} templates compilam sem erro de sintaxe")


# --------------------------------------------------------------------------
# 4. Configuration — every Settings field must be documented in .env.example,
#    otherwise somebody deploys without knowing a key was missing
# --------------------------------------------------------------------------
def check_configuration() -> None:
    heading("4/6  Configuração")
    from app.config import Settings, settings

    example = ROOT / ".env.example"
    if not example.exists():
        fail("configuração", ".env.example não existe")
        return

    text = example.read_text(encoding="utf-8").upper()
    missing = [f.upper() for f in Settings.model_fields if f.upper() not in text]

    if missing:
        warn(".env.example não documenta: " + ", ".join(sorted(missing)))
    else:
        ok(f"as {len(Settings.model_fields)} variáveis estão no .env.example")

    if settings.is_prod:
        if settings.secret_key.startswith("dev-"):
            fail("configuração", "SECRET_KEY ainda é a de desenvolvimento")
        if not settings.resend_api_key:
            fail("configuração", "RESEND_API_KEY vazia em produção")
        if settings.payment_provider == "mock":
            fail("configuração", "PAYMENT_PROVIDER=mock em produção")
        if settings.base_url.startswith("http://"):
            fail("configuração", "BASE_URL sem HTTPS em produção")
        if "sqlite" in settings.database_url:
            warn("produção usando SQLite — o recomendado é PostgreSQL")
        if not failures:
            ok("configuração de produção coerente")
    else:
        ok("rodando em modo desenvolvimento (checagens de produção puladas)")


# --------------------------------------------------------------------------
# 5. Test suite
# --------------------------------------------------------------------------
def check_tests() -> None:
    heading("5/6  Testes automatizados")
    code, output = run([sys.executable, "-m", "pytest", "-q"])
    last_line = output.strip().splitlines()[-1] if output.strip() else ""
    if code == 0:
        ok(last_line or "todos os testes passaram")
    else:
        fail("testes", "algum teste falhou:")
        print(f"{GREY}{output[-3000:]}{RESET}")


# --------------------------------------------------------------------------
# 6. Smoke test — start the real app and hit the real routes. This is what
#    catches failures that only exist at runtime.
# --------------------------------------------------------------------------
def check_smoke() -> None:
    heading("6/6  A aplicação sobe e responde")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./check.db")

    import logging

    for noisy in ("httpx", "asyncio", "ccpa.email"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        from fastapi.testclient import TestClient

        from app.main import app
    except Exception as error:  # noqa: BLE001
        fail("fumaça", f"a aplicação nem importa: {error}")
        return

    routes = [
        ("/healthz", 200),
        ("/", 200),
        ("/sobre", 200),
        ("/noticias", 200),
        ("/colunas", 200),
        ("/eventos", 200),
        ("/talentos", 200),
        ("/contato", 200),
        ("/associe-se", 200),
        ("/associe-se?tipo=pj", 200),
        ("/robots.txt", 200),
        ("/sitemap.xml", 200),
        ("/associe-se/sucesso/nao-existe", 302),
        ("/admin", 303),  # the dashboard must require a login
        ("/admin/entrar", 200),
        ("/rota-que-nao-existe", 404),
    ]

    started = time.time()
    try:
        with TestClient(app, follow_redirects=False) as client:
            for path, expected in routes:
                status = client.get(path).status_code
                if status != expected:
                    fail("fumaça", f"GET {path} devolveu {status}, esperado {expected}")
                else:
                    ok(f"GET {path} → {expected}")

            signup = client.get("/associe-se").text
            for marker, description in (
                ('action="/associe-se/pf"', "formulário de pessoa física"),
                ('action="/associe-se/pj"', "formulário de empresa"),
                ("/static/css/ccpa.css", "folha de estilo"),
                ("/static/js/form.js", "script do formulário"),
                ("/static/img/logo-ccpa.png", "logo"),
            ):
                if marker not in signup:
                    fail("fumaça", f"a página não traz {description}")

            home = client.get("/").text
            for marker, description in (
                ("/static/js/site.js", "script do site"),
                ('href="/associe-se"', "chamada para associação"),
                ("Clube de Criativos do Pará", "nome da entidade"),
            ):
                if marker not in home:
                    fail("fumaça", f"a home não traz {description}")

            for asset in (
                "app/static/css/ccpa.css",
                "app/static/js/form.js",
                "app/static/js/site.js",
                "app/static/img/logo-ccpa.png",
            ):
                if not (ROOT / asset).exists():
                    fail("fumaça", f"arquivo estático ausente: {asset}")

            if not (ROOT / "app/static/termos-de-adesao.pdf").exists():
                warn(
                    "app/static/termos-de-adesao.pdf ainda não existe — "
                    "o link dos termos vai dar 404"
                )
    except Exception as error:  # noqa: BLE001
        fail("fumaça", f"erro ao rodar a aplicação: {error}")
    finally:
        (ROOT / "check.db").unlink(missing_ok=True)

    print(f"{GREY}         ({time.time() - started:.1f}s){RESET}")


# --------------------------------------------------------------------------
def main() -> int:
    print(f"\n{GREY}  Verificando o projeto CCPA{RESET}")

    check_dependencies()
    check_lint()
    check_templates()
    check_configuration()
    check_tests()
    check_smoke()

    print(f"\n{GREY}{'─' * 62}{RESET}")
    if warnings:
        print(f"  {YELLOW}{len(warnings)} aviso(s){RESET} — não impedem o deploy.")
    if failures:
        stages = ", ".join(dict.fromkeys(failures))
        print(f"  {RED}REPROVADO{RESET} em: {stages}")
        print("  Corrija antes de subir.\n")
        return 1

    print(f"  {GREEN}APROVADO{RESET} — pode subir.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
