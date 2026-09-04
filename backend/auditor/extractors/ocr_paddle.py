"""OCR local de PDFs escaneados via PaddleOCR (PP-OCR, Apache-2.0).

Alternativa grátis e sem teto de páginas ao Azure Document Intelligence
(F0 = 20 páginas/mês) para o passo de OCR do pipeline: os modelos PP-OCRv5 mobile
correm em CPU, o scan nunca sai do PC, e a licença Apache-2.0 permite incorporar
e revender sem obrigações (ao contrário do AGPL).

Modo 'auto' do router usa-o quando o pacote está instalado; seleção explícita
com AUDITOR_OCR_ENGINE=paddle (ver config.py). A lib (paddleocr + paddlepaddle)
é pesada e o primeiro arranque descarrega modelos — o import é lazy e só acontece
na primeira chamada real.

Testado a 2026-09-04 (paddleocr 3.7.0, paddlepaddle 3.3.1, py3.13):
  - ~13s/página A4 (render scale 2.0, CPU 4 cores, mkldnn off)
  - leitura perfeita no scan PT (Papelaria Central C2026-0331, 357,93€)
  - ⚠️ mkldnn por omissão crasha o executor PIR — desligado via env (ver _get_engine)
"""
from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from typing import Any, Callable

from ..config import AIConfig, load_ai_config

LogCall = Callable[[dict[str, Any]], None]

# Render das páginas PDF -> imagem (pypdfium2/PDFium, BSD-3 — sem AGPL como o PyMuPDF).
# 2.0 ≈ 192 dpi num A4; fiel a scans de 150 dpi e folga para PP-OCR.
PDF_RENDER_SCALE = 2.0


def is_available() -> bool:
    """True se paddleocr estiver instalado (find_spec é barato; import não é)."""
    return importlib.util.find_spec("paddleocr") is not None


class PaddleOCRLocal:
    """OCR de PDFs escaneados, 100% local. Mesma interface que o DocumentIntelligenceOCR."""

    engine_name = "paddle-ppocr"

    def __init__(self, config: AIConfig | None = None, log_call: LogCall | None = None) -> None:
        self.cfg = config or load_ai_config()
        self.log_call = log_call
        self._engine: Any | None = None  # None = ainda não criado; False = indisponível
        self._warned = False

    # -- interface pública -------------------------------------------------

    def ocr_pdf(self, path: Path) -> str:
        """Devolve o texto do PDF (linhas por página) ou "" se falhar/ilegível."""
        engine = self._get_engine()
        if engine is None:
            return ""
        try:
            import pypdfium2 as pdfium
        except ImportError:
            self._log_error(path, "pypdfium2 em falta", "pip install pypdfium2")
            return ""

        parts: list[str] = []
        t0 = time.monotonic()
        try:
            with pdfium.PdfDocument(str(path)) as doc:
                for i in range(len(doc)):
                    page = doc[i]
                    try:
                        # PdfBitmap desta versão do pypdfium2 não tem context manager
                        bitmap = page.render(scale=PDF_RENDER_SCALE)
                        try:
                            text = self._ocr_image(bitmap.to_pil())
                        finally:
                            close = getattr(bitmap, "close", None)
                            if close is not None:
                                close()
                    finally:
                        page.close()
                    if text:
                        parts.append(text)
        except Exception as exc:  # PDF corrompido / render falhou — nunca rebenta o run
            self._log_error(path, "render", str(exc)[:200])
            return ""
        content = "\n".join(parts).strip()
        if self.log_call is not None:
            self.log_call(
                {
                    "model": self.engine_name,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                    "reasoning_tokens": None,
                    "pages": len(parts),
                    "seconds": round(time.monotonic() - t0, 1),
                }
            )
        return content

    # -- internals ----------------------------------------------------------

    def _get_engine(self) -> Any | None:
        """Cria o PaddleOCR uma vez (import + modelos PP-OCRv5 mobile). False se indisponível."""
        if self._engine is not None:
            return self._engine if self._engine is not False else None
        if not is_available():
            self._warn_missing()
            self._engine = False
            return None
        # ⚠️ paddlepaddle 3.3.1: mkldnn por omissão rebenta no executor PIR
        # ("ConvertPirAttribute2RuntimeAttribute ... onednn_instruction.cc") mesmo em CPU
        # e com qualquer modelo (testado com PP-OCRv6 medium e v5 mobile).
        # Correto sem mkldnn (mais lento: ~13s/página A4 neste PC); env =1 volta a ligar
        # se o bug for corrigido.
        os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
        t0 = time.monotonic()
        try:
            from paddleocr import PaddleOCR

            # PP-OCRv5 mobile (det+rec): mais rápido que o v6 medium (~13s vs ~55s por
            # página A4 sem mkldnn) e com leitura perfeita no scan PT de teste.
            # NOTA: model_name explícito anula `lang` — não passar lang com nomes.
            self._engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
            )
        except Exception as exc:
            self._warn_missing(f"falha a inicializar: {str(exc)[:200]}")
            self._engine = False
            return None
        print(f"   ... PaddleOCR inicializado em {time.monotonic() - t0:.1f}s")
        return self._engine

    def _ocr_image(self, image: Any) -> str:
        """Uma página PIL -> linhas de texto reconhecidas ("" se vazio)."""
        engine = self._get_engine()
        if engine is None:
            return ""
        try:
            import numpy as np

            arr = np.asarray(image)[:, :, ::-1].copy()  # RGB -> BGR (convenção paddle)
            lines = self._lines_from(engine.predict(arr))
        except Exception as exc:
            if not self._warned:
                self._warned = True
                print(f"   ⚠️  PaddleOCR página falhou: {str(exc)[:200]}")
            return ""
        return "\n".join(lines)

    @staticmethod
    def _lines_from(results: Any) -> list[str]:
        """Extrai texto dos resultados, tolerante às formas 3.x.

        No paddleocr 3.7 o OCRResult é dict-like: rec_texts está em res["rec_texts"]
        (o atributo `.text` existe mas devolve [] — não usar).
        """
        lines: list[str] = []
        for res in results or []:
            if res is None:
                continue
            texts: list[Any] | None = None
            try:  # dict-like: rec_texts via key
                texts = list(res["rec_texts"] or [])
            except (TypeError, KeyError, IndexError):
                texts = None
            if texts is None and hasattr(res, "rec_texts"):  # outras versões: atributo
                texts = list(res.rec_texts or [])
            if texts is None and hasattr(res, "text"):  # tuplas (score, texto)
                texts = []
                for item in res.text or []:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        texts.append(item[1])
                    else:
                        texts.append(item)
            for t in texts or []:
                if isinstance(t, str) and t.strip():
                    lines.append(t.strip())
        return lines

    def _warn_missing(self, why: str = "pacote não instalado") -> None:
        if self._warned:
            return
        self._warned = True
        print(
            f"   ⚠️  PaddleOCR indisponível ({why}). "
            "Fallback: define AUDITOR_OCR_ENGINE=docintel ou instala com "
            "`pip install paddlepaddle paddleocr pypdfium2`."
        )

    def _log_error(self, path: Path, where: str, detail: str) -> None:
        print(f"   ⚠️  OCR {path.name}: {where} {detail}")
        if self.log_call is not None:
            self.log_call({"model": self.engine_name, "error": f"{where} {detail[:150]}"})
