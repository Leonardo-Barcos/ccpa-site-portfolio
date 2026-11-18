"""Render the transactional e-mails to HTML for visual review. Sends nothing.

python scripts/preview_emails.py  ->  ./preview/welcome.html, etc.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.plans import PLANS  # noqa: E402
from app.services.email import _render  # noqa: E402


class FakeMember:
    id = "d0ad0450-3a56-4062-ae68-7103c86c294f"
    name = "Leonardo Jacomini Barcos"
    trade_name = None
    first_name = "Leonardo"
    email = "leonardo@exemplo.com"
    login = "leo.jb"
    chapter = "Belém"


def main() -> None:
    out_dir = Path("preview")
    out_dir.mkdir(exist_ok=True)
    member = FakeMember()
    plan = PLANS["PROFISSIONAL"]

    pages = {
        "welcome": {
            "member": member,
            "plan": plan,
            "checkout_url": "https://pagamento.exemplo.com/abc123",
            "cfg": settings,
        },
        "payment_confirmed": {"member": member, "plan": plan, "cfg": settings},
    }
    for name, context in pages.items():
        path = out_dir / f"{name}.html"
        path.write_text(_render(name, context), encoding="utf-8")
        print("gerado:", path)


if __name__ == "__main__":
    main()
