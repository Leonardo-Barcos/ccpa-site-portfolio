"""Membership plan catalogue.

Amounts are stored in CENTS on purpose: money in floats eventually produces a
rounding error, and this is the number the member is charged.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    audience: str  # "PF" for individuals, "PJ" for companies
    amount_cents: int
    cycle: str = "MONTHLY"
    description: str = ""
    benefits: tuple[str, ...] = field(default_factory=tuple)

    @property
    def amount_brl(self) -> str:
        """Brazilian formatting: thousands with '.', decimals with ','."""
        return (
            f"{self.amount_cents / 100:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    @property
    def cycle_label(self) -> str:
        return "/mês" if self.cycle == "MONTHLY" else "/ano"


SHARED_BENEFITS: tuple[str, ...] = (
    "Encontro mensal de negócios",
    "40% de desconto no e-commerce do Clube de Criação do Rio de Janeiro",
)

PLANS: dict[str, Plan] = {
    "ESTUDANTE": Plan(
        code="ESTUDANTE",
        name="Estudante",
        audience="PF",
        amount_cents=2990,
        cycle="MONTHLY",
        description="Para estudantes de cursos da cadeia criativa.",
        benefits=(
            "Avaliação de projetos por um profissional ativo no mercado",
            *SHARED_BENEFITS,
        ),
    ),
    "PROFISSIONAL": Plan(
        code="PROFISSIONAL",
        name="Profissional",
        audience="PF",
        amount_cents=4490,
        cycle="MONTHLY",
        description="Para profissionais atuantes na cadeia criativa.",
        benefits=(
            "Micro pesquisa — avaliação inicial da sua atuação e do seu negócio",
            "Participação na rede de profissionais do CCPA",
            *SHARED_BENEFITS,
        ),
    ),
    "EMPRESA": Plan(
        code="EMPRESA",
        name="Empresa",
        audience="PJ",
        amount_cents=6990,
        cycle="MONTHLY",
        description="Para empresas que querem entender e melhorar o próprio negócio "
        "junto com a rede criativa do Pará.",
        benefits=(
            "Micro pesquisa — avaliação inicial da empresa e do negócio, com "
            "diagnóstico do que pode ser melhorado",
            "Acesso à rede de profissionais e estudantes do CCPA",
            *SHARED_BENEFITS,
        ),
    ),
}

CHAPTERS: tuple[str, ...] = ("Belém", "Paragominas", "Santarém")

GENDERS: tuple[str, ...] = (
    "Feminino",
    "Masculino",
    "Não-binário",
    "Outro",
    "Prefiro não informar",
)

STATES: tuple[str, ...] = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
)  # fmt: skip


def plans_for(audience: str) -> list[Plan]:
    return [p for p in PLANS.values() if p.audience == audience]
