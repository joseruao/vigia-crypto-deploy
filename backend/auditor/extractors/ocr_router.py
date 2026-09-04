"""Seleção do engine de OCR para PDFs escaneados.

AUDITOR_OCR_ENGINE (config.py):
  - auto     (default) — PaddleOCR local se instalado; senão Document Intelligence; senão silencioso
  - paddle   — força OCR local (PaddleOCR, grátis, sem teto); cai para docintel/silencioso se em falta
  - docintel — força Azure Document Intelligence (F0: 20 páginas/mês)
  - none     — desliga OCR
"""
from __future__ import annotations

from typing import Any, Callable

from ..config import AIConfig, load_ai_config
from .ocr_docintel import DocumentIntelligenceOCR, NoOCRSilent
from .ocr_paddle import PaddleOCRLocal, is_available

LogCall = Callable[[dict[str, Any]], None]

OCRClient = DocumentIntelligenceOCR | PaddleOCRLocal | NoOCRSilent


def build_ocr_client(
    config: AIConfig | None = None, log_call: LogCall | None = None
) -> OCRClient:
    """Devolve o cliente OCR escolhido por AUDITOR_OCR_ENGINE (fallback silencioso nunca inventa)."""
    cfg = config or load_ai_config()
    engine = (cfg.ocr_engine or "auto").strip().lower()
    want_paddle = engine in ("auto", "paddle")
    want_docintel = engine in ("auto", "docintel")

    if want_paddle and is_available():
        return PaddleOCRLocal(cfg, log_call=log_call)
    if want_docintel and cfg.docintel_endpoint and cfg.docintel_key:
        if engine == "paddle":
            print("   ⚠️  AUDITOR_OCR_ENGINE=paddle mas PaddleOCR não instalado — a usar Document Intelligence")
        return DocumentIntelligenceOCR(cfg, log_call=log_call)
    if engine == "paddle" and not is_available():
        print(
            "   ⚠️  PaddleOCR não instalado (pip install paddlepaddle paddleocr pypdfium2) "
            "e sem Document Intelligence configurado — OCR desligado"
        )
    return NoOCRSilent()
