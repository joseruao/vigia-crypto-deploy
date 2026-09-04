from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .ai.providers import MAX_CHARS_PER_DOC, AIClient, build_ai_client
from .audits.rules import (
    find_duplicate_invoices,
    find_duplicate_payments,
    find_missing_invoice_sequences,
    reconcile_payments,
)
from .audits.suppliers import find_supplier_opportunities, find_margin_issues
from .extractors.pdf_text import extract_pdf_text
from .extractors.ocr_router import OCRClient, build_ocr_client
from .ingestion.scanner import DocumentCandidate, scan_input
from .normalizers.payments_csv import parse_payments_csv
from .reports.html_report import write_report
from .storage.db import AuditDB

EXTRACTION_PROMPT = """Extrai os dados desta fatura/recibo/documento financeiro para JSON com esta estrutura exata:

{{
  "seller": "entidade que EMITE a fatura — a que aparece no topo/cabeçalho do documento, com NIF próprio (ou null)",
  "seller_nif": "NIF da entidade emissora (ou null)",
  "seller_email": "email da entidade emissora se visível no documento (ou null)",
  "buyer": "comprador — normalmente identificado como 'Cliente:' no corpo da fatura (ou null)",
  "invoice_number": "número da fatura (ou null)",
  "date": "data da fatura em formato AAAA-MM-DD (ou null)",
  "due_date": "data de vencimento em formato AAAA-MM-DD (ou null)",
  "total": 1234.56,
  "vat": 123.45,
  "currency": "EUR",
  "payment_reference": "referência/IBAN/entidade de pagamento se visível (ou null)",
  "lines": [
    {{"description": "descrição do artigo/serviço", "qty": 1, "unit_price": 10.50, "total": 10.50}}
  ]
}}

IMPORTANTE: o campo "Cliente:" no corpo da fatura é o BUYER, nunca o seller.
Valores numéricos como números (não strings). Total = valor final da fatura incluindo IVA.
Se o documento não for uma fatura/recibo, devolve {{"not_invoice": true}}.

DOCUMENTO:
"""


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _is_csv(candidate: DocumentCandidate) -> bool:
    return candidate.suffix == ".csv"


def _extract_invoice(
    candidate: DocumentCandidate, client: AIClient, ocr: OCRClient, db: AuditDB, run_id: int
) -> dict[str, Any] | None:
    text, truncated = extract_pdf_text(candidate.path, MAX_CHARS_PER_DOC)
    if not text.strip():
        # PDF escaneado (sem camada de texto) — OCR via Document Intelligence
        text = ocr.ocr_pdf(candidate.path)
        if not text.strip():
            return None
    data = client.extract_json(EXTRACTION_PROMPT + text)
    data = dict(data)
    data["raw_json"] = json.dumps(data, ensure_ascii=False)[:2000]
    data["_truncated"] = truncated
    return data


def run_audit(workspace: Path, *, limit: int | None = None, skip_ai: bool = False) -> Path:
    """Executa o pipeline completo: scan → extração → estruturação → regras → relatório."""
    workspace = workspace.resolve()
    db_path = workspace / "db" / "audit.db"
    db = AuditDB(db_path)
    try:
        db.reset_processing_data()
        run_id = db.start_run()
        candidates = scan_input(workspace)
        pdfs = [c for c in candidates if c.suffix == ".pdf"]
        if limit is not None:
            pdfs = pdfs[:limit]

        if skip_ai:
            client: AIClient | None = None
        else:
            client = build_ai_client(log_call=lambda info: db.log_ai_call(run_id, None, info))
            if client.__class__.__name__ == "NoAIClient":
                print("⚠️  Sem AI configurada (AUDITOR_AI_PROVIDER não é azure_openai). A correr só com regras locais.")
                client = None
        ocr = build_ocr_client(log_call=lambda info: db.log_ai_call(run_id, None, info))
        print(f"🔤 OCR: {ocr.engine_name}")

        print(f"📄 {len(pdfs)} PDF(s) encontrado(s) em {workspace.name}")

        ai_calls = 0
        for cand in pdfs:
            doc_id = db.insert_document(
                cand.path.name, cand.category, _hash_file(cand.path), 0, False
            )
            if client is None:
                print(f"   - {cand.path.name}: extração IA desativada")
                continue
            extracted = _extract_invoice(cand, client, ocr, db, run_id)
            if extracted is None:
                print(f"   - {cand.path.name}: sem texto (scan?) — pypdf e OCR sem resultado")
                continue
            if extracted.get("not_invoice"):
                print(f"   - {cand.path.name}: não parece fatura")
                continue
            if "error" in extracted:
                print(f"   - {cand.path.name}: erro IA ({extracted.get('detail', extracted.get('error'))})")
                continue
            db.conn.execute(
                "UPDATE documents SET extracted_chars = ? WHERE id = ?",
                (len(str(extracted.get("raw_json"))), doc_id),
            )
            inv_type = "venda" if cand.category == "vendas" else "compra"
            # Compra: a contraparte é quem emite (seller). Venda: a contraparte é o cliente (buyer).
            if inv_type == "compra":
                extracted["supplier"] = extracted.get("seller")
                extracted["supplier_nif"] = extracted.get("seller_nif")
                extracted["supplier_email"] = extracted.get("seller_email")
            else:
                extracted["supplier"] = extracted.get("buyer")
                extracted["supplier_nif"] = None
                extracted["supplier_email"] = None
            db.insert_invoice(doc_id, extracted, type_=inv_type)
            ai_calls += 1
            print(f"   ✓ {cand.path.name} ({inv_type}): {extracted.get('supplier') or '?'} — {extracted.get('invoice_number') or 'nº ?'} — {extracted.get('total')}€")

        # Extratos bancários (CSV)
        payments_docs = 0
        for cand in candidates:
            if not _is_csv(cand):
                continue
            payments = parse_payments_csv(cand.path)
            if not payments:
                print(f"   - {cand.path.name}: CSV sem colunas de pagamento reconhecidas")
                continue
            doc_id = db.insert_document(cand.path.name, cand.category, _hash_file(cand.path), 0, False)
            for p in payments:
                db.insert_payment(doc_id, p)
            payments_docs += len(payments)
            print(f"   ✓ {cand.path.name}: {len(payments)} pagamentos importados")

        # Regras de auditoria
        db.clear_findings(run_id)
        n1 = len(find_duplicate_invoices(db, run_id))
        dup_payments = find_duplicate_payments(db, run_id)
        n2 = len(dup_payments)
        dup_payment_ids = {pid for f in dup_payments for pid in f.get("_payment_ids", [])}
        n3 = len(reconcile_payments(db, run_id, skip_payment_ids=dup_payment_ids))
        n4 = len(find_supplier_opportunities(db, run_id))
        n5 = len(find_margin_issues(db, run_id))
        n6 = len(find_missing_invoice_sequences(db, run_id))
        print(f"\n🔎 Achados: {n1} dup.faturas + {n2} dup.pagamentos + {n3} pag/fat + {n4} fornecedores + {n5} margens + {n6} em-falta")

        db.finish_run(run_id, len(pdfs), ai_calls)
        report_path = write_report(db, workspace, run_id)
        print(f"📊 Relatório: {report_path}")
        return report_path
    finally:
        db.close()
