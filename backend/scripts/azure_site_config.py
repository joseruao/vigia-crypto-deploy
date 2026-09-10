"""Aplica a configuração de site (appCommandLine, alwaysOn, healthCheckPath) no Azure.

Porque não `az webapp config set`: os comandos de arranque têm `$()`, aspas e
barras `/` que o cmd/bash do Windows corrompem; aqui o corpo vai num ficheiro
JSON e é enviado com `az rest` (sem passar pelo shell).

Uso:
  python scripts/azure_site_config.py --app vigia-consulta -g rg-vigia-auditor \
      --command 'D=$(find /tmp -maxdepth 2 -name main.py | head -1) && cd "$(dirname "$D")" && gunicorn ...' \
      --health /api/health
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

AZ = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
SUB = "908e53e3-783f-46d2-b18f-8a9e384f85ea"
API = "2023-01-01"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("-g", "--resource-group", required=True)
    p.add_argument("--command", default=None, help="appCommandLine (comando de arranque)")
    p.add_argument("--health", default=None, help="healthCheckPath (ex.: /api/health)")
    p.add_argument("--always-on", dest="always_on", action="store_true", default=None)
    p.add_argument("--no-always-on", dest="always_on", action="store_false")
    p.add_argument("--fx", default="PYTHON|3.12", help="linuxFxVersion")
    p.add_argument("--show", action="store_true", help="só mostrar a config atual")
    a = p.parse_args()

    url = (
        f"https://management.azure.com/subscriptions/{SUB}/resourceGroups/{a.resource_group}"
        f"/providers/Microsoft.Web/sites/{a.app}/config/web?api-version={API}"
    )

    if a.show:
        out = subprocess.run([AZ, "rest", "--method", "GET", "--url", url],
                             capture_output=True, text=True)
        data = json.loads(out.stdout or "{}")
        props = data.get("properties", {})
        print(json.dumps({k: props.get(k) for k in
                          ("linuxFxVersion", "appCommandLine", "alwaysOn", "healthCheckPath")},
                         indent=2, ensure_ascii=False))
        return

    props: dict[str, object] = {"linuxFxVersion": a.fx}
    if a.command is not None:
        props["appCommandLine"] = a.command
    if a.health is not None:
        props["healthCheckPath"] = a.health
    if a.always_on is not None:
        props["alwaysOn"] = a.always_on

    body = {"properties": props}
    tmp = Path(tempfile.gettempdir()) / f"siteconfig_{a.app}.json"
    tmp.write_text(json.dumps(body), encoding="utf-8")

    out = subprocess.run([AZ, "rest", "--method", "PUT", "--url", url,
                          "--body", f"@{tmp}", "--headers", "Content-Type=application/json"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        print("ERRO:", out.stderr[-1500:], file=sys.stderr)
        sys.exit(1)
    data = json.loads(out.stdout or "{}").get("properties", {})
    print("OK:", json.dumps({k: data.get(k) for k in
                             ("linuxFxVersion", "appCommandLine", "alwaysOn", "healthCheckPath")},
                            ensure_ascii=False))


if __name__ == "__main__":
    main()
