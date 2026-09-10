# Auditor API — deploy no Azure App Service

App: **vigia-auditor-api** (`https://vigia-auditor-api.azurewebsites.net`) · RG `rg-vigia-auditor` · plano B1 italynorth
Página de trabalho local (UI v0): `C:\Users\joser\audit-ui` → aponta para esta API.

## Receita (validada a 2026-09-10)

```bash
# 1) zip com barras `/` (o Compress-Archive do Windows escreve `auditor\x.py` e a
#    extração Linux não cria pastas → ModuleNotFoundError no gunicorn)
python backend/auditor/build_azure_zip.py          # -> ~/Downloads/auditor_api.zip

# 2) deploy (Oryx faz o pip install; demora 5-10 min)
az webapp deploy -g rg-vigia-auditor -n vigia-auditor-api \
    --src-path "$HOME/Downloads/auditor_api.zip" --type zip
```

No Git Bash, pôr o az no PATH e **usar `MSYS_NO_PATHCONV=1`** quando um argumento
começa por `/` (senão o Git Bash converte `/health` em `C:/Program Files/Git/health`):

```bash
export PATH="$PATH:/c/Program Files/Microsoft SDKs/Azure/CLI2/wbin"
```

## Configuração do site

Ver `backend/scripts/azure_site_config.py` (usa `az rest`, evita o shell a corromper
`$()`, aspas e `/`). Estado atual:

- `appCommandLine`: `D=$(find /tmp -maxdepth 3 -path "*/auditor/web.py" 2>/dev/null | head -1); cd "${D%/auditor/web.py}" && gunicorn -w 1 -k uvicorn.workers.UvicornWorker auditor.web:app --bind 0.0.0.0:8000 --timeout 600 > /home/LogFiles/startup_manual.log 2>&1`
- `alwaysOn`: true · `healthCheckPath`: `/` · `linuxFxVersion`: `PYTHON|3.12`
- App settings: `AUDITOR_AI_PROVIDER`, `AZURE_OPENAI_*`, `AZURE_DOCINTEL_*`, `AUDITOR_OCR_ENGINE`,
  `AUDITOR_ACCESS_CODE`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `WEBSITES_PORT=8000`

## Bugs já pagos (não repetir)

1. **`python-multipart` fora do `requirements.txt` do zip** → a rota `/auditor/upload`
   usa `File`/`Form`; o FastAPI rebenta no import da rota com
   `RuntimeError: Form data requires "python-multipart" to be installed` → gunicorn
   **exit 3** → o site cancela o arranque e devolve **503 em tudo**. O zip tem
   requirements PRÓPRIO (não é o `backend/requirements.txt`).
2. **Falta `SCM_DO_BUILD_DURING_DEPLOYMENT=true`** → o Oryx não corre o pip e a app
   crash-loopa (estado `QuotaExceeded` falso, Kudu 403).
3. O código é extraído para `/tmp/<id>` (não `/home/site/wwwroot`) — o comando de
   arranque tem de procurar lá (daí o `find`).

## Diagnóstico rápido

```bash
az webapp log download -g rg-vigia-auditor -n vigia-auditor-api --log-file ~/auditor_logs.zip
# o traceback do gunicorn fica em LogFiles/startup_manual.log dentro do zip
```
