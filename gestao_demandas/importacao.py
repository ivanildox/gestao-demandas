"""Importação em lote dos pacotes JSON de `dados/inbox` e arquivamento.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from . import classificacao, config, servicos
from .models import AnexoPacoteEmail, FormDemanda, PacoteEmail


def importar_inbox(conn: sqlite3.Connection) -> list[str]:
    """Processa todos os `.json` da inbox e devolve uma mensagem por arquivo."""
    inbox = config.get_inbox_dir()
    processados = config.get_processados_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    processados.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(
        p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() == ".json"
    )

    resultados: list[str] = []
    for arq in arquivos:
        try:
            resultados.append(_importar_arquivo_email(conn, arq))
        except Exception as exc:  # noqa: BLE001 - devolve o erro na lista
            resultados.append(f"ERRO em {arq.name}: {exc}")
    return resultados


def _ler_conteudo(arquivo: Path) -> str:
    """Lê o arquivo aceitando UTF-8 com ou sem BOM."""
    bruto = arquivo.read_bytes()
    if bruto.startswith(b"\xef\xbb\xbf"):
        bruto = bruto[3:]
    return bruto.decode("utf-8", errors="replace")


def _importar_arquivo_email(conn: sqlite3.Connection, arquivo: Path) -> str:
    nome_arquivo = arquivo.name
    conteudo = _ler_conteudo(arquivo)

    try:
        dados_brutos = json.loads(conteudo)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido: {exc}") from exc

    dados = PacoteEmail(
        entry_id=str(dados_brutos.get("entry_id", "")),
        assunto=dados_brutos.get("assunto", "") or "",
        remetente_nome=dados_brutos.get("remetente_nome", "") or "",
        remetente_email=dados_brutos.get("remetente_email", "") or "",
        recebido=dados_brutos.get("recebido", "") or "",
        corpo=dados_brutos.get("corpo", "") or "",
        pasta_anexos=dados_brutos.get("pasta_anexos", "") or "",
        anexos=[
            AnexoPacoteEmail(
                nome=a.get("nome", "") or "", caminho=a.get("caminho", "") or ""
            )
            for a in (dados_brutos.get("anexos") or [])
        ],
    )

    ja_existe = conn.execute(
        "SELECT id FROM demandas WHERE email_id = ?", (dados.entry_id,)
    ).fetchone()

    if ja_existe is not None:
        _remover_pasta_de_anexos(dados.pasta_anexos)
        _arquivar_json(arquivo)
        return f"Já importado (demanda #{ja_existe['id']}): {nome_arquivo}"

    recebido_date = classificacao.parse_data_ou_datetime(
        dados.recebido
    ) or servicos.hoje_date()

    c = classificacao.classificar(
        dados.assunto, dados.corpo, dados.remetente_nome, recebido_date
    )

    form = FormDemanda(
        titulo=c.titulo,
        descricao=dados.corpo,
        entregavel="",
        ente=c.ente,
        tipo=c.tipo,
        prioridade=c.prioridade,
        status="Novo",
        responsavel="",
        processo_sei=c.processo_sei,
        remetente=dados.remetente_nome,
        remetente_email=dados.remetente_email,
        email_corpo=dados.corpo,
        recebido_em=recebido_date.isoformat(),
        prazo=c.prazo,
        prazo_interno=c.prazo_interno,
    )

    demanda_id = servicos.criar_demanda(conn, form, "email", dados.entry_id)

    for anexo in dados.anexos:
        caminho = Path(anexo.caminho)
        if caminho.exists():
            try:
                servicos.adicionar_anexo(conn, demanda_id, caminho)
            except Exception:  # noqa: BLE001 - anexo opcional não interrompe
                pass

    _remover_pasta_de_anexos(dados.pasta_anexos)
    _arquivar_json(arquivo)

    return f"Importado como demanda #{demanda_id}: {c.titulo}"


def _remover_pasta_de_anexos(pasta_str: str) -> None:
    """Remove a pasta temporária de anexos, apenas se estiver dentro da inbox."""
    if not pasta_str or not pasta_str.strip():
        return

    pasta = Path(pasta_str)
    try:
        caminho = pasta.resolve()
        inbox = config.get_inbox_dir().resolve()
    except OSError:
        return

    # Só remove se for uma subpasta real da inbox (nunca a própria inbox).
    if caminho != inbox and caminho.is_dir() and inbox in caminho.parents:
        shutil.rmtree(caminho, ignore_errors=True)


def _arquivar_json(arquivo: Path) -> None:
    """Move o JSON processado para `inbox/processados`."""
    destino = config.get_processados_dir() / arquivo.name
    if destino.exists():
        destino.unlink(missing_ok=True)
    try:
        arquivo.replace(destino)
    except OSError:
        shutil.copy2(arquivo, destino)
        arquivo.unlink(missing_ok=True)
