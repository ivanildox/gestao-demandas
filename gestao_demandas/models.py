"""Modelos de dados fortemente tipados.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Demanda:
    id: int | None = None
    titulo: str = ""
    descricao: str = ""
    entregavel: str = ""
    ente: str = ""
    tipo: str = "Expediente"
    prioridade: str = "Média"
    tipo_atendimento: str = "Encaminhar"
    status: str = "Novo"
    responsavel: str = ""
    processo_sei: str = ""
    remetente: str = ""
    remetente_email: str = ""
    origem: str = "manual"
    email_id: str | None = None
    email_corpo: str = ""
    recebido_em: str | None = None
    prazo: str | None = None
    prazo_interno: str | None = None
    concluido_em: str | None = None
    criado_em: str = ""
    atualizado_em: str = ""
    # "atrasada", "vencendo" ou ""
    situacao_prazo: str = ""

    @classmethod
    def de_linha(cls, linha) -> "Demanda":
        """Constrói a demanda a partir de uma linha do SQLite."""
        return cls(
            id=linha["id"],
            titulo=linha["titulo"],
            descricao=linha["descricao"],
            entregavel=linha["entregavel"],
            ente=linha["ente"],
            tipo=linha["tipo"],
            prioridade=linha["prioridade"],
            tipo_atendimento=linha["tipo_atendimento"],
            status=linha["status"],
            responsavel=linha["responsavel"],
            processo_sei=linha["processo_sei"],
            remetente=linha["remetente"],
            remetente_email=linha["remetente_email"],
            origem=linha["origem"],
            email_id=linha["email_id"],
            email_corpo=linha["email_corpo"] or "",
            recebido_em=linha["recebido_em"],
            prazo=linha["prazo"],
            prazo_interno=linha["prazo_interno"],
            concluido_em=linha["concluido_em"],
            criado_em=linha["criado_em"],
            atualizado_em=linha["atualizado_em"],
        )


@dataclass
class FormDemanda:
    titulo: str = ""
    descricao: str = ""
    entregavel: str = ""
    ente: str = ""
    tipo: str = "Expediente"
    prioridade: str = "Média"
    tipo_atendimento: str = "Encaminhar"
    status: str = "Novo"
    responsavel: str = ""
    processo_sei: str = ""
    remetente: str = ""
    remetente_email: str = ""
    email_corpo: str = ""
    recebido_em: str | None = None
    prazo: str | None = None
    prazo_interno: str | None = None


@dataclass
class Historico:
    id: int | None = None
    demanda_id: int = 0
    momento: str = ""
    acao: str = ""


@dataclass
class Andamento:
    id: int | None = None
    demanda_id: int = 0
    momento: str = ""
    tipo: str = ""
    destinatario: str = ""
    descricao: str = ""


@dataclass
class Anexo:
    id: int | None = None
    demanda_id: int = 0
    nome: str = ""
    caminho: str = ""
    tamanho: int = 0
    adicionado_em: str = ""


@dataclass
class Classificacao:
    titulo: str = ""
    ente: str = ""
    tipo: str = "Expediente"
    prioridade: str = "Média"
    processo_sei: str = ""
    prazo: str | None = None
    prazo_interno: str | None = None
    dias_uteis: bool = False


@dataclass
class FiltroDemandas:
    status: str | None = None
    busca: str | None = None
    somente_abertas: bool | None = None
    recebido_de: str | None = None
    recebido_ate: str | None = None


@dataclass
class ContagemItem:
    item: str
    quantidade: int


@dataclass
class Estatisticas:
    total: int = 0
    abertas: int = 0
    atrasadas: int = 0
    vencendo: int = 0
    por_status: list[ContagemItem] = field(default_factory=list)
    por_ente: list[ContagemItem] = field(default_factory=list)
    por_tipo: list[ContagemItem] = field(default_factory=list)


@dataclass
class AnexoPacoteEmail:
    nome: str = ""
    caminho: str = ""


@dataclass
class PacoteEmail:
    entry_id: str = ""
    assunto: str = ""
    remetente_nome: str = ""
    remetente_email: str = ""
    recebido: str = ""
    corpo: str = ""
    pasta_anexos: str = ""
    anexos: list[AnexoPacoteEmail] = field(default_factory=list)


@dataclass
class OpcoesFormulario:
    tipos: list[str] = field(default_factory=list)
    prioridades: list[str] = field(default_factory=list)
    tipos_atendimento: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
