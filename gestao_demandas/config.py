"""Resolução de caminhos, diretórios e constantes do domínio.
"""

from __future__ import annotations

import os
from pathlib import Path

STATUS_FINAIS: tuple[str, ...] = ("Concluída", "Cancelada")
STATUS: tuple[str, ...] = (
    "Novo",
    "Em triagem",
    "Aguardando informações",
    "Encaminhada",
    "Em atendimento",
    "Aguardando resposta",
    "Em andamento",
    "Aguardando terceiros",
    "Concluída",
    "Cancelada",
)
TIPOS_ATENDIMENTO: tuple[str, ...] = (
    "Encaminhar",
    "Responder",
    "Encaminhar e responder",
)
TIPOS_ANDAMENTO: tuple[str, ...] = (
    "Nota interna",
    "Encaminhamento",
    "Resposta ao solicitante",
    "Solicitação de informação",
    "Retorno recebido",
)
TIPOS: tuple[str, ...] = ("Expediente", "Despacho", "Relatório", "Reunião", "Outro")
PRIORIDADES: tuple[str, ...] = ("Alta", "Média", "Baixa")
DIAS_ALERTA_PRAZO: int = 7

# Identidade do aplicativo.
TITULO_APP: str = "Gestão de Demandas"
# Convite de apoio ao projeto, exibido na barra de título da janela principal.
APOIO_PIX: str = "Se gostou, pague-me um café ☕ | PIX 142.007.668-09"
TITULO_JANELA: str = f"{TITULO_APP} - {APOIO_PIX}"

# Raiz do projeto: pasta que contém o pacote `gestao_demandas`.
RAIZ_PROJETO: Path = Path(__file__).resolve().parent.parent

def _arquivo_ultima_pasta() -> Path:
    """Arquivo (por usuário) que permite à macro do Outlook achar os dados."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Gestao de Demandas" / "ultima_pasta.txt"
    return Path.home() / ".gestao_demandas" / "ultima_pasta.txt"


def _lembrar_pasta(pasta: Path) -> None:
    """Registra a pasta em uso para as próximas execuções (e para cópias)."""
    arquivo = _arquivo_ultima_pasta()
    try:
        if arquivo.is_file() and arquivo.read_text(encoding="utf-8").strip() == str(pasta):
            return
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(str(pasta), encoding="utf-8")
    except OSError:
        pass


def _pasta_lembrada() -> Path | None:
    """Pasta de dados registrada por execuções anteriores, se ainda existir."""
    arquivo = _arquivo_ultima_pasta()
    try:
        if not arquivo.is_file():
            return None
        texto = arquivo.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not texto:
        return None
    pasta = Path(texto)
    return pasta if pasta.is_dir() else None


def _pasta_padrao_usuario() -> Path:
    """Pasta alternativa caso a pasta de dados do projeto não possa ser criada."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Gestao de Demandas" / "dados"
    return Path.home() / ".gestao_demandas" / "dados"


def _usar(pasta: Path) -> Path:
    """Garante a existência da pasta e registra o caminho para a macro.

    Se a pasta do projeto não puder ser criada, usa a pasta padrão do usuário.
    """
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError:
        alternativa = _pasta_padrao_usuario()
        alternativa.mkdir(parents=True, exist_ok=True)
        pasta = alternativa
    _lembrar_pasta(pasta)
    return pasta


def get_dados_dir() -> Path:
    """Retorna a pasta de dados do sistema.

    Ordem de busca:
      1. variável de ambiente `GESTAO_DEMANDAS_DADOS`;
      2. `dados/` no diretório de trabalho atual ou na raiz do projeto;
      3. última pasta registrada nesta conta;
      4. `dados/` na raiz do projeto.
    """
    env_dados = os.environ.get("GESTAO_DEMANDAS_DADOS")
    if env_dados:
        return _usar(Path(env_dados).expanduser())

    for pasta in (Path.cwd() / "dados", RAIZ_PROJETO / "dados"):
        if pasta.is_dir():
            return _usar(pasta)

    lembrada = _pasta_lembrada()
    if lembrada is not None:
        return _usar(lembrada)

    return _usar(RAIZ_PROJETO / "dados")


def get_db_path() -> Path:
    return get_dados_dir() / "gestao.db"


def get_anexos_dir() -> Path:
    p = get_dados_dir() / "anexos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_inbox_dir() -> Path:
    p = get_dados_dir() / "inbox"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_processados_dir() -> Path:
    p = get_inbox_dir() / "processados"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_relatorios_dir() -> Path:
    p = get_dados_dir() / "relatorios"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_icone_path() -> Path:
    """Caminho do ícone da aplicação em `icons/`."""
    base = RAIZ_PROJETO / "icons"
    for icone in (base / "icon.ico", base / "128x128.png"):
        if icone.is_file():
            return icone

    return base / "icon.ico"
