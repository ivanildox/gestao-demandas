"""Atalho de inicialização: `python principal.py`.

Mantém a compatibilidade com quem executava o `.exe` na raiz do projeto.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gestao_demandas.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())





