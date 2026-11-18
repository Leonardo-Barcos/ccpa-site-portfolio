"""Institutional copy for the public site.

Every piece of identity text lives here rather than in a template, so a board
member can ask for a wording change and only one file is touched — with no
chance of breaking HTML.

Editorial content (news, columns, events) is NOT here: it comes from the
database, written through the admin dashboard.

The strings themselves stay in Brazilian Portuguese, since that is what the
site's visitors read.
"""

from dataclasses import dataclass

# --------------------------------------------------------------------------
#  Identity
# --------------------------------------------------------------------------
NAME = "Clube de Criativos do Pará"
SHORT_NAME = "CCPA"
TAGLINE = "Valoriza, registra e fomenta a criatividade no estado."
SHORT_DESCRIPTION = (
    "O Clube de Criativos do Pará é uma associação que valoriza, registra e "
    "fomenta a criatividade paraense, reunindo profissionais, estudantes e "
    "empresas de toda a cadeia criativa."
)

# This copy is a public portfolio piece, not the club's official site. The
# notice is shown on every page and e-mail, so nobody mistakes a running copy
# for the real thing.
PORTFOLIO_NOTICE = (
    "Projeto de portfólio inspirado no Clube de Criativos do Pará — não é o site oficial."
)
OFFICIAL_SITE = "https://www.ccpara.com.br"

EMAIL = "criativosdopara@gmail.com"
SPONSOR_URL = "https://mangacode.com.br"

SOCIAL_LINKS = [
    ("Instagram", "https://www.instagram.com/cc.para/"),
    ("LinkedIn", "https://www.linkedin.com/company/101630565/"),
    ("YouTube", "https://www.youtube.com/@clubedecriativosdopara/videos"),
    ("Facebook", "https://www.facebook.com/groups/ccpara"),
    ("Spotify", "https://open.spotify.com/show/1w4fczOAWBggRBpue0zNVN"),
    ("Discord", "https://discord.gg/c9vjbjPv"),
]

# URLs stay in Portuguese: they are user facing and already indexed.
NAV = [
    ("Home", "/"),
    ("Sobre nós", "/sobre"),
    ("Notícias", "/noticias"),
    ("Eventos", "/eventos"),
    ("Colunas", "/colunas"),
    ("Banco de Talentos", "/talentos"),
    ("Contato", "/contato"),
]

CHAPTER_BLURBS = [
    (
        "Belém",
        "A regional da capital, onde nasceu o clube e acontece a maior parte "
        "dos encontros.",
    ),
    (
        "Paragominas",
        "Leva a rede criativa para o sudeste do Pará, conectando profissionais "
        "fora do eixo da capital.",
    ),
    (
        "Santarém",
        "Representa o oeste paraense e o Baixo Amazonas na cadeia criativa do estado.",
    ),
]


# --------------------------------------------------------------------------
#  Home page
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Block:
    title: str
    text: str
    color: str = "verde"


WHAT_WE_DO: tuple[Block, ...] = (
    Block(
        "Valoriza",
        "Reconhece e dá palco a quem produz criatividade no Pará — do estúdio "
        "de design à agência, do ilustrador ao fotógrafo.",
        "verde",
    ),
    Block(
        "Registra",
        "Documenta a produção criativa paraense para que ela não se perca: "
        "acervo, colunas, podcast e o registro dos trabalhos do estado.",
        "vermelho",
    ),
    Block(
        "Fomenta",
        "Cria oportunidades reais de negócio e formação, aproximando "
        "estudantes, profissionais e empresas da cadeia criativa.",
        "azul",
    ),
    Block(
        "Conecta",
        "Encontros mensais, comunidade ativa e um banco de talentos que "
        "coloca quem contrata na frente de quem faz.",
        "amarelo",
    ),
)

WHO_ITS_FOR: tuple[Block, ...] = (
    Block(
        "Estudantes",
        "Quem está começando e quer ter o próprio projeto avaliado por alguém "
        "que já está no mercado.",
        "verde",
    ),
    Block(
        "Profissionais",
        "Designers, redatores, ilustradores, fotógrafos, diretores de arte e "
        "todo mundo que vive de criar.",
        "vermelho",
    ),
    Block(
        "Empresas",
        "Negócios que querem entender a própria comunicação e encontrar "
        "talento criativo perto de casa.",
        "azul",
    ),
)

HIGHLIGHT_NUMBERS = (
    ("3", "regionais no estado"),
    ("12", "encontros por ano"),
    ("40%", "de desconto no Clube de Criação do Rio"),
    ("1", "clube para toda a cadeia criativa"),
)


# --------------------------------------------------------------------------
#  About page
# --------------------------------------------------------------------------
ABOUT_INTRO = (
    "O Clube de Criativos do Pará nasceu de uma inquietação simples: muita "
    "coisa boa é criada no Pará e quase nada disso fica registrado. Trabalhos "
    "que mereciam prêmio somem no feed, profissionais excelentes seguem "
    "invisíveis fora do próprio círculo, e empresas contratam de fora sem "
    "saber que o talento estava na esquina."
)

ABOUT_SECTIONS = [
    (
        "O que a gente faz",
        "Somos uma associação sem fins lucrativos que reúne a cadeia criativa "
        "do estado — publicidade, design, ilustração, fotografia, audiovisual "
        "e redação. Promovemos encontros de negócios, produzimos conteúdo "
        "sobre a produção local, mantemos um banco de talentos aberto a quem "
        "contrata e damos aos associados acesso a avaliações e benefícios que "
        "sozinhos seriam difíceis de alcançar.",
    ),
    (
        "Por que se associar",
        "Porque criatividade isolada rende pouco. Associado, você entra numa "
        "rede que gera indicação, participa dos encontros mensais de negócios, "
        "recebe uma avaliação do seu trabalho ou do seu negócio feita por "
        "quem está no mercado e ganha desconto no e-commerce do Clube de "
        "Criação do Rio de Janeiro.",
    ),
    (
        "Como nos organizamos",
        "O clube se estrutura em regionais, para que a criatividade paraense "
        "não fique concentrada só na capital. Cada regional tem sua agenda de "
        "encontros e seus associados, e todas compartilham os mesmos "
        "benefícios e a mesma rede.",
    ),
]

CONTACT_SUBJECTS = (
    "Quero me associar",
    "Sou empresa e quero apoiar",
    "Imprensa",
    "Parcerias e eventos",
    "Banco de talentos",
    "Outro assunto",
)
