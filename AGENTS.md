# AGENTS.md

## Commands

Setup (Windows, Python 3.13):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Run:

```powershell
.\iniciar.cmd
# or: .venv\Scripts\python.exe -m gestao_demandas
# or: .venv\Scripts\python.exe principal.py
```

Core tests:

```powershell
.venv\Scripts\python.exe -m unittest discover -s testes -v
```

Single test:

```powershell
.venv\Scripts\python.exe -m unittest testes.test_nucleo.TestClassificacao.test_extrai_sei
```

Integration test (direct only; do not use discover):

```powershell
.venv\Scripts\python.exe testes\test_integracao.py
```

No lint or typecheck tooling is configured.

## Architecture

- GUI desktop app: Python + PyQt6 + SQLite.
- Entrypoints: `gestao_demandas/main.py`, `gestao_demandas/__main__.py`, and `principal.py`.
- Business logic and DB access are in `gestao_demandas/` (`banco.py`, `servicos.py`, `importacao.py`, `relatorios.py`); UI is `app_ui.py`.
- Data location is resolved by `config.get_dados_dir()`. The development launcher points `GESTAO_DEMANDAS_DADOS` to the project's `dados/` folder.
- `dados/`, `.venv/`, and `__pycache__/` are gitignored. `dados/` is local state and must not be committed.

## Testing quirks

- Core tests use an in-memory SQLite DB via `banco.conectar_em(":memory:")`.
- Integration test copies `dados/gestao.db` into a temp `dados/` and `chdir`s there; it aborts if it would use the real project data.
- Integration requires example JSON packages in `dados/inbox/processados` for import tests.
- GUI parts of integration set `QT_QPA_PLATFORM=offscreen` internally.

## Development

- `iniciar.cmd` launches the application using the project's `.venv`; executable and portable-package generation are not configured.
