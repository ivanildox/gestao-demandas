"""Regras de negócio: CRUD, auditoria de histórico e manipulação de anexos.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
from .config import DIAS_ALERTA_PRAZO, STATUS_FINAIS, TIPOS_ANDAMENTO
from .models import (
    Anexo,
    Andamento,
    ContagemItem,
    Demanda,
    Estatisticas,
    FiltroDemandas,
    FormDemanda,
    Historico,
)

# Campos comparados na auditoria de alteração (nome exibido, atributo antigo,
# valor novo). A ordem define a ordem das mensagens no histórico.
_CAMPOS_AUDITORIA: tuple[str, ...] = (
    "titulo",
    "descricao",
    "entregavel",
    "ente",
    "tipo",
    "prioridade",
    "tipo_atendimento",
    "status",
    "responsavel",
    "processo_sei",
    "remetente",
    "remetente_email",
    "email_corpo",
    "recebido_em",
    "prazo",
    "prazo_interno",
)


def agora_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def hoje_date() -> date:
    return datetime.now().date()


def formatar_data_br(iso: str | None) -> str:
    """Converte `YYYY-MM-DD` em `DD/MM/YYYY`; devolve o original se falhar."""
    if not iso:
        return ""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def situacao_prazo(status: str, prazo: str | None, hoje: date) -> str:
    """Devolve `atrasada`, `vencendo` (até 7 dias) ou string vazia."""
    if status in STATUS_FINAIS:
        return ""
    if prazo is None or not str(prazo).strip():
        return ""
    try:
        p = datetime.strptime(str(prazo), "%Y-%m-%d").date()
    except ValueError:
        return ""
    if p < hoje:
        return "atrasada"
    if p <= hoje + timedelta(days=DIAS_ALERTA_PRAZO):
        return "vencendo"
    return ""


def registrar_historico(conn: sqlite3.Connection, demanda_id: int, acao: str) -> None:
    conn.execute(
        "INSERT INTO historico (demanda_id, momento, acao) VALUES (?, ?, ?)",
        (demanda_id, agora_iso(), acao),
    )
    conn.commit()


def criar_demanda(
    conn: sqlite3.Connection,
    form: FormDemanda,
    origem: str,
    email_id: str | None = None,
) -> int:
    """Cria a demanda e registra o evento inicial. Levanta ValueError se o
    título estiver vazio."""
    titulo = form.titulo.strip()
    if not titulo:
        raise ValueError("Informe o título da demanda.")

    momento = agora_iso()
    concluido_em = (
        hoje_date().isoformat() if form.status.strip() in STATUS_FINAIS else None
    )

    cursor = conn.execute(
        """INSERT INTO demandas (
            titulo, descricao, entregavel, ente, tipo, prioridade, status,
            tipo_atendimento, responsavel, processo_sei, remetente, remetente_email, origem,
            email_id, email_corpo, recebido_em, prazo, prazo_interno,
            concluido_em, criado_em, atualizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            titulo,
            form.descricao.strip(),
            form.entregavel.strip(),
            form.ente.strip(),
            form.tipo.strip(),
            form.prioridade.strip(),
            form.status.strip(),
            form.tipo_atendimento.strip(),
            form.responsavel.strip(),
            form.processo_sei.strip(),
            form.remetente.strip(),
            form.remetente_email.strip(),
            origem,
            email_id,
            form.email_corpo.strip(),
            form.recebido_em,
            form.prazo,
            form.prazo_interno,
            concluido_em,
            momento,
            momento,
        ),
    )
    conn.commit()

    demanda_id = cursor.lastrowid
    origem_txt = "e-mail" if origem == "email" else "cadastro manual"
    registrar_historico(conn, demanda_id, f"Demanda criada ({origem_txt})")
    return demanda_id


def _mapear_demanda(linha: sqlite3.Row) -> Demanda:
    d = Demanda.de_linha(linha)
    d.situacao_prazo = situacao_prazo(d.status, d.prazo, hoje_date())
    return d


def obter_demanda(conn: sqlite3.Connection, demanda_id: int) -> Demanda | None:
    linha = conn.execute("SELECT * FROM demandas WHERE id = ?", (demanda_id,)).fetchone()
    return _mapear_demanda(linha) if linha else None


def _checar_campo(nome: str, antigo: str, novo: str, mudancas: list[str]) -> None:
    if antigo != novo:
        mudancas.append(
            f"{nome}: {antigo or '-'} -> {novo or '-'}"
        )


def atualizar_demanda(
    conn: sqlite3.Connection, demanda_id: int, form: FormDemanda
) -> None:
    """Atualiza a demanda e registra no histórico apenas o que mudou."""
    atual = obter_demanda(conn, demanda_id)
    if atual is None:
        raise ValueError(f"Demanda #{demanda_id} não encontrada.")

    titulo = form.titulo.strip()
    if not titulo:
        raise ValueError("Informe o título da demanda.")

    # Valores novos, já normalizados (mesma ordem de _CAMPOS_AUDITORIA).
    novos = {
        "titulo": titulo,
        "descricao": form.descricao.strip(),
        "entregavel": form.entregavel.strip(),
        "ente": form.ente.strip(),
        "tipo": form.tipo.strip(),
        "prioridade": form.prioridade.strip(),
        "tipo_atendimento": form.tipo_atendimento.strip(),
        "status": form.status.strip(),
        "responsavel": form.responsavel.strip(),
        "processo_sei": form.processo_sei.strip(),
        "remetente": form.remetente.strip(),
        "remetente_email": form.remetente_email.strip(),
        "email_corpo": form.email_corpo.strip(),
        "recebido_em": form.recebido_em or "",
        "prazo": form.prazo or "",
        "prazo_interno": form.prazo_interno or "",
    }

    mudancas: list[str] = []
    for campo in _CAMPOS_AUDITORIA:
        antigo = getattr(atual, campo) or ""
        _checar_campo(campo, str(antigo), novos[campo], mudancas)

    if not mudancas:
        return

    if novos["status"] != atual.status:
        concluido_em = (
            hoje_date().isoformat() if novos["status"] in STATUS_FINAIS else None
        )
    else:
        concluido_em = atual.concluido_em

    momento = agora_iso()
    conn.execute(
        """UPDATE demandas SET
            titulo = ?, descricao = ?, entregavel = ?, ente = ?, tipo = ?,
            prioridade = ?, tipo_atendimento = ?, status = ?, responsavel = ?, processo_sei = ?,
            remetente = ?, remetente_email = ?, email_corpo = ?,
            recebido_em = ?, prazo = ?, prazo_interno = ?, concluido_em = ?,
            atualizado_em = ?
        WHERE id = ?""",
        (
            titulo,
            novos["descricao"],
            novos["entregavel"],
            novos["ente"],
            novos["tipo"],
            novos["prioridade"],
            novos["tipo_atendimento"],
            novos["status"],
            novos["responsavel"],
            novos["processo_sei"],
            novos["remetente"],
            novos["remetente_email"],
            novos["email_corpo"],
            form.recebido_em,
            form.prazo,
            form.prazo_interno,
            concluido_em,
            momento,
            demanda_id,
        ),
    )
    conn.commit()

    registrar_historico(conn, demanda_id, f"Alterado: {'; '.join(mudancas)}")


def excluir_demanda(conn: sqlite3.Connection, demanda_id: int) -> bool:
    """Exclui a demanda e a pasta de anexos. False se não existir."""
    existe = conn.execute(
        "SELECT id FROM demandas WHERE id = ?", (demanda_id,)
    ).fetchone()
    if existe is None:
        return False

    pasta_anexos = config.get_anexos_dir() / str(demanda_id)
    conn.execute("DELETE FROM demandas WHERE id = ?", (demanda_id,))
    conn.commit()

    if pasta_anexos.is_dir():
        shutil.rmtree(pasta_anexos, ignore_errors=True)

    return True


def listar_demandas(
    conn: sqlite3.Connection, filtro: FiltroDemandas
) -> list[Demanda]:
    """Lista demandas aplicando os filtros da tela principal."""
    sql = "SELECT * FROM demandas WHERE 1 = 1"
    params: list = []

    if filtro.status and filtro.status.strip() and filtro.status != "Todas":
        sql += " AND status = ?"
        params.append(filtro.status)

    if filtro.somente_abertas:
        sql += " AND status NOT IN ('Concluída', 'Cancelada')"

    if filtro.busca and filtro.busca.strip():
        sql += (
            " AND (titulo LIKE ? OR ente LIKE ? OR processo_sei LIKE ?"
            " OR remetente LIKE ? OR responsavel LIKE ?)"
        )
        like_str = f"%{filtro.busca.strip()}%"
        params.extend([like_str] * 5)

    if filtro.recebido_de and filtro.recebido_de.strip():
        sql += " AND recebido_em >= ?"
        params.append(filtro.recebido_de)

    if filtro.recebido_ate and filtro.recebido_ate.strip():
        sql += " AND recebido_em <= ?"
        params.append(filtro.recebido_ate)

    sql += " ORDER BY criado_em, id"

    linhas = conn.execute(sql, params).fetchall()
    return [_mapear_demanda(linha) for linha in linhas]


def historico(conn: sqlite3.Connection, demanda_id: int) -> list[Historico]:
    linhas = conn.execute(
        "SELECT * FROM historico WHERE demanda_id = ? ORDER BY id DESC",
        (demanda_id,),
    ).fetchall()
    return [
        Historico(
            id=linha["id"],
            demanda_id=linha["demanda_id"],
            momento=linha["momento"],
            acao=linha["acao"],
        )
        for linha in linhas
    ]


def excluir_andamento(conn: sqlite3.Connection, andamento_id: int) -> bool:
    """Exclui um registro de andamento pelo id. Retorna False se não existir."""
    existe = conn.execute(
        "SELECT id FROM andamentos WHERE id = ?", (andamento_id,)
    ).fetchone()
    if existe is None:
        return False
    conn.execute("DELETE FROM andamentos WHERE id = ?", (andamento_id,))
    conn.commit()
    return True


def atualizar_status_demanda(
    conn: sqlite3.Connection, demanda_id: int, novo_status: str
) -> None:
    """Atualiza apenas o status da demanda e registra no histórico."""
    atual = obter_demanda(conn, demanda_id)
    if atual is None:
        raise ValueError(f"Demanda #{demanda_id} não encontrada.")
    if atual.status == novo_status:
        return
    concluido_em = (
        hoje_date().isoformat() if novo_status in STATUS_FINAIS else None
    )
    conn.execute(
        "UPDATE demandas SET status = ?, concluido_em = ?, atualizado_em = ? WHERE id = ?",
        (novo_status, concluido_em, agora_iso(), demanda_id),
    )
    conn.commit()
    registrar_historico(
        conn, demanda_id, f"Status alterado: {atual.status} -> {novo_status}"
    )


def listar_andamentos(conn: sqlite3.Connection, demanda_id: int) -> list[Andamento]:
    linhas = conn.execute(
        "SELECT * FROM andamentos "
        "WHERE demanda_id = ? ORDER BY date(momento) ASC, id ASC",
        (demanda_id,),
    ).fetchall()
    return [
        Andamento(
            id=linha["id"],
            demanda_id=linha["demanda_id"],
            momento=linha["momento"],
            tipo=linha["tipo"],
            destinatario=linha["destinatario"],
            descricao=linha["descricao"],
        )
        for linha in linhas
    ]


def registrar_movimento(
    conn: sqlite3.Connection,
    demanda_id: int,
    data_movimento: str,
    destino: str,
    observacao: str = "",
) -> int:
    """Registra uma movimentação com data informada pelo usuário."""
    try:
        data_normalizada = datetime.strptime(data_movimento, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Informe uma data de movimentação válida.") from exc

    destino_normalizado = destino.strip()
    if not destino_normalizado:
        raise ValueError("Informe o destino da movimentação.")
    if obter_demanda(conn, demanda_id) is None:
        raise ValueError(f"Demanda #{demanda_id} não encontrada.")

    cursor = conn.execute(
        """INSERT INTO andamentos (
            demanda_id, momento, tipo, destinatario, descricao
        ) VALUES (?, ?, ?, ?, ?)""",
        (
            demanda_id,
            data_normalizada.isoformat(),
            "Encaminhamento",
            destino_normalizado,
            observacao.strip(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def registrar_andamento(
    conn: sqlite3.Connection,
    demanda_id: int,
    tipo: str,
    descricao: str,
    destinatario: str = "",
) -> int:
    """Registra encaminhamento, resposta ou nota na linha do tempo."""
    tipo_normalizado = tipo.strip()
    descricao_normalizada = descricao.strip()
    if tipo_normalizado not in TIPOS_ANDAMENTO:
        raise ValueError("Selecione um tipo de andamento válido.")
    if not descricao_normalizada:
        raise ValueError("Descreva o andamento antes de registrar.")
    if obter_demanda(conn, demanda_id) is None:
        raise ValueError(f"Demanda #{demanda_id} não encontrada.")

    cursor = conn.execute(
        """INSERT INTO andamentos (
            demanda_id, momento, tipo, destinatario, descricao
        ) VALUES (?, ?, ?, ?, ?)""",
        (
            demanda_id,
            agora_iso(),
            tipo_normalizado,
            destinatario.strip(),
            descricao_normalizada,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def anexos(conn: sqlite3.Connection, demanda_id: int) -> list[Anexo]:
    linhas = conn.execute(
        "SELECT * FROM anexos WHERE demanda_id = ? ORDER BY id", (demanda_id,)
    ).fetchall()
    return [
        Anexo(
            id=linha["id"],
            demanda_id=linha["demanda_id"],
            nome=linha["nome"],
            caminho=linha["caminho"],
            tamanho=linha["tamanho"],
            adicionado_em=linha["adicionado_em"],
        )
        for linha in linhas
    ]


def _destino_unico(pasta: Path, nome_original: str) -> Path:
    """Evita sobrescrever: acrescenta " (2)", " (3)"... quando necessário."""
    destino = pasta / nome_original
    if not destino.exists():
        return destino

    caminho = Path(nome_original)
    stem = caminho.stem or "arquivo"
    ext = caminho.suffix

    i = 2
    while True:
        destino = pasta / f"{stem} ({i}){ext}"
        if not destino.exists():
            return destino
        i += 1


def adicionar_anexo(
    conn: sqlite3.Connection, demanda_id: int, origem: str | Path
) -> int:
    """Copia o arquivo para `dados/anexos/<id>/` e registra no banco."""
    origem = Path(origem)
    if not origem.exists():
        raise ValueError(f"Arquivo de origem não encontrado: {origem}")

    nome_arquivo = origem.name
    if not nome_arquivo:
        raise ValueError("Nome de arquivo inválido")

    pasta = config.get_anexos_dir() / str(demanda_id)
    pasta.mkdir(parents=True, exist_ok=True)

    destino = _destino_unico(pasta, nome_arquivo)
    shutil.copy2(origem, destino)

    tamanho = destino.stat().st_size if destino.exists() else 0
    dados_dir = config.get_dados_dir()
    try:
        caminho_relativo = destino.relative_to(dados_dir).as_posix()
    except ValueError:
        caminho_relativo = destino.as_posix()

    nome_final = destino.name
    cursor = conn.execute(
        "INSERT INTO anexos (demanda_id, nome, caminho, tamanho, adicionado_em)"
        " VALUES (?, ?, ?, ?, ?)",
        (demanda_id, nome_final, caminho_relativo, tamanho, agora_iso()),
    )
    conn.commit()

    registrar_historico(conn, demanda_id, f"Anexo adicionado: {nome_final}")
    return cursor.lastrowid


def resolver_caminho_anexo(caminho: str) -> Path:
    """Resolve o caminho do anexo, que pode ser relativo a `dados/`."""
    normalizado = caminho.replace("\\", "/")
    if normalizado.startswith("anexos/"):
        return config.get_dados_dir() / normalizado
    return Path(caminho)


def obter_estatisticas(conn: sqlite3.Connection) -> Estatisticas:
    todas = listar_demandas(conn, FiltroDemandas())
    hoje = hoje_date()

    abertas = atrasadas = vencendo = 0
    por_status: Counter[str] = Counter()
    por_ente: Counter[str] = Counter()
    por_tipo: Counter[str] = Counter()

    for d in todas:
        sit = situacao_prazo(d.status, d.prazo, hoje)
        if sit == "atrasada":
            atrasadas += 1
        elif sit == "vencendo":
            vencendo += 1

        if d.status not in STATUS_FINAIS:
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
        total=len(todas),
        abertas=abertas,
        atrasadas=atrasadas,
        vencendo=vencendo,
        por_status=ordenar(por_status),
        por_ente=ordenar(por_ente),
        por_tipo=ordenar(por_tipo),
    )


def abrir_arquivo(caminho: str | Path) -> None:
    """Abre o arquivo com o aplicativo padrão do sistema."""
    import os
    import subprocess
    import sys

    caminho = str(caminho)
    if sys.platform.startswith("win"):
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", caminho], check=False)
    else:
        subprocess.run(["xdg-open", caminho], check=False)
