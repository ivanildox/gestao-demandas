# Estudo de Viabilidade Técnica: Migração do Sistema de Gestão de Demandas de Python para Rust

## 1. Resumo Executivo

O presente estudo avalia a viabilidade, benefícios, desafios e roadmap técnico para a conversão completa do sistema **Gestão de Demandas** da atual pilha em **Python (3.10+ / SQLite / Tkinter / ttkthemes)** para **Rust**.

### Parecer Técnico: **ALTAMENTE VIÁVEL E RECOMENDADO**
A migração é tecnicamente viável e traz ganhos expressivos na distribuição corporativa (binário executável único `.exe` sem dependência de instalação do Python ou configuração de `.venv`), inicialização instantânea, redução drástica no consumo de memória RAM (de ~120 MB para ~20–35 MB) e eliminação de erros em tempo de execução via sistema de tipos estrito.

A arquitetura do backend (banco SQLite, regras de classificação, importação de e-mails da fila e geração de relatórios) possui mapeamento direto e quase 1:1 com bibliotecas consolidadas do ecossistema Rust. A camada mais crítica é a **Interface Gráfica (GUI)**, para a qual recomenda-se **Tauri v2** ou **Slint**.

A macro VBA do Outlook (`vba/ExportarParaGestao.bas`) **não sofre nenhuma alteração**, mantendo total compatibilidade com o fluxo existente de envio de e-mails para a fila (`dados/inbox`).

---

## 2. Diagnóstico da Aplicação Atual (Python)

A aplicação atual possui cerca de 1.400 linhas de código Python divididas em módulos com responsabilidades bem definidas:

| Módulo Python | Linhas (aprox.) | Responsabilidade Principal |
| :--- | :---: | :--- |
| `app.py` | 5 | Ponto de entrada do sistema. |
| `gestao/config.py` | 20 | Constantes de caminhos, listas de status, prioridades, tipos e prazos. |
| `gestao/banco.py` | 65 | Conexão SQLite, criação de tabelas (`demandas`, `historico`, `anexos`), índices e migrações. |
| `gestao/classificacao.py` | 150 | Normalização de texto NFKD, regex de SEI e datas, contagem de dias úteis e heurísticas de prazo interno/prioridade. |
| `gestao/servicos.py` | 170 | Operações de CRUD, histórico de auditoria com diff de campos, gestão física de anexos e filtros avançados. |
| `gestao/importacao.py` | 75 | Leitura de pacotes JSON gerados pelo Outlook em `dados/inbox`, idempotência por `entry_id` e movimentação de arquivos. |
| `gestao/relatorios.py` | 110 | Agregação estatística, montagem de página HTML responsiva com cards e exportação CSV com UTF-8-BOM. |
| `gestao/interface.py` | 1.078 | Interface gráfica desktop rica (Tkinter/ttkthemes), filtros, tabelas coloridas, modais de edição, histórico, visualização de anexos. |
| `vba/ExportarParaGestao.bas`| 135 | Macro VBA para Outlook clássico que gera JSON e anexos em `dados/inbox`. |

---

## 3. Matriz de Mapeamento Tecnológico (Python → Rust)

O ecossistema Rust possui equivalentes diretos, estáveis e de alto desempenho para cada biblioteca utilizada na versão Python:

| Funcionalidade / Componente | Python Atual | Equivalente em Rust | Observações e Benefícios |
| :--- | :--- | :--- | :--- |
| **Banco de Dados Relacional** | `sqlite3` (std) | `rusqlite` (feature `bundled`) | O motor C do SQLite é compilado estaticamente dentro do binário `.exe`. Zero dependências de DLL externa. |
| **Datas e Prazos** | `datetime.date`, `timedelta` | `chrono` | `NaiveDate` e `Duration` oferecem manipulação segura de datas, cálculo de dias úteis e diferenças temporais. |
| **Expressões Regulares** | `re` (std) | `regex` | Motores de regex compilados em tempo de compilação ou lazy (`std::sync::LazyLock`). Performance superior. |
| **Normalização Unicode** | `unicodedata` (std) | `unicode-normalization` | Decomposição NFKD para remoção precisa de acentos e diacríticos em buscas e classificação. |
| **Serialização JSON** | `json` (std) | `serde` + `serde_json` | Serialização e desserialização de pacotes do inbox com validação estrutural em tempo de compilação. |
| **Exportação CSV** | `csv` (std) | `csv` | Geração rápida de CSV com delimitador `;` e injeção do byte order mark UTF-8 (`\u{FEFF}`) para o Excel. |
| **Manipulação de Arquivos** | `pathlib.Path`, `shutil` | `std::fs`, `std::path::PathBuf` | Criação de pastas, cópia de anexos, movimentação atômica e exclusão recursiva. |
| **Interface Gráfica (GUI)** | `tkinter`, `ttkthemes`, `pillow` | **Tauri v2** ou **Slint** | Veja análise detalhada na Seção 4. |

---

## 4. Análise de Alternativas para a Interface Gráfica (GUI)

A escolha do framework de interface gráfica é o aspecto mais determinante para o sucesso da migração. Avaliamos as 4 principais soluções do ecossistema Rust:

```
+-----------------------------------------------------------------------------------------+
|                                    FRAMEWORKS DE GUI                                    |
+--------------------+---------------------+----------------------+-----------------------+
|  Critério          | Tauri v2 (Recom. 1) | Slint (Recom. 2)     | Iced                  |
+--------------------+---------------------+----------------------+-----------------------+
| Arquitetura        | Rust + WebView2     | DSL Nativa compilada | 100% Rust (Elm-like)  |
| Visual / Estilo    | Moderno (HTML/CSS)  | Nativo customizável  | Minimalista (GPU/WGPU)|
| Tamanho do .exe    | ~10 - 15 MB         | ~8 - 12 MB           | ~15 - 25 MB           |
| Consumo de RAM     | ~30 - 45 MB         | ~15 - 25 MB          | ~30 - 50 MB           |
| Facilidade p/ CRUD | Altíssima (Tabelas) | Alta                 | Moderada/Trabalhosa   |
| Dependências OS    | WebView2 (já no Win)| Nenhuma              | Nenhuma (Vulkan/DX12) |
+--------------------+---------------------+----------------------+-----------------------+
```

### Opção 1: **Tauri v2 (Recomendação Principal)**
- **Como funciona**: A lógica de negócios, banco SQLite, regras de prazos e operações de arquivos rodam em Rust nativo. A interface visual é renderizada no componente **Microsoft Edge WebView2**, que já vem pré-instalado em todas as máquinas Windows 10 e 11.
- **Por que é a melhor escolha**:
  - Tabelas de dados ricas com ordenação, busca instantânea, badges coloridos de status (Atrasada, Vencendo) e paginação são triviais de construir e estilizar com HTML/CSS (ou frameworks leves como Tailwind CSS).
  - Janelas modais, abas de histórico e visualizadores de e-mail têm suporte visual idêntico ou superior ao desktop moderno.
  - Segurança: o frontend não tem acesso arbitrário ao sistema operacional; toda operação passa por comandos IPC fortemente tipados no Rust (`#[tauri::command]`).
  - Binário final compacto (~10–15 MB) com ícone próprio e inicialização em menos de 200ms.

### Opção 2: **Slint (Melhor alternativa 100% nativa sem Webview)**
- **Como funciona**: Interface declarativa compilada diretamente para código nativo C++/Rust, sem uso de navegador embutido.
- **Vantagens**: Não depende de WebView2 nem de Node.js no build; consumo de memória minúsculo (~15 MB).
- **Desvantagens**: Sintaxe DSL própria (`.slint`) e ecossistema de componentes de tabelas mais enxuto que o ecossistema web.

### Opções Descartadas:
- **Iced**: Excelente para apps criativos/reativos, mas a construção de tabelas administrativas e diálogos complexos de CRUD exige muito código boilerplate.
- **egui / eframe**: Modo imediato (immediate mode). É ideal para painéis de jogos e ferramentas internas de engenharia, mas inadequado para formulários comerciais corporativos com campos de texto com foco, navegação por tab e seleção padrão de sistema operacional.

---

## 5. Comparativo: Python vs. Rust

| Métrica / Aspecto | Implementação Atual (Python) | Nova Implementação (Rust + Tauri) |
| :--- | :--- | :--- |
| **Distribuição para o Usuário** | Requer Python instalado, `.venv` ou script PowerShell `criar_atalho_desktop.ps1`. | **Arquivo único `.exe`** (duplo clique, sem instaladores adicionais). |
| **Tempo de Inicialização** | ~1,5 a 3,0 segundos (carga do interpretador e módulos). | **< 150 milissegundos** (código de máquina nativo). |
| **Consumo de Memória (RAM)** | ~90 MB a 140 MB | **~25 MB a 40 MB** |
| **Tratamento de Falhas** | Exceções dinâmicas em runtime (`NoneType`, `KeyError`, etc.). | **Garantia em tempo de compilação** (`Result<T, E>` e `Option<T>`). |
| **Concorrência e Responsividade** | Tkinter roda em thread única (importação de e-mails pesada pode travar a tela). | **Multithreading seguro nativo** (importações e relatórios em background com barra de progresso). |
| **Segurança do Código** | Código-fonte visível ou facilmente descompilável. | Código compilado e otimizado em binário de máquina. |

---

## 6. Arquitetura Proposta para o Projeto em Rust

A estrutura recomendada para o repositório em Rust segue o padrão modular e desacoplado:

```
gestao_demandas/
├── Cargo.toml                  # Configuração de dependências e perfil de build
├── build.rs                    # Configurações de compilação do Windows (ícone, manifesto)
├── src-tauri/                  # (Caso utilize Tauri)
│   ├── Cargo.toml
│   ├── tauri.conf.json         # Permissões, título, tamanho de janela, ícones
│   └── src/
│       ├── main.rs             # Ponto de entrada e registro de comandos IPC
│       ├── config.rs           # Constantes de pastas, status e prazos
│       ├── models.rs           # Structs: Demanda, Historico, Anexo, Classificacao
│       ├── banco.rs            # Inicialização do SQLite, migrações e pool
│       ├── classificacao.rs    # Regex, normalização NFKD e regras de negócio
│       ├── servicos.rs         # CRUD, auditoria de histórico e anexos físicos
│       ├── importacao.rs       # Leitura da pasta inbox e idempotência
│       └── relatorios.rs       # Renderização de relatório HTML e CSV
└── ui/                         # Interface do Usuário (HTML5, CSS3, JS/TS)
    ├── index.html              # Tela principal: Dashboard, Cards e Tabela de Demandas
    ├── styles.css              # Estilos baseados na paleta do projeto original
    ├── app.js                  # Controle de telas, filtros e chamadas à API Rust
    └── modais/                 # Modais de Nova Demanda, Histórico e Visualização
```

### Exemplo de Modelagem das Estruturas em Rust (`models.rs`):

```rust
use chrono::{NaiveDate, NaiveDateTime};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Demanda {
    pub id: Option<i64>,
    pub titulo: String,
    pub descricao: String,
    pub entregavel: String,
    pub ente: String,
    pub tipo: String,
    pub prioridade: String,
    pub status: String,
    pub responsavel: String,
    pub processo_sei: String,
    pub remetente: String,
    pub remetente_email: String,
    pub origem: String,
    pub email_id: Option<String>,
    pub email_corpo: String,
    pub recebido_em: Option<NaiveDate>,
    pub prazo: Option<NaiveDate>,
    pub prazo_interno: Option<NaiveDate>,
    pub concluido_em: Option<NaiveDate>,
    pub criado_em: NaiveDateTime,
    pub atualizado_em: NaiveDateTime,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Classificacao {
    pub titulo: String,
    pub ente: String,
    pub tipo: String,
    pub prioridade: String,
    pub processo_sei: String,
    pub prazo: Option<NaiveDate>,
    pub prazo_interno: Option<NaiveDate>,
    pub dias_uteis: bool,
}
```

---

## 7. Roadmap de Migração Passo a Passo

```
Fase 0: Setup       Fase 1: Core/DB     Fase 2: I/O & Regras   Fase 3: GUI           Fase 4: Entrega
+---------------+   +---------------+   +-------------------+  +------------------+  +---------------+
| Instalação    |   | SQLite        |   | Classificação     |  | Janela Principal |  | Paridade      |
| Rustup & MSVC |-->| Models        |-->| Importação Inbox  |->| Tabelas/Filtros  |->| Testes Unit.  |
| Cargo Init    |   | Migrations    |   | Relatórios HTML   |  | Modais de Edição |  | Build Release |
+---------------+   +---------------+   +-------------------+  +------------------+  +---------------+
```

### Fase 0: Preparação do Ambiente de Desenvolvimento
1. Instalar o compilador Rust via **Rustup** (`https://rustup.rs`).
2. Instalar o pacote **Visual Studio C++ Build Tools** (necessário para compilação nativa no Windows MSVC).
3. Testar o ambiente via terminal: `cargo --version` e `rustc --version`.

### Fase 1: Núcleo de Dados e Domínio
1. Criar o projeto Cargo com as dependências `rusqlite`, `serde`, `chrono` e `regex`.
2. Implementar `src/banco.rs` com as tabelas `demandas`, `historico`, `anexos`, chaves estrangeiras e índices.
3. Implementar `src/servicos.rs` com as funções de CRUD, geração de log de histórico e manipulação de pastas de anexos.

### Fase 2: Regras de Classificação, Importação e Relatórios
1. Portar `classificacao.py` para `classificacao.rs` com as expressões regulares e lógica de dias úteis/órgãos de controle.
2. Escrever os **testes unitários equivalentes** em Rust (`#[cfg(test)]`) para garantir 100% de paridade com os 18 testes unitários existentes do Python.
3. Implementar a leitura de pacotes JSON da pasta `dados/inbox` e arquivamento em `processados`.
4. Implementar a geração do relatório HTML responsivo e do CSV formatado com delimitador `;` e UTF-8-BOM.

### Fase 3: Desenvolvimento da Interface Gráfica
1. Configurar o **Tauri v2** (`cargo tauri init`).
2. Recriar a janela principal com os cards informativos de topo (Total, Abertas, Atrasadas, Vencendo em 7 dias).
3. Implementar a tabela interativa com filtro por status, texto de busca e período de recebimento.
4. Construir o formulário de cadastro/edição de demandas, visualização do histórico e gerenciador de anexos (com acionamento de abertura pelo visualizador padrão do Windows).

### Fase 4: Homologação, Empacotamento e Entrega
1. Testar o fluxo ponta a ponta com a macro VBA do Outlook.
2. Gerar a compilação final otimizada: `cargo tauri build` ou `cargo build --release`.
3. Obter o arquivo executável único `gestao_demandas.exe` e validar em uma máquina Windows limpa sem Python instalado.

---

## 8. Estimativa de Esforço e Conclusão

- **Backend / Core Rust** (Banco, Classificação, Importação, Relatórios e Testes): **1 a 2 semanas**.
- **Interface Gráfica e Interações** (Telas, Modais, Tabela, Atalhos, Estilização): **2 a 3 semanas**.
- **Homologação e Ajustes Finais**: **1 semana**.
- **Esforço Total Estimado**: **4 a 6 semanas** para substituição completa e definitiva.

### Conclusão
A migração de Python para Rust é uma evolução técnica plenamente factível, sem riscos de quebra na integração com o Outlook e com benefícios substanciais na experiência do usuário final, estabilidade e simplicidade de implantação em ambiente Windows corporativo.
