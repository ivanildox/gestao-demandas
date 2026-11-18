"""Geração de relatório HTML e exportação CSV.

O CSV sai em UTF-8 com BOM e separador `;`, formato que o Excel em
português abre diretamente com os acentos corretos.
"""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from . import config, servicos
from .models import Andamento, ContagemItem, Estatisticas, FiltroDemandas

COLUNAS: tuple[str, ...] = (
    "ID",
    "Título",
    "Ente",
    "Tipo",
    "Prioridade",
    "Ação necessária",
    "Status",
    "Responsável",
    "Processo SEI",
    "Recebido em",
    "Prazo",
    "Prazo interno",
    "Concluído em",
    "Situação",
)

_ESTILO = """
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 24px; color: #222; background: #fff; }
table { border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 13px; }
th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; font-weight: 600; }
tr.atrasada { background: #f8d7da; }
tr.vencendo { background: #fff3cd; }
.cards { display: flex; gap: 20px; margin-bottom: 20px; }
.card { background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 18px; }
.card b { font-size: 22px; display: block; color: #1e293b; }
.card span { font-size: 13px; color: #64748b; }
h1 { color: #0f172a; margin-bottom: 6px; }
h2 { color: #334155; margin-top: 24px; font-size: 16px; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; }
"""


def html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _rotulo_situacao(situacao: str) -> str:
    if situacao == "atrasada":
        return "Atrasada"
    if situacao == "vencendo":
        return "Vence em breve"
    return ""


def _render_tabela_resumo(titulo: str, contagem: list[ContagemItem]) -> str:
    partes = [
        f"<h2>{html_escape(titulo)}</h2>\n",
        "<table>\n<tr><th>Item</th><th>Quantidade</th></tr>\n",
    ]
    for item in contagem:
        partes.append(
            f"<tr><td>{html_escape(item.item)}</td><td>{item.quantidade}</td></tr>\n"
        )
    partes.append("</table>\n")
    return "".join(partes)


def exportar_csv(conn: sqlite3.Connection) -> Path:
    """Exporta todas as demandas para CSV (UTF-8-BOM, separador `;`)."""
    demandas = servicos.listar_demandas(conn, FiltroDemandas())

    nome_arquivo = f"demandas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    caminho = config.get_relatorios_dir() / nome_arquivo

    # `utf-8-sig` escreve o BOM que o Excel precisa para reconhecer acentos.
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.writer(arquivo, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(COLUNAS)

        for d in demandas:
            writer.writerow(
                [
                    d.id or 0,
                    d.titulo,
                    d.ente,
                    d.tipo,
                    d.prioridade,
                    d.tipo_atendimento,
                    d.status,
                    d.responsavel,
                    d.processo_sei,
                    servicos.formatar_data_br(d.recebido_em),
                    servicos.formatar_data_br(d.prazo),
                    servicos.formatar_data_br(d.prazo_interno),
                    servicos.formatar_data_br(d.concluido_em),
                    _rotulo_situacao(d.situacao_prazo),
                ]
            )

    return caminho


def _montar_relatorio_html(
    demandas: list,
    est: Estatisticas,
    filtro_desc: str,
    agora: datetime,
) -> str:
    """Monta o HTML do relatório a partir de demandas e estatísticas."""
    h: list[str] = []
    h.append('<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n')
    h.append("<title>Relatório de demandas</title>\n<style>\n")
    h.append(_ESTILO)
    h.append("</style>\n</head>\n<body>\n")

    h.append("<h1>Relatório de Demandas</h1>\n")
    h.append(
        f"<p>Gerado em {agora.strftime('%d/%m/%Y %H:%M')}. "
        f"Filtro: {html_escape(filtro_desc)}.</p>\n"
    )

    h.append('<div class="cards">\n')
    for rotulo, valor in (
        ("Total", est.total),
        ("Abertas", est.abertas),
        ("Atrasadas", est.atrasadas),
        ("Vencendo em 7 dias", est.vencendo),
    ):
        h.append(
            f'<div class="card"><span>{rotulo}</span><b>{valor}</b></div>\n'
        )
    h.append("</div>\n")

    h.append(_render_tabela_resumo("Por Status", est.por_status))
    h.append(_render_tabela_resumo("Por Ente", est.por_ente))
    h.append(_render_tabela_resumo("Por Tipo", est.por_tipo))

    h.append("<h2>Demandas</h2>\n<table>\n<tr>\n")
    for coluna in COLUNAS:
        h.append(f"<th>{html_escape(coluna)}</th>")
    h.append("</tr>\n")

    for d in demandas:
        h.append(f'<tr class="{d.situacao_prazo}">')
        h.append(f"<td>{d.id or 0}</td>")
        h.append(f"<td>{html_escape(d.titulo)}</td>")
        h.append(f"<td>{html_escape(d.ente)}</td>")
        h.append(f"<td>{html_escape(d.tipo)}</td>")
        h.append(f"<td>{html_escape(d.prioridade)}</td>")
        h.append(f"<td>{html_escape(d.tipo_atendimento)}</td>")
        h.append(f"<td>{html_escape(d.status)}</td>")
        h.append(f"<td>{html_escape(d.responsavel)}</td>")
        h.append(f"<td>{html_escape(d.processo_sei)}</td>")
        h.append(f"<td>{servicos.formatar_data_br(d.recebido_em)}</td>")
        h.append(f"<td>{servicos.formatar_data_br(d.prazo)}</td>")
        h.append(f"<td>{servicos.formatar_data_br(d.prazo_interno)}</td>")
        h.append(f"<td>{servicos.formatar_data_br(d.concluido_em)}</td>")
        h.append(f"<td>{_rotulo_situacao(d.situacao_prazo)}</td>")
        h.append("</tr>\n")

    h.append("</table>\n</body>\n</html>")
    return "".join(h)


def _estatisticas_de(demandas: list) -> Estatisticas:
    """Calcula estatísticas a partir de uma lista de demandas já filtradas."""
    abertas = atrasadas = vencendo = 0
    por_status: Counter[str] = Counter()
    por_ente: Counter[str] = Counter()
    por_tipo: Counter[str] = Counter()

    for d in demandas:
        sit = d.situacao_prazo
        if sit == "atrasada":
            atrasadas += 1
        elif sit == "vencendo":
            vencendo += 1

        if d.status not in servicos.STATUS_FINAIS:
            abertas += 1

        por_status[d.status] += 1
        por_ente[d.ente.strip() or "(sem ente)"] += 1
        por_tipo[d.tipo] += 1

    def ordenar(contador: Counter[str]) -> list[ContagemItem]:
        return [
            ContagemItem(item=item, quantidade=qtd)
            for item, qtd in contador.most_common()
        ]

    return Estatisticas(
        total=len(demandas),
        abertas=abertas,
        atrasadas=atrasadas,
        vencendo=vencendo,
        por_status=ordenar(por_status),
        por_ente=ordenar(por_ente),
        por_tipo=ordenar(por_tipo),
    )


def gerar_html(conn: sqlite3.Connection, filtro_desc: str = "Todas") -> Path:
    """Gera o relatório HTML responsivo em `dados/relatorios/`."""
    est = servicos.obter_estatisticas(conn)
    demandas = servicos.listar_demandas(conn, FiltroDemandas())

    agora = datetime.now()
    caminho = config.get_relatorios_dir() / f"relatorio_{agora.strftime('%Y%m%d_%H%M%S')}.html"

    conteudo = _montar_relatorio_html(demandas, est, filtro_desc, agora)
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def gerar_html_ente(conn: sqlite3.Connection, ente: str) -> Path:
    """Gera relatório HTML apenas para as demandas do ente informado."""
    todas = servicos.listar_demandas(conn, FiltroDemandas())
    demandas = [d for d in todas if (d.ente or "").strip().lower() == ente.strip().lower()]

    est = _estatisticas_de(demandas)

    agora = datetime.now()
    caminho = config.get_relatorios_dir() / f"relatorio_{agora.strftime('%Y%m%d_%H%M%S')}.html"

    conteudo = _montar_relatorio_html(
        demandas, est, f"Ente: {ente}", agora
    )
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def exportar_historico_html(
    demanda_id: int,
    titulo: str,
    andamentos: list[Andamento],
) -> Path:
    """Exporta o histórico de movimentações de uma demanda para HTML."""
    agora = datetime.now()
    caminho = config.get_relatorios_dir() / (
        f"historico_demanda_{demanda_id}_{agora.strftime('%Y%m%d_%H%M%S')}.html"
    )
    partes = [
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n',
        "<title>Histórico de movimentações</title>\n",
        "<style>\n",
        "body { font-family: 'Segoe UI', Arial, sans-serif; margin: 24px; "
        "color: #0f172a; }\n",
        "table { border-collapse: collapse; width: 100%; }\n",
        "th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; "
        "vertical-align: top; white-space: pre-wrap; }\n",
        "th { background: #f1f5f9; }\n",
        "</style>\n</head>\n<body>\n",
        f"<h1>Histórico de movimentações — Demanda #{demanda_id}</h1>\n",
        f"<p>{html_escape(titulo)}</p>\n",
        "<table>\n<thead><tr><th>Data do Movimento</th><th>Destino</th>"
        "<th>Observação</th></tr></thead>\n<tbody>\n",
    ]

    for andamento in andamentos:
        data_movimento = (
            servicos.formatar_data_br(andamento.momento)
            if len(andamento.momento) == 10
            else andamento.momento
        )
        partes.append(
            "<tr>"
            f"<td>{html_escape(data_movimento)}</td>"
            f"<td>{html_escape(andamento.destinatario)}</td>"
            f"<td>{html_escape(andamento.descricao)}</td>"
            "</tr>\n"
        )
    if not andamentos:
        partes.append(
            '<tr><td colspan="3">Nenhuma movimentação registrada.</td></tr>\n'
        )

    partes.append("</tbody>\n</table>\n</body>\n</html>")
    caminho.write_text("".join(partes), encoding="utf-8")
    return caminho
