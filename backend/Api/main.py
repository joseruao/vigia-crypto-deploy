# backend/Api/main.py
from __future__ import annotations
import os
import logging
import sys
import re
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
    for _env_path in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if _env_path.exists():
            load_dotenv(_env_path, override=True)
            break
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vigia")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
ALLOWED_ORIGINS = {
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://joseruao.com",
    "https://www.joseruao.com",
    "https://joseruao.vercel.app",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Vigia API a iniciar")
    # Agendador dos workers (substitui os crons do Railway) — ver Api/services/scheduler.py
    try:
        from Api.services.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
    except Exception as e:  # nunca impedir o arranque da API por causa do agendador
        stop_scheduler = None
        log.warning("Agendador de crons indisponivel: %s", e)
    yield
    if stop_scheduler:
        stop_scheduler()
    log.info("Vigia API a encerrar")


app = FastAPI(title="Vigia API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    StarletteCORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|https://joseruao\.com|https://www\.joseruao\.com|http://localhost:.*|http://127\.0\.0\.1:.*",
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_buffering_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Accel-Buffering", "no")
    resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


from Api.routes.alerts import (
    router as alerts_router,
    _answer_top100_buy_watchlist as answer_top100_buy_watchlist,
    _is_top100_buy_question as is_top100_buy_question,
    _is_buy_watchlist_question as _is_opportunity_question,
)
app.include_router(alerts_router, prefix="")

try:
    from Api.routes.coin_analysis import router as coin_analysis_router
    app.include_router(coin_analysis_router, prefix="")
except ImportError as e:
    log.warning("Coin analysis router nao disponivel: %s", e)

try:
    from Api.routes.football import router as football_router
    app.include_router(football_router, prefix="")
except ImportError as e:
    log.warning("Football router nao disponivel: %s", e)

try:
    from Api.routes.bet import router as bet_router
    app.include_router(bet_router, prefix="")
except ImportError as e:
    log.warning("Bet router nao disponivel: %s", e)

try:
    from Api.routes.pme import router as pme_router
    app.include_router(pme_router, prefix="")
except Exception as e:
    log.warning("PME router nao disponivel: %s", e)


@app.get("/")
@app.head("/")
def root():
    return {"ok": True, "service": "vigia-backend"}


@app.get("/ping")
@app.head("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
@app.head("/health")
def health():
    return {"ok": True, "service": "vigia-backend", "status": "healthy"}


@app.get("/__version")
def version():
    return {"name": "vigia-backend", "version": "0.2.0"}


# ---------------------------------------------------------------------------
# Administração dos crons (substituem os serviços cron do Railway)
# ---------------------------------------------------------------------------
def _check_admin_code(request: Request) -> None:
    """Gate simples por header — mesmo código do Devil's Advocate."""
    expected = os.environ.get("DEVILS_ADVOCATE_ACCESS_CODE", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="código de acesso não configurado")
    if request.headers.get("x-access-code", "") != expected:
        raise HTTPException(status_code=401, detail="código de acesso inválido")


@app.get("/admin/cron-status")
def admin_cron_status(request: Request):
    _check_admin_code(request)
    from Api.services.scheduler import status
    return status()


@app.post("/admin/run-worker")
def admin_run_worker(request: Request, name: str):
    """Dispara um worker à mão (holdings | top100 | arkham) sem esperar pela hora."""
    _check_admin_code(request)
    from Api.services.scheduler import JOBS, run_worker
    if name not in JOBS:
        raise HTTPException(status_code=400, detail=f"worker desconhecido: {name} (use {', '.join(JOBS)})")
    return run_worker(name)


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------
from datetime import date as _date
from Api.services.chat_helpers import (
    ChatRequest,
    LAST_COIN_ANALYSIS,
    _is_trade_followup,
    _is_sell_followup,
    _is_entry_price_followup,
    _is_analysis_detail_followup,
    _is_onboarding_question,
    _is_top100_recommendation_followup,
    _should_use_coin_analysis,
    _normalize_coin_symbol,
    _format_trade_followup,
    _format_text_sell_followup,
    _format_text_analysis_detail_followup,
    _format_coin_analysis,
    _format_onboarding,
    _format_comparison_followup,
    _format_top100_recommendation,
    _portfolio_context_line,
    _extract_entry_price,
    _fmt_price,
)
from Api.services.tools import TOOL_SCHEMAS, execute_tool, parse_tool_arguments

_KNOWN_COIN_NAMES = {
    "BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL", "CARDANO": "ADA",
    "POLKADOT": "DOT", "POLYGON": "MATIC", "AVALANCHE": "AVAX", "CHAINLINK": "LINK",
    "LITECOIN": "LTC", "BITCOIN CASH": "BCH", "STELLAR": "XLM", "ETHEREUM CLASSIC": "ETC",
    "TRON": "TRX", "MONERO": "XMR", "COSMOS": "ATOM", "ALGORAND": "ALGO",
    "VECHAIN": "VET", "INTERNET COMPUTER": "ICP", "FILECOIN": "FIL",
    "APTOS": "APT", "ARBITRUM": "ARB", "OPTIMISM": "OP", "INJECTIVE": "INJ",
    "CELESTIA": "TIA", "DOGWIFHAT": "WIF",
}
_KNOWN_SYMBOLS = [
    "BTC", "ETH", "SOL", "ADA", "DOT", "MATIC", "AVAX", "LINK", "LTC", "BCH",
    "XLM", "ETC", "TRX", "XMR", "EOS", "ATOM", "ALGO", "VET", "ICP", "FIL",
    "NEAR", "APT", "ARB", "OP", "SUI", "INJ", "SEI", "TIA", "WIF", "BONK",
    "HYPE", "PEPE", "SHIB", "FLOKI", "WLD", "UNI", "AAVE", "ONDO", "FET",
    "BNB", "XRP", "DOGE", "USDT", "USDC",
]
_COIN_COMMON_WORDS = {
    "ANALISA", "ME", "A", "MOEDA", "GRAFICAMENTE", "GRAFICO", "GRAFICA",
    "TECNICA", "ANALISE", "CRIPTOMOEDA", "COIN", "TOKEN", "CRYPTOCURRENCY",
    "EXPLICA", "DIFERENCA", "DIFERENÇA", "ENTRE", "RSI", "MACD", "SUPORTE",
    "RESISTENCIA", "INDICADOR", "INDICADORES",
}


def _extract_coin_from_prompt(prompt: str) -> str | None:
    upper = prompt.upper()
    for name, symbol in _KNOWN_COIN_NAMES.items():
        if name in upper:
            return _normalize_coin_symbol(symbol)
    for symbol in _KNOWN_SYMBOLS:
        if re.search(rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])", upper):
            return _normalize_coin_symbol(symbol)
        # also match lowercase versions (btc, eth, sol, ...)
        if re.search(rf"(?<![a-zA-Z0-9]){re.escape(symbol.lower())}(?![a-zA-Z0-9])", prompt):
            return _normalize_coin_symbol(symbol)
    words = prompt.split()
    for i, word in enumerate(words):
        if word.lower().strip(".,!?") in ["moeda", "coin", "token", "criptomoeda"] and i + 1 < len(words):
            next_word = words[i + 1].upper().strip(".,!?")
            if len(next_word) >= 2 and next_word.isalpha():
                return _normalize_coin_symbol(next_word)
    for word in words:
        w = word.upper().strip(".,!?")
        if 2 <= len(w) <= 10 and w.isalpha() and w not in _COIN_COMMON_WORDS:
            return _normalize_coin_symbol(w)
    return None


def _is_listing_tool_question(prompt: str) -> bool:
    q = (prompt or "").lower()
    return any(t in q for t in [
        "listing", "listado", "listados", "listagem",
        "vao ser", "vai ser", "acumular", "acumulando",
        "ainda nao foram listados", "unlisted", "not listed", "not yet listed",
        "exchange wallet", "exchange wallets", "potenciais listings", "radar",
    ]) and any(t in q for t in ["token", "tokens", "exchange", "exchanges", "wallet", "wallets"])


def _is_recent_holdings_tool_question(prompt: str) -> bool:
    q = (prompt or "").lower()
    if _is_listing_tool_question(prompt):
        return False
    return any(t in q for t in ["holding", "holdings", "wallet", "wallets", "acumulados", "detidos"]) and any(
        t in q for t in ["mostra", "recentes", "top", "exchange", "exchanges"]
    )


def _agent_system_message(req: ChatRequest, lang: str = "pt") -> str:
    portfolio_context = _portfolio_context_line(req.history)
    tools_block = (
        "\nAvailable tools:\n"
        "- analyze_coin: for technical analysis requests on a coin.\n"
        "- get_top100_rankings: for questions about top100, lower risk, support, RSI, risk/reward, reversal or best setups.\n"
        "- get_listing_predictions: for potential listings.\n"
        "- get_recent_holdings: for recent holdings detected in exchange wallets.\n"
        "- get_top100_delta: for changes in the top100 since yesterday.\n\n"
    )
    if lang == "en":
        lang_rule = (
            "You are the Vigia Crypto agent. ALWAYS reply in English — the user is writing in English. "
            "Never mix Portuguese into your answer.\n\n"
        )
        guidance = (
            "Use tools whenever the question needs internal data, rankings, predictions, holdings or technical analysis. "
            "Do not invent prices, scores, targets, news or rankings.\n\n"
            f"Today's date: {_date.today().isoformat()}.\n"
            + (f"{portfolio_context}\n" if portfolio_context else "")
            + tools_block
            + "If a tool returns a ready answer in the answer field, use it as the basis of your reply. "
            "If you don't need a tool, answer short, technical and clear. "
            "Avoid direct financial advice: present scenarios, risk and next steps."
        )
        return lang_rule + guidance

    lang_rule = (
        "És o agente do Vigia Crypto. Responde SEMPRE em português europeu — o utilizador está a escrever em português. "
        "Nunca mistures inglês na tua resposta.\n\n"
    )
    guidance = (
        "Usa ferramentas sempre que a pergunta precise de dados internos, rankings, predictions, holdings ou análise técnica. "
        "Não inventes preços, scores, targets, notícias ou rankings.\n\n"
        f"Data de hoje: {_date.today().isoformat()}.\n"
        + (f"{portfolio_context}\n" if portfolio_context else "")
        + tools_block
        + "Se uma ferramenta devolver uma resposta pronta no campo answer, usa essa resposta como base. "
        "Se não precisares de ferramenta, responde curto, técnico e claro. "
        "Evita aconselhamento financeiro direto: apresenta cenários, risco e próximos passos."
    )
    return lang_rule + guidance


def _history_messages(req: ChatRequest) -> list[dict]:
    return [
        {"role": m.role, "content": m.content}
        for m in (req.history or [])[-8:]
        if m.role in {"user", "assistant"} and m.content
    ]


def _tool_call_to_dict(call) -> dict:
    return {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.function.name,
            "arguments": call.function.arguments or "{}",
        },
    }


async def _run_agent_tool_calling(client, req: ChatRequest, lang: str = "pt") -> str:
    messages: list[dict] = [
        {"role": "system", "content": _agent_system_message(req, lang)},
        *_history_messages(req),
        {"role": "user", "content": req.prompt},
    ]
    last_tool_answer = None

    for _ in range(2):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []

        if not tool_calls:
            _no_answer = "Could not answer right now." if lang == "en" else "Não consegui responder agora."
            return (message.content or last_tool_answer or _no_answer).strip()

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [_tool_call_to_dict(call) for call in tool_calls],
            }
        )
        for call in tool_calls[:4]:
            result = await execute_tool(
                call.function.name,
                parse_tool_arguments(call.function.arguments),
            )
            last_tool_answer = result.get("answer") if isinstance(result, dict) else None
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    _fallback = "Could not complete analysis with tools now." if lang == "en" else "Não consegui fechar a análise com as ferramentas agora."
    return (last_tool_answer or _fallback).strip()


# Distinctive stopwords/markers for each language. These are words that appear
# very frequently in one language and almost never in the other, so counting
# them gives a robust per-message signal even for short prompts.
_PT_MARKERS = {
    "que", "qual", "quais", "como", "porque", "porquê", "está", "estao", "estão",
    "não", "nao", "sim", "uma", "uns", "umas", "isto", "isso", "agora", "também",
    "tambem", "moeda", "moedas", "comprar", "compro", "vender", "vendo", "achas",
    "devo", "posso", "tenho", "preço", "preco", "subir", "descer", "melhor",
    "está", "são", "sao", "para", "com", "dos", "das", "pelo", "pela", "mais",
    "muito", "ainda", "então", "entao", "fazes", "podes", "queres", "obrigado",
}
_EN_MARKERS = {
    "the", "what", "which", "how", "why", "is", "are", "should", "can", "could",
    "would", "do", "does", "buy", "sell", "price", "coin", "now", "good", "best",
    "about", "tell", "show", "give", "find", "analyze", "analyse", "this", "that",
    "near", "support", "for", "with", "and", "your", "you", "have", "want",
    "thanks", "please", "going", "still", "more",
}


def _detect_lang(prompt: str, fallback: str = "pt") -> str:
    """Detect PT vs EN by scoring distinctive markers. Falls back to the
    client-provided language when the signal is ambiguous (e.g. just a coin
    symbol like "BTC" with no real words)."""
    text = re.sub(r"[^a-zA-ZáàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ\s]", " ", prompt).lower()
    words = text.split()
    if not words:
        return fallback if fallback in ("pt", "en") else "pt"

    # Accented characters are a strong PT signal (EN has none of these).
    has_accents = bool(re.search(r"[áàâãéêíóôõúç]", text))

    word_set = set(words)
    pt_score = len(word_set & _PT_MARKERS) + (2 if has_accents else 0)
    en_score = len(word_set & _EN_MARKERS)

    if pt_score > en_score:
        return "pt"
    if en_score > pt_score:
        return "en"
    # Tie / no markers matched → trust the client's language preference.
    return fallback if fallback in ("pt", "en") else "pt"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    try:
        lang = _detect_lang(req.prompt, fallback=getattr(req, "lang", "pt"))
        if _is_onboarding_question(req.prompt):
            return StreamingResponse(_format_onboarding(req.prompt, lang=lang)(), media_type="text/plain")

        _q = req.prompt.lower()
        _is_delta_q = (
            any(t in _q for t in ["mudou", "mudança", "subiu mais", "desceu mais", "novidades top"]) or
            ("ontem" in _q and any(t in _q for t in ["top100", "top 100", "ranking", "score", "moedas", "coins"]))
        )
        _is_smart_money_q = any(t in _q for t in [
            "smart money", "fundos", "whales", "whale", "insiders", "insider",
            "market makers", "market maker", "institutions", "institucionais",
            "jump", "wintermute", "paradigm", "galaxy", "a16z", "multicoin",
        ])
        if not _is_smart_money_q and (is_top100_buy_question(req.prompt) or _is_opportunity_question(req.prompt) or _is_delta_q):
            result = answer_top100_buy_watchlist(log, req.prompt)
            def _top100():
                yield result.get("answer") or ("Could not fetch top100 ranking now." if lang == "en" else "Não consegui obter o ranking técnico top100 agora.")
            return StreamingResponse(_top100(), media_type="text/plain")

        if _is_listing_tool_question(req.prompt):
            result = await execute_tool("get_listing_predictions", {"lang": lang})
            def _listings():
                yield result.get("answer") or ("Could not fetch listing signals now." if lang == "en" else "Não consegui obter potenciais listings agora.")
            return StreamingResponse(_listings(), media_type="text/plain")

        if _is_smart_money_q:
            result = await execute_tool("get_smart_money", {"lang": lang})
            def _smart_money():
                yield result.get("answer") or ("Could not fetch smart money signals now." if lang == "en" else "Não consegui obter smart money agora.")
            return StreamingResponse(_smart_money(), media_type="text/plain")

        if _is_recent_holdings_tool_question(req.prompt):
            result = await execute_tool("get_recent_holdings")
            def _holdings():
                yield result.get("answer") or ("Could not fetch recent holdings now." if lang == "en" else "Não consegui obter holdings recentes agora.")
            return StreamingResponse(_holdings(), media_type="text/plain")

        if _is_top100_recommendation_followup(req.prompt):
            fn = _format_top100_recommendation(req.history or [], lang=lang)
            if fn:
                return StreamingResponse(fn(), media_type="text/plain")

        if _is_trade_followup(req.prompt):
            fn = _format_trade_followup(req.prompt, req.history, lang=lang)
            if fn:
                return StreamingResponse(fn(), media_type="text/plain")

        if _is_sell_followup(req.prompt) or _is_entry_price_followup(req.prompt):
            fn = _format_text_sell_followup(req.prompt, req.history, lang=lang)
            if fn:
                return StreamingResponse(fn(), media_type="text/plain")

        if _is_analysis_detail_followup(req.prompt):
            fn = _format_text_analysis_detail_followup(req.prompt, req.history, lang=lang)
            if fn:
                return StreamingResponse(fn(), media_type="text/plain")

        # Detect comparison questions (two or more coin symbols in the same prompt)
        _prompt_upper = req.prompt.upper()
        _mentioned_coins = [s for s in _KNOWN_SYMBOLS if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", _prompt_upper)]
        if len(_mentioned_coins) >= 2:
            fn = _format_comparison_followup(_mentioned_coins[:3], req.history or [], lang=lang)
            if fn:
                return StreamingResponse(fn(), media_type="text/plain")
            def _comparison_hint():
                if lang == "en":
                    yield (
                        f"To compare {' vs '.join(_mentioned_coins[:3])}, the best approach is to analyse each one separately and then compare the results.\n\n"
                        f"Try:\n"
                        + "\n".join(f"- `analyse {c}`" for c in _mentioned_coins[:3])
                        + "\n\nThen tell me what you see in each and I'll help you interpret which is in the best technical position."
                    )
                else:
                    yield (
                        f"Para comparar {' vs '.join(_mentioned_coins[:3])}, o melhor é analisares cada uma em separado e depois comparares os resultados.\n\n"
                        f"Experimenta:\n"
                        + "\n".join(f"- `analisa {c}`" for c in _mentioned_coins[:3])
                        + "\n\nDepois diz-me o que vês em cada uma e ajudo-te a interpretar qual está em melhor posição técnica."
                    )
            return StreamingResponse(_comparison_hint(), media_type="text/plain")

        if _should_use_coin_analysis(req.prompt):
            try:
                from analisegrafica.coin_analysis import AdvancedCoinAnalyzer
                coin = _extract_coin_from_prompt(req.prompt)
                if coin:
                    openai_key = os.getenv("OPENAI_API_KEY")
                    try:
                        from Api.services.crypto_tools import analyze_coin_tool
                        result = await analyze_coin_tool(coin)
                    except Exception:
                        analyzer = AdvancedCoinAnalyzer(openai_api_key=openai_key)
                        result = await analyzer.analyze_coin(coin)

                    if "error" not in result:
                        LAST_COIN_ANALYSIS.clear()
                        LAST_COIN_ANALYSIS.update({"coin": coin, "result": result})
                        entry_price = _extract_entry_price(req.prompt)
                        has_sell_q = _is_sell_followup(req.prompt)
                        def _analysis(
                            _coin=coin, _result=result, _lang=lang,
                            _entry=entry_price, _sell=has_sell_q,
                        ):
                            yield from _format_coin_analysis(_coin, _result, lang=_lang)
                            if _entry is not None and _sell:
                                current_price = _result.get("current_price")
                                if current_price:
                                    pnl_pct = ((_entry - 0) and (current_price - _entry) / _entry * 100)
                                    ts = lambda pt, en: pt if _lang == "pt" else en
                                    yield f"\n---\n\n**{ts('A tua posição', 'Your position')}**\n\n"
                                    yield f"- {ts('Preço médio de entrada:', 'Average entry price:')} **{_fmt_price(_entry)}**\n"
                                    yield f"- {ts('Preço atual:', 'Current price:')} **{_fmt_price(current_price)}**\n"
                                    pnl_pct = (current_price - _entry) / _entry * 100
                                    yield f"- {ts('Resultado atual:', 'Current result:')} **{pnl_pct:+.1f}%**\n\n"
                                    if pnl_pct < -50:
                                        yield ts(
                                            f"Estás com uma perda de **{abs(pnl_pct):.0f}%**. A este nível, a prioridade não é realizar lucro — é gerir risco. Avalia se a tese mudou. Se sim, considera sair antes de perdas maiores. Se ainda acreditas no projeto, define um stop e reduz a exposição.\n",
                                            f"You're at a **{abs(pnl_pct):.0f}%** loss. At this level, the priority isn't about taking profit — it's risk management. Assess if the thesis has changed. If so, consider cutting losses. If you still believe in the project, set a stop and reduce exposure.\n",
                                        )
                                    elif pnl_pct < -10:
                                        yield ts(
                                            "Como estás em perda, não trates isto como realização de lucro. A decisão é gerir risco: vender parcial se a tese mudou, ou aguardar recuperação técnica se ainda acreditas no setup.\n",
                                            "As you're at a loss, don't treat this as profit-taking. The decision is about risk management: sell partial if the thesis changed, or wait for technical recovery if you still believe in the setup.\n",
                                        )
                                    elif pnl_pct >= 50:
                                        yield ts(
                                            "Estás em lucro significativo. Com base nos targets técnicos acima, considera realizar parcial nos níveis de resistência identificados.\n",
                                            "You're at a significant profit. Based on the technical targets above, consider taking partial at the identified resistance levels.\n",
                                        )
                                    else:
                                        yield ts(
                                            "Estás próximo do teu preço médio. Acompanha os níveis técnicos acima para decidir continuidade ou saída.\n",
                                            "You're near your average entry. Watch the technical levels above to decide whether to hold or exit.\n",
                                        )
                        return StreamingResponse(_analysis(), media_type="text/plain")
                    else:
                        def _err():
                            err = result.get('error', 'Unknown error' if lang == 'en' else 'Erro desconhecido')
                            if lang == "en":
                                yield f"Error analysing {coin}: {err}\n"
                            else:
                                yield f"Erro ao analisar {coin}: {err}\n"
                        return StreamingResponse(_err(), media_type="text/plain")
                else:
                    def _ask_coin():
                        if lang == "en":
                            yield "Please specify which cryptocurrency you want to analyse.\nExamples: `analyse BTC`, `analyse SOL`, `analyse NEAR`\n"
                        else:
                            yield "Por favor especifica qual criptomoeda queres analisar.\nExemplos: `analisa BTC`, `analisa SOL`, `analisa NEAR`\n"
                    return StreamingResponse(_ask_coin(), media_type="text/plain")
            except Exception as e:
                log.warning("Erro ao analisar moeda: %s", e, exc_info=True)
                def _analysis_err():
                    if lang == "en":
                        yield f"Error analysing the coin: {e}\n"
                    else:
                        yield f"Erro ao analisar a moeda: {e}\n"
                return StreamingResponse(_analysis_err(), media_type="text/plain")

        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            async def _agent_openai():
                try:
                    yield await _run_agent_tool_calling(client, req, lang)
                except Exception as exc:
                    log.error("Erro no agente OpenAI: %s", exc)
                    yield ("Error processing your request." if lang == "en" else "Erro ao processar o pedido.")
            return StreamingResponse(_agent_openai(), media_type="text/plain")

            def _openai():
                try:
                    system_msg = (
                        "És um assistente especializado em análise de mercado de criptomoedas. "
                        "Responde sempre em português europeu quando o utilizador escrever em português. "
                        "O teu estilo é direto, técnico mas acessível — sem jargão desnecessário.\n\n"
                        f"Data de hoje: {_date.today().isoformat()}. Usa esta data como referência — nunca inventes datas futuras ou passadas.\n\n"
                        + (f"{_portfolio_context_line(req.history)}\n\n" if _portfolio_context_line(req.history) else "")
                        + "O que sabes fazer:\n"
                        "- Explicar conceitos de análise técnica (RSI, MACD, Bollinger, suporte/resistência, médias móveis)\n"
                        "- Interpretar setups de mercado e dar contexto sobre o que os indicadores significam\n"
                        "- Ajudar a pensar em gestão de risco: stop loss, targets, dimensionamento de posição\n"
                        "- Responder a perguntas sobre como exchanges funcionam, o que é on-chain, wallets, listings\n"
                        "- Dar contexto sobre projetos crypto: o que fazem, qual a narrativa, riscos conhecidos\n\n"
                        "Como lidar com perguntas específicas:\n\n"
                        "COMPARAÇÕES (ex: 'BTC ou ETH qual está melhor?'):\n"
                        "- Explica que a comparação técnica se faz moeda a moeda\n"
                        "- Sugere pedir 'analisa BTC' e 'analisa ETH' para obter os dados de RSI, tendência e SMA de cada uma\n"
                        "- Explica o que comparar: RSI (sobrecomprado vs sobrever), tendência de curto prazo, posição face à SMA200\n\n"
                        "PORTFOLIO (ex: 'tenho BTC e SOL, o que achas?'):\n"
                        "- Pergunta a que preço entrou em cada posição, se ainda não disse\n"
                        "- Dá contexto sobre o estado técnico atual de cada moeda com base no que sabes\n"
                        "- Fala sobre risco de correlação entre assets e diversificação\n\n"
                        "NOTÍCIAS / MACRO (ex: 'o que está a acontecer no mercado?'):\n"
                        "- Reconhece que não tens acesso a notícias em tempo real\n"
                        "- Explica o que os indicadores técnicos mostram (RSI médio do mercado, dominância BTC, tendência geral)\n"
                        "- Sugere pedir análises específicas para ver o estado técnico de cada moeda\n\n"
                        "PREVISÕES TEMPORAIS (ex: 'vai subir esta semana?'):\n"
                        "- Explica claramente por que previsões de curto prazo são impossíveis com certeza\n"
                        "- Oferece o que os indicadores mostram agora: RSI, tendência, suporte/resistência próximos\n"
                        "- Sugere 'analisa [SÍMBOLO]' para análise técnica atual\n\n"
                        "Regras gerais:\n"
                        "- Nunca digas 'deves comprar X' ou 'este é um bom investimento' — apresenta sempre cenários e riscos\n"
                        "- Se o utilizador perguntar sobre uma moeda específica, diz-lhe que pode pedir 'analisa [SÍMBOLO]' para análise técnica detalhada\n"
                        "- Se não souberes algo com certeza, diz-o — não inventes dados de preços ou indicadores\n"
                        "- Sê conciso: prefere 3 pontos claros a um parágrafo vago\n"
                        "- Quando o utilizador mencionar uma posição sua (comprou a X, tem Y unidades), usa isso para contextualizar a resposta"
                    )
                    with client.chat.completions.stream(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_msg},
                            *[
                                {"role": m.role, "content": m.content}
                                for m in (req.history or [])[-8:]
                                if m.role in {"user", "assistant"} and m.content
                            ],
                            {"role": "user", "content": req.prompt},
                        ],
                    ) as stream:
                        for event in stream:
                            if event.type == "content.delta" and event.delta:
                                yield event.delta
                            elif event.type == "error":
                                yield f"Erro: {event.error}"
                except Exception as exc:
                    log.error("Erro no stream OpenAI: %s", exc)
                    yield f"Erro ao processar: {exc}"
            return StreamingResponse(_openai(), media_type="text/plain")

        def _fallback():
            if lang == "en":
                yield "The AI chat feature is temporarily unavailable.\nYou can use the suggestions to check token holdings and predictions."
            else:
                yield "A funcionalidade de chat com IA está temporariamente indisponível.\nPodes usar as sugestões para consultar holdings e previsões de tokens."
        return StreamingResponse(_fallback(), media_type="text/plain")

    except Exception as e:
        log.error("Erro em /chat/stream: %s", e)
        _lang = locals().get("lang", "pt")
        def _exc():
            if _lang == "en":
                yield f"Error processing the message: {e}"
            else:
                yield f"Erro ao processar a mensagem: {e}"
        return StreamingResponse(_exc(), media_type="text/plain")
