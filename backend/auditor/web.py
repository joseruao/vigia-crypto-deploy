"""Interface web local do AI Business Auditor.

Corre com:
    python -m uvicorn auditor.web:app --port 8765
e abre http://localhost:8765

Fluxo: upload de faturas de fornecedores + vendas (+ extratos) -> "Correr auditoria"
-> achados -> "Gerar emails" para fornecedores alternativos (rascunhos; envio só
com clique explícito e SMTP configurado).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline as pipeline_mod
from .alerts import notify_high_confidence, set_finding_state
from .audits.email_drafts import generate_email_drafts, send_email_draft
from .config import _BACKEND_ROOT
from .storage.db import AuditDB

app = FastAPI(title="AI Business Auditor", version="0.1.0")

# CORS para o UI local (Next dev em audit-ui: http://localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # URL de produção quando o UI for deployado (ex.: Vercel)
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_WORKSPACE = "cliente_demo"
# Workspaces vivem em backend/audits/ (é onde o CLI corre com caminhos relativos)
AUDITS_ROOT = _BACKEND_ROOT / "audits"

# Ficheiro temporário para uploads com drag-drop (sem JS de bibliotecas)
UPLOAD_DIR = _BACKEND_ROOT / "auditor" / "_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CATEGORY_DIRS = {"faturas": "faturas", "vendas": "vendas", "extratos": "extratos", "outros": "outros"}

PAGE = """<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8"><title>AI Business Auditor</title>
<style>
:root { --bg:#0f1115; --card:#171a21; --border:#262b36; --text:#e6e9ef; --muted:#8b93a3;
        --accent:#4f8cff; --good:#3ecf8e; --warn:#ffb020; --bad:#ff5d5d; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; padding:24px 5vw; }
h1 { font-size:20px; } h1 small { color:var(--muted); font-weight:400; font-size:13px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; margin-top:16px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }
.card h3 { font-size:14px; margin-bottom:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
label { font-size:12px; color:var(--muted); display:block; margin:8px 0 4px; }
input[type=text], input[type=number] { width:100%; padding:8px 10px; background:#0d0f13; border:1px solid var(--border);
  border-radius:8px; color:var(--text); font-size:14px; }
input[type=file] { width:100%; padding:14px; background:#0d0f13; border:1px dashed var(--border); border-radius:8px;
  color:var(--muted); font-size:13px; cursor:pointer; }
input[type=file]:hover { border-color:var(--accent); }
.btn { display:inline-block; padding:10px 18px; border:none; border-radius:8px; font-size:14px; font-weight:600;
  cursor:pointer; background:var(--accent); color:#fff; margin-top:12px; }
.btn:hover { opacity:.9; } .btn:disabled { opacity:.4; cursor:wait; }
.btn.ghost { background:transparent; border:1px solid var(--border); color:var(--text); }
.btn.good { background:var(--good); color:#06281a; }
.btn.warn { background:var(--warn); color:#2b1d00; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-top:14px; }
.stat { background:#0d0f13; border:1px solid var(--border); border-radius:10px; padding:12px; }
.stat .n { font-size:24px; font-weight:700; } .stat .l { font-size:12px; color:var(--muted); }
table { width:100%; border-collapse:collapse; margin-top:10px; }
th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:8px; border-bottom:1px solid var(--border); }
td { font-size:13px; padding:8px; border-bottom:1px solid var(--border); vertical-align:top; }
.badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }
.b-alta { background:rgba(255,93,93,.15); color:var(--bad); } .b-media { background:rgba(255,176,32,.15); color:var(--warn); }
.b-baixa { background:rgba(143,147,163,.15); color:var(--muted); }
.neg { color:var(--bad); font-weight:600; } .pos { color:var(--good); font-weight:600; }
.hidden { display:none; }
#log { background:#0d0f13; border:1px solid var(--border); border-radius:8px; padding:12px; font-family:Consolas,monospace;
  font-size:12px; max-height:220px; overflow:auto; margin-top:12px; white-space:pre-wrap; }
.email { border:1px solid var(--border); border-radius:8px; padding:12px; margin-top:10px; background:#0d0f13; }
.email .subj { font-weight:600; font-size:14px; } .email pre { font-family:inherit; white-space:pre-wrap; font-size:13px; margin-top:6px; color:#c9ced8; }
footer { margin-top:28px; color:var(--muted); font-size:12px; }
</style></head><body>
<h1>AI Business Auditor <small>— procura o dinheiro escondido da empresa</small></h1>

<div class="grid">
  <div class="card">
    <h3>1 · Upload de documentos</h3>
    <label>Empresa auditada (nome da pasta)</label>
    <input type="text" id="ws" value="cliente_demo">
    <label>Faturas de fornecedores (PDF)</label>
    <input type="file" id="faturas" multiple accept=".pdf,.csv,.xlsx,.txt">
    <label>Vendas (PDF)</label>
    <input type="file" id="vendas" multiple accept=".pdf,.csv,.xlsx,.txt">
    <label>Extratos bancários / pagamentos (CSV)</label>
    <input type="file" id="extratos" multiple accept=".csv,.xlsx,.txt">
    <button class="btn" id="btnUpload">⬆ Enviar ficheiros</button>
    <button class="btn good" id="btnRun">🔍 Correr auditoria</button>
  </div>

  <div class="card">
    <h3>2 · Resultados</h3>
    <div id="stats"><p style="color:var(--muted)">Corre a auditoria para veres os achados.</p></div>
    <div id="log" class="hidden"></div>
  </div>
</div>

<div class="card" style="margin-top:16px" id="alertasBox">
  <h3>3 · Alertas <small style="color:var(--muted)">(achados de confiança alta — marca como confirmado quando verificares)</small></h3>
  <div id="alertas"></div>
</div>

<div class="card" style="margin-top:16px">
  <h3>4 · Todos os achados</h3>
  <div id="findings"></div>
</div>

<div class="card" style="margin-top:16px">
  <h3>5 · Emails para fornecedores alternativos <small style="color:var(--muted)">(rascunhos — envio só com o teu clique)</small></h3>
  <button class="btn" id="btnEmails">✉ Gerar emails</button>
  <div id="emails"></div>
</div>

<footer>AI Business Auditor · dados na UE (Azure germanywestcentral) · regista tudo o que é enviado à IA</footer>

<script>
const $ = id => document.getElementById(id);
function el(tag, cls, html){ const e = document.createElement(tag); if(cls) e.className = cls; if(html) e.innerHTML = html; return e; }
function badge(c){ return `<span class="badge b-${c}">${c}</span>`; }
function money(v){ return v == null ? '—' : Number(v).toLocaleString('pt-PT',{style:'currency',currency:'EUR'}); }

async function api(url, opts={}){
  const r = await fetch(url, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || d.message || ('Erro ' + r.status));
  return d;
}

$('btnUpload').onclick = async () => {
  const ws = $('ws').value.trim() || 'cliente_demo';
  const fd = new FormData();
  for (const f of $('faturas').files) fd.append('faturas', f);
  for (const f of $('vendas').files) fd.append('vendas', f);
  for (const f of $('extratos').files) fd.append('extratos', f);
  if (![...fd.keys()].length) return alert('Escolhe ficheiros primeiro.');
  fd.append('workspace', ws);
  $('btnUpload').disabled = true;
  try {
    const d = await api('/auditor/upload', {method:'POST', body:fd});
    $('log').classList.remove('hidden');
    $('log').textContent = (d.saved||[]).join('\\n') || 'Nada enviado.';
  } catch(e){ alert(e.message); } finally { $('btnUpload').disabled = false; }
};

$('btnRun').onclick = async () => {
  const ws = $('ws').value.trim() || 'cliente_demo';
  $('btnRun').disabled = true; $('log').classList.remove('hidden'); $('log').textContent = 'A correr... (IA no Azure, demora alguns segundos)';
  try {
    const d = await api('/auditor/run?workspace=' + encodeURIComponent(ws), {method:'POST'});
    $('log').textContent = (d.log||[]).join('\\n');
    render(d);
  } catch(e){ $('log').textContent = 'Erro: ' + e.message; } finally { $('btnRun').disabled = false; }
};

$('btnEmails').onclick = async () => {
  const ws = $('ws').value.trim() || 'cliente_demo';
  try {
    const d = await api('/auditor/emails/generate?workspace=' + encodeURIComponent(ws), {method:'POST'});
    renderEmails(d.drafts || []);
  } catch(e){ alert(e.message); }
};

function stateBadge(s){ return `<span class="badge b-${s==='confirmado'?'media':'baixa'}">${s||'novo'}</span>`; }

function findingRow(x){
  const tr = el('tr');
  const acoes = `<button class="btn ghost" style="margin:2px;padding:4px 10px;font-size:12px" onclick="setState(${x.id},'confirmado')">✓ Confirmar</button>
                 <button class="btn ghost" style="margin:2px;padding:4px 10px;font-size:12px" onclick="setState(${x.id},'ignorado')">✗ Ignorar</button>`;
  tr.innerHTML = `<td>${badge(x.confianca)}<br>${stateBadge(x.estado)}</td><td>${x.tipo}</td>
    <td><strong>${x.titulo}</strong><br><span style="color:var(--muted);font-size:12px">${x.descricao||''}</span>
    <br><span style="color:var(--muted);font-size:11px">${x.evidencia||''} · ${x.documentos||''}</span></td>
    <td class="neg">${money(x.impacto_eur)}</td><td>${acoes}</td>`;
  return tr;
}

async function setState(id, state){
  const ws = $('ws').value.trim() || 'cliente_demo';
  try { await api(`/auditor/findings/${id}/state?workspace=${encodeURIComponent(ws)}&state=${state}`, {method:'POST'});
        render(await api('/auditor/state?workspace=' + encodeURIComponent(ws))); }
  catch(e){ alert(e.message); }
}

function render(d){
  const s = $('stats');
  s.innerHTML = '';
  const stats = [['Achados', d.stats.findings], ['Impacto', money(d.stats.impacto)], ['Faturas', d.stats.faturas],
                 ['Vendas', d.stats.vendas], ['Pagamentos', d.stats.pagamentos], ['Tokens IA', d.stats.tokens]];
  const wrap = el('div','cards');
  for (const [l,n] of stats){ const c = el('div','stat'); c.innerHTML = `<div class="n">${n}</div><div class="l">${l}</div>`; wrap.appendChild(c); }
  s.appendChild(wrap);

  // Alertas: confiança alta não confirmados
  const a = $('alertas'); a.innerHTML = '';
  const alertas = d.findings.filter(x => x.confianca === 'alta' && x.estado !== 'ignorado');
  if (!alertas.length){ a.innerHTML = '<p style="color:var(--muted)">Sem alertas de alta confiança pendentes.</p>'; }
  else {
    const t = el('table');
    t.innerHTML = '<tr><th>Confiança</th><th>Estado</th><th>Achado</th><th>Impacto</th><th></th></tr>';
    for (const x of alertas) t.appendChild(findingRow(x));
    a.appendChild(t);
  }

  const f = $('findings'); f.innerHTML = '';
  if (!d.findings.length){ f.innerHTML = '<p style="color:var(--muted)">Sem achados.</p>'; return; }
  const t = el('table');
  t.innerHTML = '<tr><th>Confiança</th><th>Tipo</th><th>Achado</th><th>Impacto</th><th>Ações</th></tr>';
  for (const x of d.findings) t.appendChild(findingRow(x));
  f.appendChild(t);
  renderEmails(d.emails || []);
}

function renderEmails(emails){
  const box = $('emails'); box.innerHTML = '';
  if (!emails.length){ box.innerHTML = '<p style="color:var(--muted)">Sem rascunhos — corre a auditoria e gera emails.</p>'; return; }
  for (const e of emails){
    const div = el('div','email');
    div.innerHTML = `<div class="subj">${e.subject} <span class="badge b-${e.status==='enviado'?'alta':'media'}">${e.status}</span></div>
      <div style="font-size:12px;color:var(--muted)">Para: ${e.supplier_email || '<i>sem email — preenche manualmente</i>'} · ${e.supplier}</div>
      <pre></pre><button class="btn ghost">✉ Enviar</button>`;
    div.querySelector('pre').textContent = e.body;
    const btn = div.querySelector('button');
    btn.onclick = async () => {
      if (!confirm('Enviar este email REAL para ' + e.supplier_email + '?')) return;
      btn.disabled = true;
      try { const r = await api('/auditor/emails/send/' + e.id, {method:'POST'}); alert(r.message); renderEmails(await refreshEmails()); }
      catch(err){ alert(err.message); btn.disabled = false; }
    };
    box.appendChild(div);
  }
}
async function refreshEmails(){ const ws = $('ws').value.trim() || 'cliente_demo'; const d = await api('/auditor/state?workspace=' + encodeURIComponent(ws)); return d.emails; }
</script></body></html>"""


def _workspace_path(name: str) -> Path:
    from .workspace import ensure_workspace

    ws = (AUDITS_ROOT / name).resolve()
    ensure_workspace(ws)
    return ws


CLIENT_META = "client.json"


def _slugify(name: str) -> str:
    """Nome de cliente -> pasta de workspace (ASCII, sem acentos)."""
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return slug or f"cliente-{datetime.now(timezone.utc).timestamp():.0f}"


def _client_record(ws_dir: Path) -> dict[str, Any]:
    """Lê client.json (metadados do cliente) + se já correu uma auditoria."""
    meta: dict[str, Any] = {}
    meta_file = ws_dir / CLIENT_META
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:  # client.json corrompido — segue com defaults
            meta = {}
    return {
        "id": ws_dir.name,
        "companyName": meta.get("companyName") or ws_dir.name,
        "contactName": meta.get("contactName", ""),
        "email": meta.get("email", ""),
        "phone": meta.get("phone", ""),
        "industry": meta.get("industry", ""),
        "notes": meta.get("notes", ""),
        "hasRun": (ws_dir / "db" / "audit.db").exists(),
    }


@app.get("/auditor/clients")
def clients_list() -> JSONResponse:
    """Clientes = pastas em AUDITS_ROOT com client.json ou dados (input/db)."""
    out: list[dict[str, Any]] = []
    if AUDITS_ROOT.exists():
        for d in sorted(AUDITS_ROOT.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            has_meta = (d / CLIENT_META).exists()
            has_data = (d / "input").is_dir() or (d / "db" / "audit.db").exists()
            if has_meta or has_data:
                out.append(_client_record(d))
    return {"clients": out}


@app.post("/auditor/clients")
def clients_create(payload: dict[str, Any]) -> JSONResponse:
    """Cria um cliente: pasta de workspace + client.json com os metadados."""
    company = str(payload.get("companyName") or "").strip()
    if not company:
        raise HTTPException(status_code=422, detail="companyName é obrigatório")
    ws = _workspace_path(_slugify(company))
    meta = {
        "companyName": company,
        "contactName": str(payload.get("contactName") or "").strip(),
        "email": str(payload.get("email") or "").strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "industry": str(payload.get("industry") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (ws / CLIENT_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return _client_record(ws)


def _db_for(workspace: Path) -> AuditDB:
    return AuditDB(workspace / "db" / "audit.db")


def _state(workspace: Path) -> dict[str, Any]:
    db = _db_for(workspace)
    try:
        findings = [dict(r) for r in db.all_findings()]
        invoices = [dict(r) for r in db.all_invoices()]
        payments = [dict(r) for r in db.all_payments()]
        drafts = [dict(r) for r in db.all_email_drafts()]
        tokens = db.total_ai_tokens()
        impacto = sum(f.get("impacto_eur") or 0 for f in findings)
        return {
            "findings": findings,
            "invoices": invoices,
            "payments": payments,
            "emails": drafts,
            "stats": {
                "findings": len(findings),
                "faturas": sum(1 for i in invoices if i.get("type") == "compra"),
                "vendas": sum(1 for i in invoices if i.get("type") == "venda"),
                "pagamentos": len(payments),
                "impacto": impacto,
                "tokens": tokens,
            },
        }
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


@app.get("/auditor", response_class=HTMLResponse)
def auditor_page() -> HTMLResponse:
    return RedirectResponse("/")


@app.post("/auditor/upload")
async def upload(
    faturas: list[UploadFile] = File(default=[]),
    vendas: list[UploadFile] = File(default=[]),
    extratos: list[UploadFile] = File(default=[]),
    workspace: str = Form(DEFAULT_WORKSPACE),
) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    saved: list[str] = []
    for files, folder in ((faturas, "faturas"), (vendas, "vendas"), (extratos, "extratos")):
        target = ws / "input" / folder
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            content = await f.read()
            if not content:
                continue
            dest = target / f.filename
            dest.write_bytes(content)
            saved.append(f"✓ {folder}/{f.filename} ({len(content)//1024} KB)")
    return {"saved": saved}


@app.post("/auditor/run")
def run(workspace: str = DEFAULT_WORKSPACE) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    try:
        report = pipeline_mod.run_audit(ws)
    except Exception as exc:  # noqa: BLE001 - expõe o erro na UI
        raise HTTPException(status_code=500, detail=f"Falha na auditoria: {exc}") from exc
    state = _state(ws)
    state["report"] = str(report)
    alert_msg = notify_high_confidence(state["findings"])
    state["log"] = [f"✅ Auditoria concluída — relatório: {report}", alert_msg]
    return state


@app.get("/auditor/state")
def state(workspace: str = DEFAULT_WORKSPACE) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    return _state(ws)


@app.post("/auditor/findings/{finding_id}/state")
def finding_state(finding_id: int, state: str, workspace: str = DEFAULT_WORKSPACE) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    db = _db_for(ws)
    try:
        ok = set_finding_state(db, finding_id, state)
    finally:
        db.close()
    if not ok:
        raise HTTPException(status_code=400, detail="Estado inválido (novo|confirmado|ignorado) ou achado não existe.")
    return {"message": f"Achado marcado como {state}."}


@app.post("/auditor/emails/generate")
def emails_generate(workspace: str = DEFAULT_WORKSPACE) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    db = _db_for(ws)
    try:
        rows = db.conn.execute("SELECT id FROM audit_runs ORDER BY id DESC LIMIT 1").fetchall()
        run_id = int(rows[0]["id"]) if rows else 0
        drafts = generate_email_drafts(db, run_id)
    finally:
        db.close()
    return {"drafts": drafts, "count": len(drafts)}


@app.post("/auditor/emails/send/{draft_id}")
def emails_send(draft_id: int, workspace: str = DEFAULT_WORKSPACE) -> JSONResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    db = _db_for(ws)
    try:
        ok, message = send_email_draft(draft_id, db)
    finally:
        db.close()
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


@app.get("/auditor/report")
def report_html(workspace: str = DEFAULT_WORKSPACE) -> HTMLResponse:
    ws = _workspace_path(workspace.strip() or DEFAULT_WORKSPACE)
    report = ws / "reports" / "report.html"
    if not report.exists():
        raise HTTPException(status_code=404, detail="Corre a auditoria primeiro.")
    return HTMLResponse(report.read_text(encoding="utf-8"))
