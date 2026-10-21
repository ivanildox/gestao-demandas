# Gestão de Demandas (Rust + egui)

Sistema desktop nativo em **Rust puro (egui/eframe)** com SQLite embutido para registrar, classificar e acompanhar demandas.

As demandas entram por dois caminhos:
1. **E-mail (Outlook Clássico)**: a macro `vba/ExportarParaGestao.bas` exporta o e-mail selecionado para a fila (`dados/inbox`). O sistema importa a fila e cria a demanda automaticamente classificada (ente, tipo, nº SEI, prazos e prioridade).
2. **Cadastro direto**: botão "➕ Nova Demanda" na interface.

O sistema inclui controle de anexos por demanda, histórico completo de auditoria com diff de alterações, relatórios em HTML responsivo e exportação de planilhas CSV com suporte direto ao Microsoft Excel em português.

> **Nota de migração**: a versão anterior usava Tauri v2 (Rust + WebView2/HTML). A interface foi reescrita em **egui**, uma biblioteca de GUI 100% nativa em Rust. O executável resultante não depende mais do runtime WebView2 do Windows — é um único `.exe` autocontido.

---

## Executar o Programa

O sistema é distribuído como um único arquivo executável nativo do Windows, sem instalador e sem dependências externas:

- **Download pronto**: baixe o `gestao_demandas.exe` mais recente na aba [Releases](../../releases) do repositório.
- **Atalho na Área de Trabalho**: Um atalho **"Gestão de Demandas"** pode ser criado na Área de Trabalho com o ícone oficial do programa.
- **Executável Direto**: `gestao_demandas.exe` na raiz do projeto (após compilar localmente).

### Build e releases automatizados

O repositório tem dois workflows de GitHub Actions (`.github/workflows/`):

- **CI** (`ci.yml`): roda `cargo check` e `cargo test` a cada push/PR na `main`, usando o toolchain MSVC (já disponível nos runners `windows-latest`, sem precisar de configuração extra).
- **Release** (`release.yml`): ao criar uma tag no padrão `v*.*.*` (ex.: `v0.3.0`), compila o projeto em modo release e publica o `gestao_demandas.exe` automaticamente como anexo da Release correspondente no GitHub.

Para publicar uma nova versão:

```powershell
git tag v0.3.0
git push origin v0.3.0
```

Para recriar o atalho da Área de Trabalho caso necessário:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\criar_atalho_desktop.ps1
```

---

## Estrutura do Projeto

| Diretório / Arquivo | Função |
| :--- | :--- |
| `gestao_demandas.exe` | Executável principal compilado em release (nativo Windows, autocontido) |
| `src-tauri/src/main.rs` | Ponto de entrada do executável (`eframe::run_native`) |
| `src-tauri/src/app_ui.rs` | Interface gráfica completa em egui (dashboard, filtros, tabela, modal de edição, toasts) |
| `src-tauri/src/config.rs` | Resolução de caminhos e diretórios (`dados/`, `inbox/`, `anexos/`, `relatorios/`) |
| `src-tauri/src/banco.rs` | Conexão SQLite nativa (`rusqlite`), criação de tabelas e migrações |
| `src-tauri/src/models.rs` | Modelos de dados fortemente tipados em Rust |
| `src-tauri/src/classificacao.rs` | Heurísticas de regex, remoção de acentos NFKD e cálculo de prazos úteis |
| `src-tauri/src/servicos.rs` | Regras de negócio (CRUD, auditoria de histórico e manipulação de anexos) |
| `src-tauri/src/importacao.rs` | Importação em lote dos pacotes JSON de `dados/inbox` e arquivamento |
| `src-tauri/src/relatorios.rs` | Geração de relatório HTML e CSV formatado (UTF-8-BOM com separador `;`) |
| `src-tauri/icons/` | Ícones oficiais da aplicação (`.ico` multi-resolução e `.png`) |
| `vba/ExportarParaGestao.bas` | Macro do Outlook para envio de e-mails à fila |
| `dados/` | Banco de dados local (`gestao.db`), `anexos/`, `inbox/` e `relatorios/` |
| `docs/estudo_migracao_rust.md` | Estudo detalhado de viabilidade técnica da conversão para Rust |

---

## Compilação

O projeto é 100% Rust (sem Node.js/npm). É necessário um toolchain Rust com um linker C funcional. Duas opções testadas:

**Opção A — toolchain GNU + w64devkit (mingw-w64)**:
```powershell
rustup default stable-x86_64-pc-windows-gnu
$env:PATH = "$env:USERPROFILE\w64devkit\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"
```

**Opção B — toolchain MSVC + Visual Studio Build Tools** ("Desenvolvimento para desktop com C++"):
```powershell
rustup default stable-x86_64-pc-windows-msvc
```

Para executar os testes unitários do núcleo em Rust:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --release
```

Para compilar uma nova versão de produção (Release):

```powershell
cargo build --manifest-path src-tauri/Cargo.toml --release
Copy-Item src-tauri\target\release\gestao_demandas.exe gestao_demandas.exe -Force
```

---

## Instalar a Macro no Outlook

A macro VBA do Outlook se integra de forma transparente ao sistema nativo em Rust:

1. Abra `vba/ExportarParaGestao.bas` e confirme que `INBOX_PATH` aponta para a pasta `dados\inbox` deste projeto.
2. No Outlook clássico: pressione `Alt + F11` → **Arquivo > Importar arquivo** → selecione o arquivo `.bas`.
3. Para usar: selecione qualquer e-mail no Outlook e execute a macro `EnviarParaGestao` (pode ser vinculada a um botão na barra de ferramentas do Outlook).
4. No **Gestão de Demandas**, clique no botão **📥 Importar E-mails**. O sistema processará os pacotes e moverá os arquivos para `dados/inbox/processados`.

---

## Regras de Classificação Automática

- **Nº SEI**: padrão `00000.000000/0000-00`.
- **Prazo Externo**: data explícita próxima de "prazo", "até" ou "limite" (dd/mm/aaaa) ou menção relativa ("X dias").
  Se houver "dias úteis" no texto, a contagem pula sábados e domingos.
- **Prazo Interno**: 2 dias antes do prazo externo (1 dia se o prazo for curto até 4 dias; 3 dias para Ministério Público e Tribunal de Contas), ajustado para não cair em fim de semana.
- **Prioridade**: Alta para órgãos de controle ou prazo em até 5 dias; senão Média.
- **Tipo e Ente**: detectados por análise de palavras-chave no assunto e no corpo do e-mail.
- **Edição Livre**: a classificação automática é uma sugestão; todos os campos podem ser editados na tela.
