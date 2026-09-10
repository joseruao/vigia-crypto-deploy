"""Constrói o zip de deploy do auditor para o Azure App Service.

Receita (aprendida a 2026-09-10, ver DEPLOY_AZURE.md):
- o zip tem de usar barras `/` nos arcnames — o `Compress-Archive` do Windows
  escreve `Api\\main.py` e a extração no Linux não cria a pasta (o gunicorn
  morre com ModuleNotFoundError);
- o `requirements.txt` do zip é PRÓPRIO (não é o do backend/) e tem de incluir
  tudo o que as rotas importam: o `python-multipart` faltava e o arranque
  rebentava com `RuntimeError: Form data requires "python-multipart"` na rota
  `/auditor/upload` (gunicorn exit 3 → 503).

Uso:  python build_azure_zip.py [destino.zip]
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = Path.home() / "Downloads" / "auditor_api.zip"

# Versões fixas iguais às que já corriam em produção, + python-multipart.
REQUIREMENTS = """fastapi==0.115.0
uvicorn==0.30.6
gunicorn==23.0.0
python-dotenv==1.0.1
requests==2.32.3
pypdf==6.13.2
openai==1.51.0
python-multipart>=0.0.9
"""

# CUIDADO: `audits/`, `reports/` e `storage/` DENTRO de auditor/ são pacotes Python
# (o código importa-os) — nunca os excluir. Os dados de clientes vivem em
# backend/audits/, fora desta pasta.
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv", "_uploads", "tests"}
SKIP_SUFFIXES = {".pyc", ".db", ".zip", ".md"}
SKIP_NAMES = {"build_azure_zip.py"}


def build(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("requirements.txt", REQUIREMENTS)
        for path in sorted(HERE.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(HERE)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if path.suffix in SKIP_SUFFIXES or path.name in SKIP_NAMES:
                continue
            # arcname com barras `/` — é isto que o Oryx precisa no Linux
            z.write(path, "auditor/" + rel.as_posix())
            n += 1
    print(f"OK: {n} ficheiros + requirements.txt -> {out_path}")
    return out_path


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    build(dest)
