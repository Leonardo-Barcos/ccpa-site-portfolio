"""Create a dashboard user, or reset the password of an existing one.

    python scripts/create_admin.py

The password is asked for interactively so it never lands in the shell
history. If the address already exists the script offers to reset it — that is
how access is recovered when someone forgets their password.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.models import AdminUser  # noqa: E402
from app.security import hash_password  # noqa: E402

MIN_PASSWORD = 10


def ask_password() -> str | None:
    password = getpass.getpass("Senha (mínimo 10 caracteres): ")
    if len(password) < MIN_PASSWORD:
        print(f"Senha muito curta — use pelo menos {MIN_PASSWORD} caracteres.")
        return None
    if password != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.")
        return None
    return password


def main() -> int:
    init_db()

    email = input("E-mail: ").strip().lower()
    if "@" not in email:
        print("E-mail inválido.")
        return 1

    with Session(engine) as db:
        existing = db.scalars(
            select(AdminUser).where(func.lower(AdminUser.email) == email)
        ).first()

        if existing:
            print(f"Já existe um usuário com esse e-mail ({existing.name}).")
            if input("Redefinir a senha dele? [s/N] ").strip().lower() != "s":
                print("Nada foi alterado.")
                return 0
            password = ask_password()
            if not password:
                return 1
            existing.password_hash = hash_password(password)
            existing.active = True
            db.commit()
            print(f"Senha redefinida para {existing.email}.")
            return 0

        name = input("Nome completo: ").strip()
        if len(name) < 3:
            print("Informe o nome.")
            return 1

        password = ask_password()
        if not password:
            return 1

        db.add(AdminUser(name=name, email=email, password_hash=hash_password(password)))
        db.commit()

    print(f"\nUsuário criado. Entre em /admin/entrar com {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
