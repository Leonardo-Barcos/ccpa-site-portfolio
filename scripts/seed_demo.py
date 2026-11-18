"""Fill the database with demo content so the site can be seen populated.

    python scripts/seed_demo.py

For demos and development only. Every post, author and event here is fictional — delete it through the
dashboard before going live.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.models import Event, Post, PostKind  # noqa: E402
from app.services.content import unique_slug  # noqa: E402

NOW = datetime.now(UTC)

POSTS = [
    (
        PostKind.NEWS,
        "CCPA abre inscrições para o encontro de negócios de Belém",
        "Mercado",
        "Rodada reúne associados e empresas para apresentar trabalhos e fechar "
        "parcerias. As vagas são limitadas ao espaço da sede.",
        "Ana Marques",
        """O encontro mensal de negócios do Clube de Criativos do Pará chega à sua nova edição em Belém, e desta vez com um formato mais direto.

## Como funciona

Cada participante tem cinco minutos para apresentar o que faz e o que procura. Depois, a rodada abre para conversas livres — que é quando, na prática, os negócios acontecem.

- Aberto a associados de todas as categorias
- Empresas associadas podem levar um convidado
- Não é preciso levar apresentação pronta

> A gente cansou de ver bom trabalho paraense sendo descoberto só em São Paulo.

Quem ainda não é associado pode se inscrever pelo site e participar já nesta edição.""",
    ),
    (
        PostKind.NEWS,
        "Banco de talentos do clube passa a listar estudantes",
        "Comunidade",
        "A partir desta semana, estudantes associados também aparecem na busca "
        "de talentos aberta a quem contrata.",
        "Redação CCPA",
        """O banco de talentos do CCPA agora inclui estudantes, e não apenas profissionais já estabelecidos.

A mudança responde a um pedido antigo das agências associadas, que reclamavam da dificuldade de encontrar estagiário e assistente com portfólio na região.

## O que muda

Quem se associa na categoria Estudante passa a ter nome, curso e regional visíveis na busca. E-mail, telefone e documentos continuam fora — a página nunca expõe dado de contato.""",
    ),
    (
        PostKind.NEWS,
        "Regional de Santarém recebe primeira roda de conversa do ano",
        "Eventos",
        "O oeste do Pará entra no calendário do clube com um encontro sobre "
        "produção criativa fora da capital.",
        "Redação CCPA",
        """A regional de Santarém realiza sua primeira atividade do ano, com foco em quem produz criatividade longe do eixo de Belém.

A conversa vai tratar de precificação, acesso a clientes de outras cidades e o que muda quando o profissional criativo trabalha a partir do interior.""",
    ),
    (
        PostKind.COLUMN,
        "Criatividade paraense não precisa de sotaque neutro",
        "Carreira",
        "Por que apagar a origem do trabalho para agradar cliente de fora "
        "costuma sair mais caro do que parece.",
        "Marcos Tavares",
        """Existe um reflexo antigo no mercado criativo do Norte: para parecer profissional, apague de onde você veio.

## O custo de parecer genérico

O trabalho fica indistinguível do que se faz em qualquer lugar — e, indistinguível, ele compete só por preço.

> Quando tudo parece igual, o cliente escolhe pelo mais barato.

O caminho contrário dá mais trabalho e rende mais: assumir repertório, referência e linguagem daqui como diferencial, não como limitação.""",
    ),
    (
        PostKind.COLUMN,
        "O portfólio que ninguém vê não existe",
        "Design",
        "Uma provocação sobre o hábito de guardar os melhores trabalhos para "
        "quando estiverem perfeitos.",
        "Juliana Costa",
        """Todo mundo do clube conhece alguém com uma pasta cheia de trabalho bom que nunca foi publicado.

A justificativa é sempre parecida: falta ajustar uma coisa, falta pedir autorização, falta tempo de montar direito.

## O trabalho publicado trabalha por você

Enquanto o portfólio não sai, ele não gera indicação, não aparece em busca e não convence ninguém. Publicar imperfeito e ajustar depois rende mais do que a perfeição que nunca chega.""",
    ),
]

EVENTS = [
    (
        "Encontro mensal de negócios — Belém",
        "Rodada de apresentações e networking entre associados e empresas "
        "parceiras do clube.",
        NOW + timedelta(days=12),
        "Sede do CCPA",
        "Belém",
        "Belém",
        True,
        """Rodada mensal do clube, com apresentações rápidas e conversa aberta depois.

## Programação

- 19h — Credenciamento
- 19h30 — Apresentações relâmpago
- 20h30 — Networking livre

Aberto a todos os associados. Empresas associadas podem levar um convidado.""",
    ),
    (
        "Roda de conversa: precificar trabalho criativo",
        "Como montar preço sem se subvalorizar nem perder o cliente — com "
        "exemplos reais do mercado paraense.",
        NOW + timedelta(days=27),
        "Auditório da regional",
        "Santarém",
        "Santarém",
        True,
        """Uma conversa prática sobre a pergunta que mais aparece no grupo do clube: quanto cobrar.

Vamos discutir hora técnica, valor por projeto e o que fazer quando o cliente pede desconto.""",
    ),
    (
        "Mostra de portfólios — estudantes",
        "Estudantes apresentam projetos e recebem avaliação de profissionais "
        "que estão no mercado.",
        NOW - timedelta(days=20),
        "Sede do CCPA",
        "Belém",
        "Belém",
        True,
        """Edição já realizada da mostra de portfólios, com avaliação individual dos trabalhos apresentados.""",
    ),
]


def main() -> int:
    init_db()
    created = {"posts": 0, "events": 0}

    with Session(engine) as db:
        for kind, title, category, summary, author, body in POSTS:
            if db.scalars(select(Post).where(Post.title == title)).first():
                continue
            db.add(
                Post(
                    kind=kind,
                    slug=unique_slug(db, Post, title),
                    title=title,
                    summary=summary,
                    body=body,
                    author=author,
                    category=category,
                    published=True,
                    published_at=NOW - timedelta(days=created["posts"] * 3),
                )
            )
            created["posts"] += 1
            db.flush()

        for title, summary, starts_at, venue, city, chapter, free, description in EVENTS:
            if db.scalars(select(Event).where(Event.title == title)).first():
                continue
            db.add(
                Event(
                    slug=unique_slug(db, Event, title),
                    title=title,
                    summary=summary,
                    description=description,
                    starts_at=starts_at,
                    venue=venue,
                    city=city,
                    chapter=chapter,
                    free=free,
                    published=True,
                )
            )
            created["events"] += 1
            db.flush()

        db.commit()

    print(
        f"Conteúdo de exemplo criado: {created['posts']} publicações e "
        f"{created['events']} eventos."
    )
    print("Lembre-se de apagar tudo pelo painel antes de colocar o site no ar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
