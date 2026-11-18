# Gestão de Demandas (Python + PyQt6)

Sistema desktop nativo em **Python + PyQt6** com SQLite embutido para registrar, classificar e acompanhar demandas.

As demandas entram por dois caminhos:
1. **E-mail (Outlook Clássico)**: a macro `vba/ExportarParaGestao.bas` exporta o e-mail selecionado para a fila (`dados/inbox`). O sistema importa a fila e cria a demanda automaticamente classificada (ente, tipo, nº SEI, prazos e prioridade).
2. **Cadastro direto**: botão "➕ Nova Demanda" na interface.

O sistema inclui controle de anexos por demanda, histórico completo de auditoria com diff de alterações, relatórios em HTML responsivo e exportação de planilhas CSV com suporte direto ao Microsoft Excel em português.

O acompanhamento do ciclo inclui a escolha da ação necessária (**encaminhar**, **responder** ou ambas), responsável, status de trabalho e prazos. Na tela principal, o botão **Mover**, ao lado de **Editar**, registra data, destino e observação, exibe as movimentações em tabela e permite exportar o histórico em HTML. A edição contém os dados gerais, anexos e, quando disponível, o e-mail original. O histórico de auditoria continua sendo registrado separadamente.

Fluxo sugerido: **Novo → Em triagem → Encaminhada / Em atendimento → Aguardando resposta ou informações → Concluída**. Os status podem ser ajustados na edição; demandas antigas continuam mantendo seus status existentes.

---

## Executar o Programa

### Inicializar pelo terminal

Na raiz do projeto:

```powershell
.\iniciar.cmd
```

O `iniciar.cmd` executa o aplicativo pelo ambiente virtual `.venv`. Os dados locais (banco SQLite, anexos, inbox e relatórios) ficam na pasta `dados/` do projeto.

> **Tema**: a interface é **clara** (fundo `#f1f5f9`, painéis brancos, texto `#0f172a`). O tema é aplicado pelo módulo `gestao_demandas/tema.py` e não muda conforme o "modo escuro" do Windows — o estilo **Fusion** com uma paleta clara explícita é forçado em toda execução.

> **Interface**: a janela principal abre **maximizada**, ocupando toda a área de trabalho. A tela inicial é dividida em duas: a **relação de demandas** na parte de cima (1/4 da altura) e o **detalhamento da demanda selecionada** — prazo interno, prazo externo e entregável esperado — na parte de baixo (3/4). Os botões **Editar** e **Mover** ficam na primeira coluna da tabela (clicar na linha apenas seleciona o registro). As telas de cadastro/edição são exibidas **centralizadas** na tela.

### Ambiente de desenvolvimento

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Inicie o programa pelo ambiente de desenvolvimento:

```powershell
.venv\Scripts\python.exe -m gestao_demandas
```

### Automação

O workflow de CI (`.github/workflows/ci.yml`) instala as dependências e executa os testes do núcleo e de integração em pushes e pull requests para `main`. A geração de executáveis e pacotes de distribuição está desativada; o projeto permanece voltado ao desenvolvimento.

---

## Estrutura do Projeto

| Diretório / Arquivo | Função |
| :--- | :--- |
| `iniciar.cmd` | Inicializa o aplicativo usando o ambiente virtual de desenvolvimento |
| `gestao_demandas/` | Pacote Python com a implementação completa do sistema |
| `gestao_demandas/main.py` | Ponto de entrada do aplicativo (`python -m gestao_demandas`) |
| `gestao_demandas/app_ui.py` | Interface gráfica em PyQt6 (dashboard, filtros, tabela, modal de edição, toasts) |
| `gestao_demandas/config.py` | Resolução de caminhos e diretórios (`dados/`, `inbox/`, `anexos/`, `relatorios/`) |
| `gestao_demandas/tema.py` | Tema claro da interface (estilo Fusion + paleta explícita) |
| `gestao_demandas/banco.py` | Conexão SQLite, criação de tabelas e migrações |
| `gestao_demandas/models.py` | Modelos de dados fortemente tipados |
| `gestao_demandas/classificacao.py` | Heurísticas de regex, remoção de acentos NFKD e cálculo de prazos úteis |
| `gestao_demandas/servicos.py` | Regras de negócio (CRUD, auditoria de histórico e manipulação de anexos) |
| `gestao_demandas/importacao.py` | Importação em lote dos pacotes JSON de `dados/inbox` e arquivamento |
| `gestao_demandas/relatorios.py` | Geração de relatório HTML e CSV formatado (UTF-8-BOM com separador `;`) |
| `icons/` | Ícones oficiais da aplicação (`.ico` multi-resolução e `.png`) |
| `vba/ExportarParaGestao.bas` | Macro do Outlook para envio de e-mails à fila |
| `principal.py` | Atalho de inicialização em modo fonte (`python principal.py`) |
| `testes/` | Testes do núcleo (`test_nucleo.py`) e de integração (`test_integracao.py`) |
| `requirements.txt` | Dependências do projeto |
| `dados/` | Banco de dados local (`gestao.db`), `anexos/`, `inbox/` e `relatorios/` |

---

## Testes

```powershell
# testes do núcleo
.venv\Scripts\python.exe -m unittest discover -s testes -v

# teste de integração (usa uma cópia temporária do banco, não toca nos dados reais)
.venv\Scripts\python.exe testes\test_integracao.py
```

---

## Instalar a Macro no Outlook

A macro VBA do Outlook se integra de forma transparente ao sistema:

1. **Abra o programa pelo menos uma vez** neste ambiente: ele cria a pasta de dados do projeto e registra o caminho. Não é preciso editar caminho na macro.
2. No Outlook clássico: pressione `Alt + F11` → **Arquivo > Importar arquivo** → selecione `vba/ExportarParaGestao.bas`.
3. Para usar: selecione qualquer e-mail no Outlook e execute a macro `EnviarParaGestao` (pode ser vinculada a um botão na barra de ferramentas do Outlook). A macro `MostrarPastaEntrada` mostra a pasta e a origem do caminho em uso.
4. No **Gestão de Demandas**, clique no botão **📥 Importar E-mails**. O sistema processará os pacotes e moverá os arquivos para `dados/inbox/processados`. Se a fila estiver vazia, o aviso informa a pasta verificada.

Se quiser fixar um caminho manualmente, preencha a constante `DADOS_FIXO` no topo da macro ou defina a variável de ambiente `GESTAO_DEMANDAS_DADOS` — ambas têm prioridade sobre o registro automático.

---

## Regras de Classificação Automática

- **Nº SEI**: padrão `00000.000000/0000-00`.
- **Prazo Externo**: data explícita próxima de "prazo", "até" ou "limite" (dd/mm/aaaa) ou menção relativa ("X dias").
  Se houver "dias úteis" no texto, a contagem pula sábados e domingos.
- **Prazo Interno**: 2 dias antes do prazo externo (1 dia se o prazo for curto até 4 dias; 3 dias para Ministério Público e Tribunal de Contas), ajustado para não cair em fim de semana.
- **Prioridade**: Alta para órgãos de controle ou prazo em até 5 dias; senão Média.
- **Tipo e Ente**: detectados por análise de palavras-chave no assunto e no corpo do e-mail.
- **Edição Livre**: a classificação automática é uma sugestão; todos os campos podem ser editados na tela.
