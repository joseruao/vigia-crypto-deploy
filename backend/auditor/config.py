from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv é dep padrão do projeto
    load_dotenv = None

# Backend root = 2 níveis acima de auditor/config.py (backend/auditor/config.py -> backend)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _ensure_env() -> None:
    """Carrega backend/.env se existir (sem sobrepor variáveis já definidas).

    O Notepad/outros editores Windows gravam cp1252 (ex.: "jurídica") e o
    dotenv lê UTF-8 — tolerância: se UTF-8 falhar, tenta cp1252.
    """
    if load_dotenv is None:
        return
    env_file = _BACKEND_ROOT / ".env"
    if not env_file.exists():
        return
    try:
        load_dotenv(env_file, override=False)
    except UnicodeDecodeError:
        load_dotenv(env_file, override=False, encoding="cp1252")


@dataclass(frozen=True)
class AIConfig:
    provider: str = "none"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"
    # Azure AI Document Intelligence (OCR de scans) — opcional
    docintel_endpoint: str = ""
    docintel_key: str = ""
    # Engine de OCR para scans: auto | paddle (local, grátis) | docintel (Azure) | none
    ocr_engine: str = "auto"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"


def load_ai_config() -> AIConfig:
    _ensure_env()
    return AIConfig(
        provider=os.getenv("AUDITOR_AI_PROVIDER", "none").strip().lower(),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        docintel_endpoint=os.getenv("AZURE_DOCINTEL_ENDPOINT", ""),
        docintel_key=os.getenv("AZURE_DOCINTEL_KEY", ""),
        ocr_engine=os.getenv("AUDITOR_OCR_ENGINE", "auto").strip().lower(),
        mistral_api_key=os.getenv("MISTRAL_API_KEY", ""),
        mistral_model=os.getenv("MISTRAL_MODEL", "mistral-large-latest"),
    )
