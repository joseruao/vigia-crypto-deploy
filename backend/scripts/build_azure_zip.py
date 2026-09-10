"""Constrói o zip de deploy do backend do vigia para o Azure App Service.

Inclui: Api/, utils/, worker/, dailyworker/, analisegrafica/, requirements.txt
Exclui: .env (as chaves vão por Application Settings), auditor/ (módulo local —
não é importado pela API), tests/, audits/ (dados de clientes), scripts/, logs,
__pycache__ e artefactos locais.

Os arcnames usam barras `/`: o `Compress-Archive` do Windows escreve `Api\\main.py`
e a extração Linux não cria pastas (foi o que partiu o deploy do devil em 21 Ago).

Uso:  python scripts/build_azure_zip.py [destino.zip]
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_OUT = Path.home() / "Downloads" / "vigia_api_azure.zip"

INCLUDE_DIRS = ("Api", "utils", "worker", "dailyworker", "analisegrafica")
INCLUDE_FILES = ("requirements.txt", "__init__.py")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv", "tests", "audits", "auditor", "scripts", ".next"}


def build(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in INCLUDE_FILES:
            p = BACKEND / name
            if p.exists():
                z.write(p, name)
                n += 1
        for d in INCLUDE_DIRS:
            for path in sorted((BACKEND / d).rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(BACKEND)
                if any(part in SKIP_DIRS for part in rel.parts):
                    continue
                if path.suffix in {".pyc", ".pyo"} or path.name == ".env":
                    continue
                z.write(path, rel.as_posix())
                n += 1
    print(f"OK: {n} ficheiros -> {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT)
