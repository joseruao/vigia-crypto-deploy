from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import requests

from ..config import AIConfig

# API v3.1 (estável). A v3.2 (2024-11-30) também existe; 2023-07-31 é a mais comprovada.
DOCINTEL_API_VERSION = "2023-07-31"
MODEL = "prebuilt-layout"
# Poll do Operation-Location: Document Intelligence demora alguns segundos por página.
OCR_POLL_INTERVAL_S = 1.5
OCR_TIMEOUT_S = 60

LogCall = Callable[[dict[str, Any]], None]


class NoOCRSilent:
    """Fallback offline: devolve texto vazio (nunca inventa)."""

    engine_name = "none"

    def ocr_pdf(self, path: Path) -> str:
        return ""


class DocumentIntelligenceOCR:
    """OCR de PDFs escaneados via Azure AI Document Intelligence (região UE).

    Seleção do engine (auto/paddle/docintel) em ocr_router.build_ocr_client().
    """

    engine_name = "docintel-prebuilt-layout"

    def __init__(self, config: AIConfig, log_call: LogCall | None = None) -> None:
        self.cfg = config
        self.log_call = log_call
        self._analyze_url = (
            f"{config.docintel_endpoint.rstrip('/')}/formrecognizer/documentModels/"
            f"{MODEL}:analyze?api-version={DOCINTEL_API_VERSION}"
        )

    def ocr_pdf(self, path: Path) -> str:
        """Devolve o texto do PDF (layout) ou "" se falhar/ilegível."""
        with path.open("rb") as fh:
            resp = requests.post(
                self._analyze_url,
                headers={
                    "Ocp-Apim-Subscription-Key": self.cfg.docintel_key,
                    "Content-Type": "application/pdf",
                },
                data=fh,
                timeout=OCR_TIMEOUT_S,
            )
        if resp.status_code != 202:
            self._log_error(path, f"POST {resp.status_code}", resp.text[:200])
            return ""
        op_location = resp.headers.get("Operation-Location", "")
        if not op_location:
            self._log_error(path, "sem Operation-Location", "")
            return ""

        deadline = time.monotonic() + OCR_TIMEOUT_S
        while time.monotonic() < deadline:
            time.sleep(OCR_POLL_INTERVAL_S)
            status = requests.get(
                op_location,
                headers={"Ocp-Apim-Subscription-Key": self.cfg.docintel_key},
                timeout=OCR_TIMEOUT_S,
            )
            if status.status_code != 200:
                self._log_error(path, f"poll {status.status_code}", status.text[:200])
                return ""
            body = status.json()
            state = body.get("status")
            if state == "succeeded":
                content = self._extract_content(body)
                if self.log_call is not None:
                    pages = len(body.get("analyzeResult", {}).get("pages", []))
                    self.log_call(
                        {
                            "model": f"docintel-{MODEL}",
                            "prompt_tokens": None,
                            "completion_tokens": None,
                            "total_tokens": None,
                            "reasoning_tokens": None,
                            "pages": pages,
                        }
                    )
                return content
            if state == "failed":
                err = body.get("error", {})
                self._log_error(path, f"failed: {err.get('code', '?')}", str(err.get("message", ""))[:200])
                return ""
        self._log_error(path, "timeout", "Document Intelligence não terminou")
        return ""

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        """`content` do analyzeResult já inclui linhas/parágrafos com layout."""
        analyze = body.get("analyzeResult", {})
        return (analyze.get("content") or "").strip()

    def _log_error(self, path: Path, where: str, detail: str) -> None:
        print(f"   ⚠️  OCR {path.name}: {where} {detail}")
        if self.log_call is not None:
            self.log_call(
                {
                    "model": f"docintel-{MODEL}",
                    "error": f"{where} {detail[:150]}",
                }
            )
