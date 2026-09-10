"""Empurra variáveis de ambiente para as Application Settings de um Web App Azure.

Existem dois modos:
  --env-file <ficheiro>     lê um .env local (KEY=VALUE, aceita comentários)
  --from-railway <serviço>  lê `railway variables --json` (projeto/ambiente ligados)
                            e ignora as vars internas RAILWAY_*

Os valores NUNCA são impressos no terminal (só os nomes), para não deixar
segredos em logs/transcrições.

Uso:
  python scripts/azure_sync_settings.py --app vigia-consulta -g rg-vigia-auditor \
      --env-file ../../joseruao/consulta/.env

  python scripts/azure_sync_settings.py --app vigia-api -g rg-vigia-auditor \
      --from-railway vigia-crypto -p spectacular-imagination -e production
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def _railway_bin() -> str:
    """No Windows o CLI do Railway é um shim npm — o subprocess precisa do `.cmd`."""
    for candidate in ("railway.cmd", "railway.exe", "railway"):
        found = shutil.which(candidate)
        if found:
            return found
    return "railway"


def from_railway(service: str, project: str | None, environment: str | None) -> dict[str, str]:
    cmd = [_railway_bin(), "variables", "-s", service, "--json"]
    if project:
        cmd += ["-p", project]
    if environment:
        cmd += ["-e", environment]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    data = json.loads(raw)
    return {k: v for k, v in data.items() if not k.startswith("RAILWAY_") and v is not None}


def push(app: str, rg: str, settings: dict[str, str]) -> None:
    if not settings:
        print("nada para enviar")
        return
    args = [AZ, "webapp", "config", "appsettings", "set", "-g", rg, "-n", app, "--settings"]
    args += [f"{k}={v}" for k, v in settings.items()]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERRO:", result.stderr[-2000:], file=sys.stderr)
        sys.exit(1)
    print(f"OK: {len(settings)} settings aplicadas em {app}: {', '.join(sorted(settings))}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("-g", "--resource-group", required=True)
    p.add_argument("--env-file")
    p.add_argument("--from-railway")
    p.add_argument("-p", "--project")
    p.add_argument("-e", "--environment")
    a = p.parse_args()

    if a.env_file:
        settings = parse_env_file(Path(a.env_file))
    elif a.from_railway:
        settings = from_railway(a.from_railway, a.project, a.environment)
    else:
        p.error("indica --env-file ou --from-railway")
        return
    push(a.app, a.resource_group, settings)


if __name__ == "__main__":
    main()
