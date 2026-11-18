"""Heurísticas de classificação automática de e-mails.

Regras:
  * Nº SEI: padrão `00000.000000/0000-00`.
  * Prazo Externo: data explícita próxima de "prazo", "até" ou "limite"
    (dd/mm/aaaa) ou menção relativa ("X dias"). Havendo "dias úteis" na
    vizinhança do trecho, a contagem pula sábados e domingos.
  * Prazo Interno: 2 dias antes do externo (1 dia se o prazo for curto,
    até 4 dias; 3 dias para Ministério Público e Tribunal de Contas),
    ajustado para não cair em fim de semana.
  * Prioridade: Alta para órgãos de controle ou prazo em até 5 dias.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

from .models import Classificacao

DIAS_INTERNOS_CONTROLE: int = 3
DIAS_INTERNOS_PADRAO: int = 2
DIAS_CURTO_PRAZO: int = 4
DIAS_PRIORIDADE_ALTA: int = 5
JANELA_DIAS_UTEIS: int = 40

PREFIXOS_ASSUNTO: tuple[str, ...] = ("re:", "fw:", "fwd:", "enc:", "res:", "tr:")

RE_SEI = re.compile(r"\b\d{5}\.\d{6}/\d{4}-\d{2}\b")
RE_PRAZO_DATA = re.compile(
    r"(?:prazo|ate|limite)[^0-9]{0,30}(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})"
)
RE_PRAZO_DIAS = re.compile(r"(?:prazo\s*(?:de|:)?\s*)?(\d{1,3})\s*dias?")

# Palavra-chave normalizada -> nome canônico do ente.
ENTES: tuple[tuple[str, str], ...] = (
    ("barra de santo antonio", "Barra de Santo Antonio_AL"),
    ("cajueiro", "Cajueiro_AL"),
    ("coqueiro seco", "Coqueiro Seco_AL"),
    ("sao sebastiao", "São Sebastião_AL"),
    ("agua branca", "Agua Branca_PB"),
    ("arara", "Arara_PB"),
    ("bom jesus", "Bom Jesus_PB"),
    ("sao jose da lagoa tapada", "São José da Lagoa Tapada_PB"),
    ("sape", "Sape_PB"),
)


def normalizar(texto: str) -> str:
    """Remove acentos (NFKD) e coloca em minúsculas."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.lower()


def limpar_assunto(assunto: str) -> str:
    """Remove prefixos de resposta/encaminhamento e espaços redundantes."""
    s = " ".join(assunto.split())
    alterou = True
    while alterou and s:
        alterou = False
        lower = s.lower()
        for prefixo in PREFIXOS_ASSUNTO:
            if lower.startswith(prefixo):
                s = s[len(prefixo):].strip()
                alterou = True
                break
    return s or "(sem assunto)"


def extrair_sei(texto: str) -> str:
    m = RE_SEI.search(texto)
    return m.group(0) if m else ""


def e_controle(texto: str) -> bool:
    t = normalizar(texto)
    return "ministerio publico" in t or "tribunal de contas" in t


def inferir_tipo(texto: str) -> str:
    t = normalizar(texto)
    if "relatorio" in t:
        return "Relatório"
    if "oficio" in t or "despacho" in t or "expediente" in t:
        return "Despacho"
    if "reuniao" in t:
        return "Reunião"
    return "Expediente"


def inferir_ente(texto: str) -> str:
    t = normalizar(texto)
    for chave, nome in ENTES:
        if chave in t:
            return nome
    return ""


def _data_valida(dia_str: str, mes_str: str, ano_str: str) -> date | None:
    try:
        ano = int(ano_str)
        mes = int(mes_str)
        dia = int(dia_str)
    except ValueError:
        return None
    if ano < 100:
        ano += 2000
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def adicionar_dias_uteis(inicio: date, n: int) -> date:
    """Soma `n` dias úteis (seg-sex), ignorando fins de semana."""
    atual = inicio
    contados = 0
    while contados < n:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            contados += 1
    return atual


def _menciona_uteis(texto_normalizado: str, inicio: int, tamanho: int) -> bool:
    if inicio >= len(texto_normalizado):
        return False
    janela = texto_normalizado[inicio:inicio + tamanho]
    return "uteis" in janela or "util" in janela


def extrair_prazo(texto: str, recebido: date) -> tuple[date | None, bool]:
    """Extrai o prazo externo; devolve (data, usou_dias_uteis)."""
    t = normalizar(texto)

    m = RE_PRAZO_DATA.search(t)
    if m:
        data = _data_valida(m.group(1), m.group(2), m.group(3))
        if data is not None:
            uteis = _menciona_uteis(
                t, m.start(), (m.end() - m.start()) + JANELA_DIAS_UTEIS
            )
            return data, uteis

    m = RE_PRAZO_DIAS.search(t)
    if m:
        try:
            n = int(m.group(1))
        except ValueError:
            n = None
        if n is not None:
            uteis = _menciona_uteis(
                t, m.start(), (m.end() - m.start()) + JANELA_DIAS_UTEIS
            )
            if uteis:
                return adicionar_dias_uteis(recebido, n), True
            return recebido + timedelta(days=n), False

    return None, False


def calcular_prazo_interno(prazo: date, recebido: date, controle: bool) -> date:
    """Calcula o prazo interno, nunca antes da data de recebimento."""
    dias_total = (prazo - recebido).days
    if controle:
        d = prazo - timedelta(days=DIAS_INTERNOS_CONTROLE)
    elif dias_total <= DIAS_CURTO_PRAZO:
        d = prazo - timedelta(days=1)
    else:
        d = prazo - timedelta(days=DIAS_INTERNOS_PADRAO)

    while d.weekday() >= 5:
        d -= timedelta(days=1)

    return max(d, recebido)


def inferir_prioridade(controle: bool, prazo: date | None, recebido: date) -> str:
    if controle:
        return "Alta"
    if prazo is not None and (prazo - recebido).days <= DIAS_PRIORIDADE_ALTA:
        return "Alta"
    return "Média"


def classificar(
    assunto: str, corpo: str, remetente_nome: str, recebido: date
) -> Classificacao:
    """Classifica um e-mail, sugerindo todos os campos da demanda."""
    texto_assunto_corpo = f"{assunto} {corpo}"
    controle = e_controle(f"{texto_assunto_corpo} {remetente_nome}")
    prazo, uteis = extrair_prazo(texto_assunto_corpo, recebido)
    prazo_interno = (
        calcular_prazo_interno(prazo, recebido, controle) if prazo is not None else None
    )

    return Classificacao(
        titulo=limpar_assunto(assunto),
        ente=inferir_ente(texto_assunto_corpo),
        tipo=inferir_tipo(texto_assunto_corpo),
        prioridade=inferir_prioridade(controle, prazo, recebido),
        processo_sei=extrair_sei(f"{corpo} {assunto}"),
        prazo=prazo.isoformat() if prazo else None,
        prazo_interno=prazo_interno.isoformat() if prazo_interno else None,
        dias_uteis=uteis,
    )


def parse_data_ou_datetime(texto: str) -> date | None:
    """Aceita `YYYY-MM-DDTHH:MM:SS` ou `YYYY-MM-DD`."""
    if not texto:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto.strip(), fmt).date()
        except ValueError:
            continue
    return None
