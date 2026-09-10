
---

## ☁️ MIGRAÇÃO RAILWAY → AZURE (10 Set 2026) — o Railway morreu (trial expirado, 03:04 UTC)

Tudo passou para **um único App Service Plan B1 em Italy North** (`plan-vigia-devil-italynorth`,
~€11,5/mês dos créditos de estudante). Quatro apps, todas Running:

| App | URL | Notas |
|---|---|---|
| `vigia-api` | https://vigia-api.azurewebsites.net | API + **crons dentro da app**, PYTHON\|3.13, alwaysOn |
| `vigia-consulta` | https://vigia-consulta.azurewebsites.net | joseruao.com/consulta (rewrite no Vercel), `DATA_DIR=/home/data` |
| `vigia-devil-mistral` | https://vigia-devil-mistral.azurewebsites.net | Mistral UE, alwaysOn |
| `vigia-auditor-api` | https://vigia-auditor-api.azurewebsites.net | UI local em `C:\Users\joser\audit-ui` |

### Deploy da API (receita)
```bash
python backend/scripts/build_azure_zip.py        # zip com barras `/`, sem .env
az webapp deploy -g rg-vigia-auditor -n vigia-api \
    --src-path "C:/Users/joser/Downloads/vigia_api_azure.zip" --type zip
```
Settings: `python backend/scripts/azure_sync_settings.py --app vigia-api -g rg-vigia-auditor --from-railway vigia-crypto -p spectacular-imagination -e production`
(só nomes de variáveis são impressos). Site config: `backend/scripts/azure_site_config.py` (usa `az rest`).
Startup command (o código é extraído para `/tmp/<id>`, daí o `find`):
`D=$(find /tmp -maxdepth 3 -path "*/Api/main.py" | head -1) && cd "${D%/Api/main.py}" && gunicorn -w 1 -k uvicorn.workers.UvicornWorker Api.main:app --bind 0.0.0.0:8000 --timeout 600`

### Crons deixaram de ser serviços
`Api/services/scheduler.py` (APScheduler ligado no `lifespan`, só com `gunicorn -w 1`) lança cada
worker num **subprocesso** — `worker/` e `dailyworker/` são pesados e não podem bloquear a API.
06:00 holdings · 07:00 top100 · 08:00 arkham (UTC). Logs em `/home/LogFiles/cron_<nome>.log`.
`GET /admin/cron-status` e `POST /admin/run-worker?name=…` (header `x-access-code`) — disparo manual.
Desligar: App Setting `VIGIA_CRON_ENABLED=false`. ⚠️ `alwaysOn=true` é obrigatório senão não disparam.

### Quirks do Azure (a dor desta sessão)
- **Git Bash converte argumentos que começam por `/`** para `C:/Program Files/Git/...` → `MSYS_NO_PATHCONV=1`
  (partiu `DATA_DIR=/home/data` e o `healthCheckPath`; a app escreveu dados no /tmp e perdeu-os num restart).
- Chamar `az` **direto do bash** (PATH += `.../CLI2/wbin`) — o wrapper PowerShell come os `|`
  (`--runtime "PYTHON|3.12"` falhava); ids ARM também precisam de `MSYS_NO_PATHCONV=1`.
- `az webapp deploy` pode devolver **504 e o build continuar** em background (foi o caso do vigia-api,
  5-8 min de pip) → confirmar com `az webapp log deployment list`.
- **Kudu basic auth desativada** (401 no `/api/vfs`) → logs com `az webapp log download` (traz `/home/LogFiles`).
- O `--set properties.serverFarmId=<plano>` via `az resource update` **move apps entre planos sem redeploy**.
- `tesseract` não existe na imagem (bullseye EOL): OCR de imagem do football falha; o resto não usa.

### Pendente
`NEXT_PUBLIC_API_URL` no Vercel ainda aponta para o Railway → mudar para `https://vigia-api.azurewebsites.net`
+ redeploy. O `TELEGRAM_BOT_TOKEN` do top100 dá 401 (token inválido — ver log do cron).
Railway fica parado como fallback (projetos `consulta` e `spectacular-imagination`).

---

## 🧾 AI BUSINESS AUDITOR — pipeline local + Azure (16 Ago 2026)

### O que está feito e a funcionar
- **Pipeline completo** em `backend/auditor/`: `python -m auditor init|run|report|upload|pull`
- IA real: **Azure OpenAI gpt-5-mini** (germanywestcentral, zona EUR, deployment `gpt-5-mini`).
  `.env` do backend já tem `AUDITOR_AI_PROVIDER=azure_openai` + `AZURE_OPENAI_*` (chaves também no
  Key Vault `kv-vigia-audit`).
- Fluxo: PDFs → texto (pypdf, local) → JSON estruturado (gpt-5-mini) → SQLite (db/audit.db) →
  regras locais (faturas duplicadas + pagamentos vs extratos CSV) → relatório HTML (reports/report.html).
- **Demo pronta**: `audits/cliente_demo/` com 3 faturas (1 duplicada) + extrato CSV. Corre:
  `cd backend && python -m auditor run ../audits/cliente_demo` (ou `--open`).
- **Blob**: upload/pull funcional via Azure CLI (`--auth-mode login`). Container `audit-backups`.
  500 PDFs: `python -m auditor upload <ws>` → noutro PC: `pull` → `run`.

### Quirks conhecidos (importantes!)
- Azure for Students: política limita regiões a 5 (todas UE); só SKU `GlobalStandard`; api-version
  OpenAI que funciona = **2024-10-21** (2025-01-01 dá 404 nesta conta).
- gpt-5-mini é reasoning model: `max_completion_tokens` ≥4096 na extração (senão devolve vazio).
- `.cmd` com argumentos com espaços falham via cmd direto → usar `powershell -NoProfile -Command`.
- Console Windows cp1252 rebenta com emojis → `cli.py` faz `stdout.reconfigure(utf-8)`.

### Custo real (testes de hoje)
9 chamadas IA + resumos = ~11k tokens ≈ 1-2 cêntimos. Auditoria demo completa ≈ €0.02.
500 PDFs estimado $2-5 (confirmar na 1ª faturação).

### NEEDS_DECISION — José decide quando voltar
1. **UI via Vercel v0**: backend do pipeline está pronto a servir dados. Sugestão: gerar um
   endpoint FastAPI em `backend/Api` (ex. `/auditor/findings?ws=cliente_demo`) ou expor o JSON
   do SQLite; com o v0 crias a página (cards de impacto, tabela de achados, filtros). O relatório
   HTML local já serve para demo ao cliente sem backend extra.
2. ~~**OCR de scans** (PDFs sem texto)~~ ✅ FEITO a 17 Ago — ver secção abaixo.
3. **Fornecedores mais baratos** (comparação de preços/catálogos): ✅ comparador + emails já
   feitos (2ª sessão); falta a comparação de **catálogos/contratos** se quiseres ir mais longe.
4. **Push ao Railway**: módulo auditor é LOCAL (não vai para o backend de produção). Só fará
   sentido expor via API quando a UI v0 existir.

### Web UI + comparador + emails (16 Ago, 2ª sessão)
- **Web UI local**: `backend/start_auditor_web.ps1` → http://localhost:8765. Upload de faturas de
  fornecedores + vendas + extratos (drag-drop), "Correr auditoria", achados com impacto, botão
  "Gerar emails". Servidor FastAPI em `backend/auditor/web.py` (app separado — NÃO toca no Api de produção).
- **Comparador de fornecedores** (`audits/suppliers.py`): agrupa produtos iguais entre fornecedores
  (jaccard ≥0.6 sobre tokens), acha "compra_acima_melhor_preco" com poupança na amostra + anualizada (x4),
  e margens de venda vs compra (achado se margem <15%).
- **Emails** (`audits/email_drafts.py`): rascunhos PT para o fornecedor MAIS BARATO de cada produto
  (a pedir proposta), estado rascunho→enviado. **Nunca envia sem clique + confirm() na UI**; SMTP opcional
  (SMTP_HOST/PORT/USER/PASSWORD/FROM no .env). Demo: rascunho → OfficeMax (vendas@officemax.pt).
- Extração: prompt agora usa seller/buyer (seller = entidade emissora; "Cliente:" no corpo é buyer).
  Compra → contraparte=seller; venda → contraparte=buyer. Fix crítico (antes lia "Cliente:" como fornecedor).
- Demo atualizada: 5 compras (incl. Papelaria Central 15,8% cara vs OfficeMax) + 2 vendas (margem 10,4% baixa)
  + extrato. Resultado: 9 achados, impacto 6.932€ (demo).

### OCR de scans via Azure Document Intelligence (17 Ago, 4ª sessão)
- **Recurso novo**: `vigia-docintel` (kind FormRecognizer, **SKU F0 = grátis**, 20 páginas/mês)
  em germanywestcentral — ao contrário do OpenAI, o F0 **não** foi bloqueado pela subscrição.
  Endpoint `https://vigia-docintel-1f1dc.cognitiveservices.azure.com/`; key1 + endpoint no
  Key Vault (`azure-docintel-key1`, `azure-docintel-endpoint`) e em `backend/.env`
  (`AZURE_DOCINTEL_ENDPOINT`, `AZURE_DOCINTEL_KEY`).
- **Código**: `extractors/ocr_docintel.py` — `build_ocr_client()` + `DocumentIntelligenceOCR`
  (modelo `prebuilt-layout`, api-version **2023-07-31**, POST `:analyze` → poll do
  `Operation-Location` até succeeded, timeout 60s, texto = `analyzeResult.content`).
  Fallback offline silencioso (NoOCRSilent) se não configurado.
- **Pipeline**: pypdf sem texto → OCR → extração IA normal. Chamada OCR fica registada em
  `ai_calls` (model `docintel-prebuilt-layout`). Se OCR também falhar → aviso e segue.
- **Teste**: `audits/ocr_test/` — fatura scan (imagem, 0 chars de texto) da Papelaria Central
  C2026-0331 → OCR + gpt-5-mini extraíram **Papelaria Central Lda / C2026-0331 / 357,93€** ✓.
- **Gerar scans de teste**: `python -m auditor.make_scan_test --dest audits/ocr_test/input/faturas`
  (desenha fatura com PIL e embute como imagem num PDF sem texto).
- **Custo**: F0 cobre a demo de sobra. Se um dia houver muitos scans → S0 (~$1/1000 páginas).

### OCR local via PaddleOCR (4 Set) — grátis, sem teto de páginas
- **`extractors/ocr_paddle.py`** (novo): OCR 100% local de scans — PP-OCRv5 mobile det+rec
  (Apache-2.0), sem custo e **sem teto de páginas** (vs F0 do Doc Intelligence = 20 págs/mês).
  Mesma interface `ocr_pdf(path) -> str`; páginas renderizadas com **pypdfium2** (BSD-3, scale 2.0);
  import lazy da lib (pesada); o scan nunca sai do PC.
- **Router** `extractors/ocr_router.py` (novo): `build_ocr_client()` escolhe por
  **`AUDITOR_OCR_ENGINE`** = `auto` (default: paddle se instalado, senão docintel, senão silencioso)
  | `paddle` | `docintel` | `none`. O pipeline imprime `🔤 OCR: <engine>`.
- **Empirismo 4 Set (py3.13, 4 cores, sem GPU)**: paddleocr 3.7.0 + paddlepaddle 3.3.1 OK no Windows.
  ⚠️ **mkldnn por omissão crasha o executor PIR** (`ConvertPirAttribute2RuntimeAttribute` em
  `onednn_instruction.cc`) com QUALQUER modelo → módulo força `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=0`.
  PP-OCRv6 medium (o preset de lang) = **~55s/página**; **PP-OCRv5 mobile = ~13s/página** com leitura
  perfeita no scan PT de teste (C2026-0331 → Papelaria Central Lda / 357,93€) — usado. Scale 1.5
  degrada ("Reterencia") — manter 2.0. Pipeline completo testado OK (OCR→extração→relatório).
- **Deps LOCAIS** (instaladas no Python do sistema — **NÃO** entraram em `requirements.txt` de prod):
  `pip install paddlepaddle paddleocr pypdfium2`; modelos em cache em `~/.paddlex` (1º init ~7s).
- **Fix .env**: o ficheiro estava em cp1252 (Notepad: "jurídica") → `load_dotenv` crasha em UTF-8.
  Transcodificado para UTF-8 + `config.py` tolerante (fallback cp1252 se UTF-8 falhar).
- Docintel continua disponível para confidencialidade UE/máxima qualidade: `AUDITOR_OCR_ENGINE=docintel`.

### UI v0 ligada à API local (4 Set) — frontend em C:\Users\joser\audit-ui (FORA do repo)
- **Frontend v0** (Next 16 + React 19 + Three/R3F, criado pelo José no Vercel v0) colocado em
  `C:\Users\joser\audit-ui` (pasta própria, fora do repo — sem interferir nos deploys Vercel/Railway).
- **web.py ganhou**: CORS para `http://localhost:3000` + `GET/POST /auditor/clients`
  (clientes = pastas em `backend/audits`; metadados em `client.json` por workspace; slug ASCII
  gerado do nome; `hasRun` = se db/audit.db existe).
- **Frontend ligado de verdade** (`lib/api.ts` + rewrite de experience/lab-overlay):
  - Boot/login estéticos (v0), mas o lab usa a API real: lista/cria clientes, upload
    (PDF→faturas, CSV→extratos), "Start audit" → `POST /auditor/run` (progresso de fases
    cosmético durante a chamada real), findings reais mapeados (confianca→severity,
    impacto_eur, evidencia, documentos, estado novo/confirmado ↔ OPEN/REVIEWED),
    emails = rascunhos reais de fornecedores (`/auditor/emails/generate`), "Draft email"
    do achado = mailto para o contacto do cliente (nunca envia).
  - API base: `NEXT_PUBLIC_AUDITOR_API` (default `http://localhost:8765`).
- **Testado E2E 4 Set via HTTP**: criar cliente → upload 3 faturas + extrato → run →
  7 achados reais (impacto 9.577,20 €) com schema certo; CORS preflight OK.
- **Correr**: terminal 1 `python -m uvicorn auditor.web:app --port 8765` (em backend/);
  terminal 2 `npm run dev` em audit-ui/ → http://localhost:3000.
- **Pendente**: deploy do UI (Vercel) implicaria expor o pipeline — por agora é local-first
  (consistente com o desenho "Nível 2": dados saem do PC só para a IA Azure UE).

### Alertas + pagamentos duplicados + faturas em falta (16 Ago, 3ª sessão)
- **Pagamentos duplicados** (regra nova): mesmo montante + mesma descrição/fornecedor + datas ≤30 dias
  → "pagamento_duplicado" (confiança alta). Pagamentos duplicados não são re-sinalizados como
  "sem fatura" (dedup via `_payment_ids`).
- **Faturas em falta** (regra nova): buracos ≤10 na sequência numérica por fornecedor+ano
  (ex.: 0113, 0114, 0116 → falta 0115). Confiança baixa (sinal, não acusação).
- **Alertas**: secção na UI com achados de confiança alta não confirmados; cada achado tem estado
  novo/confirmado/ignorado (botões na UI, endpoint POST /auditor/findings/{id}/state).
- **Telegram opcional**: `alerts.py` — notifica achados de alta confiança no fim do run SÓ com
  `AUDITOR_TELEGRAM_ENABLED=1` (reutiliza TELEGRAM_BOT_TOKEN_SOL/CHAT_ID_SOL ou vars próprias). Desligado por defeito.
- Demo: agora 6 compras (energia 0113+dup, 0114, 0116→buraco 0115; papelaria vs officemax) + 2 vendas
  + extrato com pagamento duplicado 1.284,30€. Resultado: 14 achados, impacto 11.995,63€.
