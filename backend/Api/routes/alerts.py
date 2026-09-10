# backend/Api/routes/alerts.py
from __future__ import annotations
import os, time, math, logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
import requests

log = logging.getLogger("vigia")

# Garante que o diretório backend está no path para imports absolutos
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Carrega .env antes de importar utils.supa
try:
    from dotenv import load_dotenv
    env_paths = [
        BACKEND_DIR / ".env",
        BACKEND_DIR.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)  # override=True para garantir que carrega
            break
except ImportError:
    pass

# Importa supa
from utils import supa
import os

router = APIRouter(tags=["alerts"])

# Normalização de exchanges (p/ “listado noutra”)
EXCHANGE_NORMALIZE = {
    "Binance 1": "Binance", "Binance 2": "Binance", "Binance 3": "Binance",
    "Binance 7": "Binance", "Binance 8": "Binance", "Binance 14": "Binance", "Binance 16": "Binance",
    "Binance BNB 7": "Binance", "Binance BNB 28": "Binance", "Binance BNB 51": "Binance", "Binance BNB 70": "Binance",
    "Binance BNB Hot Wallet 20": "Binance",
    "Binance AVAX 74": "Binance", "Binance AVAX Cold Wallet 2": "Binance",
    "Binance AVAX Cold Wallet 5": "Binance", "Binance AVAX Hot Wallet 10": "Binance",
    "Coinbase 1": "Coinbase", "Coinbase Hot": "Coinbase", "Coinbase 10": "Coinbase",
    "Bybit": "Bybit", "Gate.io": "Gate.io", "Bitget": "Bitget",
    "Kraken Cold 1": "Kraken", "Kraken Cold 2": "Kraken",
    "OKX": "OKX", "OKX 73": "OKX", "OKX 93": "OKX",
    "OKX BNB 35": "OKX",
    "MEXC": "MEXC", "Bitget Hot Wallet 1": "Bitget",
    "Bybit BNB 17": "Bybit",
    "Gate BNB Deposit Funder": "Gate.io",
    "Huobi BNB 1": "Huobi",
}

TEST_TOKENS = {"TEST", "FOO", "PNUT"}
TOP100_EXCLUDED_SYMBOLS = {
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "USDS", "PYUSD",
    "USD1", "USDB", "USDX", "BUSD", "GUSD", "LUSD", "FRAX", "SUSD",
    "EURC", "EUROC", "EURI", "EURT", "EURQ", "BSC-USD", "USYC", "USDTE", "IDRT",
    "WBTC", "WETH", "STETH", "WSTETH", "WEETH", "RETH", "BETH",
    "CBBTC", "SPENDLE", "SENA", "BBTC", "BTCB", "HBTC",
    "PAXG", "XAUT", "XAUT0",
}
LISTING_EXCLUDED_SYMBOLS = TOP100_EXCLUDED_SYMBOLS | {
    "BNB", "ETH", "BTC", "SOL", "XRP", "ADA", "DOGE", "TRX", "MATIC",
}
LISTING_EXCLUDED_PREFIXES = ("W", "CB", "S", "BSC", "USD", "EUR")
LISTING_EXCLUDED_SUFFIXES = ("BTC", "ETH", "SOL", "USD", "EUR", "USDT", "BNB", "PENDLE")
LISTING_EXCLUDED_MAX_VALUE_USD = 500_000_000
DEFAULT_PREDICTIONS_MAX_AGE_HOURS = 336
PREDICTIONS_LIMIT = 10
_LIVE_LISTING_CACHE: Dict[str, set] = {}
STATIC_LIVE_LISTING_FALLBACKS = {
    "Binance": {"BABYDOGE", "BEAM", "BTT", "CAT", "CHEEMS", "EOS", "WNXM"},
}

def _is_english_prompt(text: str) -> bool:
    q = (text or "").lower()
    english_terms = (
        "what", "which", "show", "more", "listing", "listings", "unlisted",
        "exchange", "wallet", "wallets", "token", "tokens", "today",
    )
    portuguese_terms = (
        "que ", "quais", "mais ", "listados", "acumular", "carteira",
        "moeda", "moedas", "hoje", "comprar",
    )
    return any(term in q for term in english_terms) and not any(term in q for term in portuguese_terms)

def _prediction_max_age_hours() -> int:
    try:
        value = int(os.getenv("PREDICTIONS_MAX_AGE_HOURS", DEFAULT_PREDICTIONS_MAX_AGE_HOURS))
        return max(value, 1)
    except (TypeError, ValueError):
        return DEFAULT_PREDICTIONS_MAX_AGE_HOURS

def _prediction_since_iso() -> str:
    since = datetime.now(timezone.utc) - timedelta(hours=_prediction_max_age_hours())
    return since.isoformat()

def _wants_historical_predictions(q: str) -> bool:
    q = (q or "").lower()
    return any(term in q for term in [
        "historico", "histórico", "antigo", "antigos", "arquivo", "outubro",
        "old", "older", "historical", "archive",
    ])

def _is_buy_watchlist_question(q: str) -> bool:
    q = (q or "").lower()
    buy_terms = (
        "comprar", "compra", "buy", "entrada", "entrar", "aconselhas",
        "recomendas", "oportunidade", "oportunidades", "analisar",
        "melhor", "melhores", "risco", "suporte", "pullback", "rsi",
    )
    universe_terms = ("moeda", "moedas", "crypto", "cripto", "token", "tokens", "top100", "top 100", "hoje", "mercado")
    return any(term in q for term in buy_terms) and any(term in q for term in universe_terms)

def _is_top100_buy_question(q: str) -> bool:
    q = (q or "").lower()
    if "top100" not in q and "top 100" not in q:
        return False
    top100_terms = (
        "comprar", "compra", "buy", "entrada", "entrar", "aconselhas",
        "recomendas", "oportunidade", "oportunidades", "analisar",
        "analisa", "melhor", "melhores", "risco", "suporte", "rsi",
        "oversold", "sobrevend", "pullback", "hoje",
    )
    return _is_buy_watchlist_question(q) or any(term in q for term in top100_terms)

def _fmt_money(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "N/A"
    if number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"${number / 1_000:.1f}K"
    if number >= 1:
        return f"${number:.2f}"
    if number >= 0.001:
        return f"${number:.4f}"
    if number > 0:
        return f"${number:.8g}"
    return f"${number:.2f}"

def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "N/A"

def _human_zone_label(zone: str) -> str:
    return {"ZONA_DE_COMPRA": "compra", "ZONA_DE_VENDA": "venda", "ZONA_NEUTRA": "neutra"}.get(zone, zone.lower() or "—")


def _top100_mode(prompt: str) -> str:
    q = (prompt or "").lower()
    if any(t in q for t in ["mudou", "mudança", "mudancas", "ontem", "subiu mais", "desceu mais", "novidades", "o que e novo", "o que é novo"]):
        return "delta"
    if "risco" in q or "segura" in q or "seguro" in q or "menos risco" in q:
        return "low_risk"
    if "risco/retorno" in q or "risco retorno" in q or "relacao risco" in q or "relação risco" in q:
        return "risk_reward"
    if "melhor compra" in q or "comprar hoje" in q or "confirmado" in q or "virou" in q:
        return "bounce"
    if "suporte" in q or "pullback" in q or "perto" in q:
        return "near_support"
    if "rsi" in q or "oversold" in q or "sobrevend" in q or "barato" in q:
        return "low_rsi"
    return "score"


def _top100_mode(prompt: str) -> str:
    q = (prompt or "").lower()
    if any(t in q for t in ["mudou", "mudanca", "mudancas", "ontem", "yesterday", "changed", "change", "subiu mais", "desceu mais", "novidades", "o que e novo"]):
        return "delta"
    if "risco/retorno" in q or "risco retorno" in q or "relacao risco" in q or "risk/reward" in q or "risk reward" in q:
        return "risk_reward"
    if "risco" in q or "risk" in q or "safe" in q or "safer" in q or "segura" in q or "seguro" in q or "menos risco" in q:
        return "low_risk"
    if "melhor compra" in q or "comprar hoje" in q or "confirmed buy" in q or "best buy" in q or "confirmado" in q or "virou" in q:
        return "bounce"
    if "suporte" in q or "support" in q or "pullback" in q or "near" in q or "perto" in q:
        return "near_support"
    if "rsi" in q or "oversold" in q or "lowest" in q or "cheap" in q or "sobrevend" in q or "barato" in q:
        return "low_rsi"
    return "score"


def _is_buy_watchlist_question(q: str) -> bool:
    q = (q or "").lower()
    buy_terms = (
        "comprar", "compra", "buy", "entrada", "entrar", "aconselhas",
        "recomendas", "oportunidade", "oportunidades", "analisar",
        "melhor", "melhores", "risco", "suporte", "pullback", "rsi",
        "opportunity", "opportunities", "analyze", "best", "risk", "support",
        "lowest", "cheap", "near", "oversold",
    )
    universe_terms = (
        "moeda", "moedas", "crypto", "cripto", "token", "tokens", "coin",
        "coins", "top100", "top 100", "hoje", "today", "market", "mercado",
    )
    return any(term in q for term in buy_terms) and any(term in q for term in universe_terms)


def _is_top100_buy_question(q: str) -> bool:
    q = (q or "").lower()
    if "top100" not in q and "top 100" not in q:
        return False
    top100_terms = (
        "comprar", "compra", "buy", "entrada", "entrar", "aconselhas",
        "recomendas", "oportunidade", "oportunidades", "analisar",
        "analisa", "melhor", "melhores", "risco", "suporte", "rsi",
        "oversold", "sobrevend", "pullback", "hoje", "today", "support",
        "risk", "lowest", "near", "mudou", "mudanca", "mudança", "mudancas",
        "mudanças", "ontem", "subiu mais", "desceu mais", "novidades",
        "changed", "change", "yesterday",
    )
    return _is_buy_watchlist_question(q) or any(term in q for term in top100_terms)

def _risk_rank(value: Any) -> int:
    text = str(value or "").upper()
    if "BAIXO" in text:
        return 0
    if "MODERADO/ELEVADO" in text:
        return 2
    if "ELEVADO" in text:
        return 3
    return 1

def _risk_reward_ratio(row: Dict[str, Any]) -> float:
    """Upside/downside ratio: (resistance-price) / (price-support). Higher = better."""
    try:
        price = float(row.get("price") or 0)
        support = float(row.get("support") or 0)
        resistance = float(row.get("resistance") or 0)
        if price <= 0 or support <= 0 or resistance <= price:
            return 0.0
        upside = resistance - price
        downside = price - support
        return round(upside / downside, 2) if downside > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _bounce_score(row: Dict[str, Any]) -> float:
    """Score for 'bateu no suporte e virou': near support + RSI recovering + MACD bullish."""
    score = 0.0
    pos = float(row.get("current_position") or 50)
    rsi = float(row.get("rsi") or 50)
    macd = str(row.get("macd_signal") or "")
    entry = str(row.get("entry_zone") or "")
    if pos <= 35:
        score += 3
    if 25 <= rsi <= 48:
        score += 3
    if "BULLISH" in macd:
        score += 3
        if "STRONG" in macd:
            score += 1
    if entry == "ZONA_DE_COMPRA":
        score += 2
    return score


def _sort_top100_rows(rows: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    if mode == "low_risk":
        return sorted(rows, key=lambda row: (_risk_rank(row.get("risk")), -float(row.get("score") or 0)))
    if mode == "risk_reward":
        return sorted(rows, key=lambda row: -_risk_reward_ratio(row))
    if mode == "bounce":
        return sorted(rows, key=lambda row: (-_bounce_score(row), -float(row.get("score") or 0)))
    if mode == "near_support":
        return sorted(rows, key=lambda row: (
            abs(float(row.get("current_position") if row.get("current_position") is not None else 50) - 25),
            -float(row.get("score") or 0),
        ))
    if mode == "low_rsi":
        return sorted(rows, key=lambda row: (
            float(row.get("rsi") if row.get("rsi") is not None else 50),
            -float(row.get("score") or 0),
        ))
    return sorted(rows, key=lambda row: float(row.get("score") or 0), reverse=True)

def _top100_title(mode: str, count: int) -> str:
    titles = {
        "near_support": f"**Perto do suporte — possíveis entradas ({count} moedas)**",
        "low_rsi":      f"**Preços mais castigados agora ({count} moedas)**",
        "low_risk":     f"**Menor risco técnico agora ({count} moedas)**",
        "risk_reward":  f"**Melhor relação risco/retorno ({count} moedas)**",
        "bounce":       f"**Possível reversão confirmada — bateu no suporte e virou ({count} moedas)**",
    }
    return titles.get(mode, f"**Melhores setups técnicos hoje ({count} moedas)**")


def _rsi_label(rsi: float) -> str:
    if rsi < 28:
        return "preço muito castigado — tende a recuperar"
    if rsi < 38:
        return "preço sobrevendido — vendedores a perder força"
    if rsi < 50:
        return "ligeira pressão de venda — equilibrio frágil"
    if rsi < 62:
        return "mercado equilibrado"
    if rsi < 70:
        return "compradores dominam — atenção se subir mais"
    return "preço esticado — risco de correção"


def _mode_label(mode: str) -> str:
    if mode == "near_support":
        return "Perto de Suporte"
    if mode == "low_rsi":
        return "RSI Baixo"
    if mode == "risk_reward":
        return "Melhor R/R"
    if mode == "bounce":
        return "Reversão Confirmada"
    if mode == "delta":
        return "Variação Diária"
    if mode == "low_risk":
        return "Menor Risco"
    return "Melhor Setup"


def _coingecko_link(item: Dict[str, Any]) -> str:
    coin_id = str(item.get("coin_id") or "").strip()
    symbol = str(item.get("symbol") or "").strip()
    if coin_id:
        return f"https://www.coingecko.com/en/coins/{coin_id}"
    if symbol:
        return f"https://www.coingecko.com/en/search?query={symbol}"
    return ""


def _format_top100_block(i: int, item: Dict[str, Any], mode: str) -> str:
    symbol = item.get("symbol") or "N/A"
    name = item.get("name") or symbol
    score = float(item.get("score") or 0)
    price = float(item.get("price") or 0)
    signal = item.get("signal") or "N/A"
    entry_zone = item.get("entry_zone") or ""
    technical_action = item.get("technical_action") or ""
    rsi = item.get("rsi")
    trend = item.get("trend") or ""
    above_200 = item.get("above_sma200")
    macd_sig = item.get("macd_signal") or "NEUTRO"
    bb_pos = item.get("bb_position") or "NEUTRO"
    support = item.get("support")
    resistance = item.get("resistance")
    current_position = item.get("current_position")
    change_7d = item.get("change_7d")
    change_30d = item.get("change_30d")

    mode_lbl = _mode_label(mode)
    mode_part = f" ({mode_lbl})" if mode != "score" else ""
    lines = [f"**{i}. {symbol} — {name}**{mode_part}"]
    if price:
        lines.append(f"**Preço atual:** {_fmt_money(price)}")
    else:
        lines.append("**Preço atual:** N/A")

    # Suporte / Resistência
    if support and resistance:
        sup_fmt = _fmt_money(support)
        res_fmt = _fmt_money(resistance)
        # Alvo bullish: +8% a +18% acima da resistência, proporcional ao score
        target_mult = 1.08 + (score / 100) * 0.10
        target_fmt = _fmt_money(float(resistance) * target_mult)

        rr = _risk_reward_ratio(item)
        rr_str = f" · R/R {rr:.1f}x" if rr >= 1 else ""

        if entry_zone == "ZONA_DE_COMPRA":
            lines.append(f"🎯 **Entrada:** perto de {sup_fmt} · **Alvo:** {target_fmt}{rr_str}")
            lines.append(f"🛡️ **Stop:** {_fmt_money(float(support) * 0.94)}")
        elif entry_zone == "ZONA_DE_VENDA":
            lines.append(f"⚠️ Perto da resistência **{res_fmt}** — não perseguir")
        else:
            lines.append(f"🟢 Suporte: **{sup_fmt}** · 🔴 Resistência: **{res_fmt}**{rr_str}")
    elif not price:
        lines.append("Sem preço suficiente para calcular entrada/alvo.")

    # Sinais
    signals = []
    if rsi is not None:
        rsi_f = float(rsi)
        emoji = "✅" if rsi_f < 45 else ("⚠️" if rsi_f < 70 else "🔴")
        signals.append(f"{emoji} {_rsi_label(rsi_f)}")
    if above_200 is True:
        signals.append("✅ Tendência de longo prazo positiva")
    elif above_200 is False:
        signals.append("⚠️ Tendência de longo prazo negativa")
    if macd_sig in ("BULLISH", "BULLISH_STRONG"):
        signals.append("✅ Momentum a virar para cima" + (" — confirmado" if "STRONG" in macd_sig else ""))
    elif macd_sig in ("BEARISH", "BEARISH_STRONG"):
        signals.append("⚠️ Momentum ainda em queda")
    if bb_pos == "ZONA_BAIXA":
        signals.append("✅ Preço perto da zona de bounce")
    if change_30d is not None:
        c30 = float(change_30d)
        signals.append(f"{'📈' if c30 >= 0 else '📉'} {'+' if c30 >= 0 else ''}{c30:.1f}% nos últimos 30 dias")
    if signals:
        lines.append("**Sinais:**")
        lines.extend(signals)

    # Leitura
    bounce_confirmed = entry_zone == "ZONA_DE_COMPRA" and macd_sig in ("BULLISH", "BULLISH_STRONG")
    if bounce_confirmed:
        lines.append("🔥 **Reversão em curso** — perto do suporte com momentum a virar. Setup de entrada válido.")
    elif entry_zone == "ZONA_DE_COMPRA":
        lines.append("🟡 **Perto do suporte** — aguardar momentum confirmar antes de entrar.")
    elif entry_zone == "ZONA_DE_VENDA":
        lines.append("🔴 **Perto da resistência** — não perseguir. Esperar pullback.")
    elif technical_action == "AGUARDAR" or not entry_zone:
        if support:
            lines.append(f"⏳ Zona neutra — vigiar teste ao suporte **{_fmt_money(support)}**.")
        else:
            lines.append("⏳ Zona neutra — aguardar setup mais claro.")

    cg_url = _coingecko_link(item)
    if cg_url:
        lines.append(f"[Ver no CoinGecko]({cg_url})")

    return "\n".join(lines)


def _wants_english(prompt: str) -> bool:
    q = (prompt or "").lower()
    return any(t in q for t in ["which ", "what ", "show ", "changed", "since yesterday", "near support", "lowest rsi", "risk reward"])


def _delta_reason(row: Dict[str, Any], yest: Dict[str, Any] | None, english: bool = False) -> str:
    zone = str(row.get("entry_zone") or "")
    zone_y = str((yest or {}).get("entry_zone") or "")
    macd = str(row.get("macd_signal") or "")
    rsi = row.get("rsi")
    pos = row.get("current_position")
    reasons = []
    if zone != zone_y and zone_y:
        before = _human_zone_label(zone_y)
        after = _human_zone_label(zone)
        reasons.append(f"zone changed from {before} to {after}" if english else f"zona passou de {before} para {after}")
    if macd in ("BULLISH", "BULLISH_STRONG"):
        reasons.append("momentum turned bullish" if english else "momentum virou para cima")
    elif macd in ("BEARISH", "BEARISH_STRONG"):
        reasons.append("momentum still weak" if english else "momentum ainda fraco")
    try:
        rsi_f = float(rsi)
        if rsi_f < 35:
            reasons.append(f"RSI oversold ({rsi_f:.0f})" if english else f"RSI sobrevendido ({rsi_f:.0f})")
        elif rsi_f > 70:
            reasons.append(f"RSI stretched ({rsi_f:.0f})" if english else f"RSI esticado ({rsi_f:.0f})")
    except (TypeError, ValueError):
        pass
    try:
        pos_f = float(pos)
        if pos_f <= 35:
            reasons.append("close to support" if english else "perto do suporte")
        elif pos_f >= 75:
            reasons.append("close to resistance" if english else "perto da resistencia")
    except (TypeError, ValueError):
        pass
    if not reasons:
        reasons.append("technical score improved vs yesterday" if english else "score tecnico melhorou face a ontem")
    return "; ".join(reasons[:2])


def _format_top100_block_en(i: int, item: Dict[str, Any], mode: str) -> str:
    symbol = item.get("symbol") or "N/A"
    name = item.get("name") or symbol
    score = float(item.get("score") or 0)
    support = item.get("support")
    resistance = item.get("resistance")
    rsi = item.get("rsi")
    risk = item.get("risk") or "N/A"
    entry_zone = item.get("entry_zone") or ""
    macd = item.get("macd_signal") or "NEUTRAL"
    price = item.get("price")
    lines = [f"**{i}. {symbol} - {name}**"]
    if price:
        lines.append(f"Current price: **{_fmt_money(price)}**")
    else:
        lines.append("Current price: **N/A**")
    if support and resistance:
        lines.append(f"Entry area: **{_fmt_money(support)}** - Target area: **{_fmt_money(resistance)}** - R/R {_risk_reward_ratio(item):.1f}x")
    details = []
    if rsi is not None:
        details.append(f"RSI {float(rsi):.0f}")
    details.append(f"risk {risk}")
    details.append(f"score {score:.0f}/100")
    lines.append("Signals: " + " - ".join(details))
    if entry_zone == "ZONA_DE_COMPRA" and macd in ("BULLISH", "BULLISH_STRONG"):
        lines.append("Read: close to support with bullish momentum confirmation.")
    elif entry_zone == "ZONA_DE_COMPRA":
        lines.append("Read: close to support, but waiting for momentum confirmation.")
    elif entry_zone == "ZONA_DE_VENDA":
        lines.append("Read: close to resistance; avoid chasing, wait for pullback.")
    else:
        lines.append("Read: neutral area; wait for a clearer setup.")
    cg_url = _coingecko_link(item)
    if cg_url:
        lines.append(f"[Open CoinGecko]({cg_url})")
    return "\n".join(lines)

def _fetch_top100_rows(date_filter: str | None, log=None) -> tuple[list, bool]:
    """Fetch top100 rows from Supabase. Returns (rows, has_technical_cols)."""
    base_select = "date,rank,coin_id,symbol,name,price,market_cap,volume_24h,change_24h,change_7d,change_30d,volume_ratio,score,risk,signal,rationale,ts"
    tech_select = f"{base_select},rsi,trend,support,resistance,current_position,entry_zone,technical_action,technical_confidence,macd_signal,macd_hist,above_sma200,bb_position,bb_width"
    params = {"select": tech_select, "order": "score.desc", "limit": "50"}
    if date_filter:
        params["date"] = f"eq.{date_filter}"
    r = supa.rest_get("top100_technical_rankings", params=params, timeout=8)
    if r.status_code != 200:
        # Fallback: try without technical columns (older schema)
        params2 = {"select": base_select, "order": "score.desc", "limit": "50"}
        if date_filter:
            params2["date"] = f"eq.{date_filter}"
        r2 = supa.rest_get("top100_technical_rankings", params=params2, timeout=8)
        if r2.status_code != 200:
            if log:
                log.warning("Top100 ranking indisponivel: HTTP %s / %s", r.status_code, r2.status_code)
            return [], False
        if log:
            log.warning("Top100 ranking sem colunas tecnicas; usando select legacy")
        return r2.json() or [], False
    return r.json() or [], True


def _answer_top100_buy_watchlist(log=None, prompt: str = "") -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    raw, has_tech = _fetch_top100_rows(today, log)
    if not raw:
        raw, has_tech = _fetch_top100_rows(yesterday, log)
    if not raw:
        # Last resort: no date filter (any historical data)
        raw, has_tech = _fetch_top100_rows(None, log)

    if raw is None or (isinstance(raw, list) and len(raw) == 0 and not has_tech):
        answer = (
            "The daily top100 technical ranking isn't available yet.\n\n"
            "The holders cron updates it — check that it ran without errors.\n\n"
            "In the meantime you can try `analyze BTC`, `analyze SOL`, `analyze NEAR`, etc."
        )
        return {"ok": True, "answer": answer, "count": 0, "items": []}

    mode = _top100_mode(prompt)
    english = _wants_english(prompt)

    # Delta mode: compare today vs yesterday
    if mode == "delta":
        raw_yesterday, _ = _fetch_top100_rows(yesterday, log)
        yest_by_symbol = {
            str(r.get("symbol") or "").upper(): r
            for r in (raw_yesterday or [])
            if str(r.get("symbol") or "").upper() not in TOP100_EXCLUDED_SYMBOLS
        }
        delta_rows = []
        for row in raw:
            sym = str(row.get("symbol") or "").upper()
            if sym in TOP100_EXCLUDED_SYMBOLS or not float(row.get("score") or 0):
                continue
            yest = yest_by_symbol.get(sym)
            score_now = float(row.get("score") or 0)
            score_then = float(yest.get("score") or 0) if yest else score_now
            row["score_delta"] = round(score_now - score_then, 1)
            row["zone_yesterday"] = str(yest.get("entry_zone") or "") if yest else ""
            delta_rows.append(row)
        # Show biggest positive movers first
        delta_rows.sort(key=lambda r: -float(r.get("score_delta") or 0))
        rows = delta_rows[:10]
        if rows:
            if english:
                lines = [f"**What changed in the top100 since yesterday ({len(rows)} biggest movers)**\n"]
                for i, r in enumerate(rows, 1):
                    sym = str(r.get("symbol") or "")
                    delta = float(r.get("score_delta") or 0)
                    score = float(r.get("score") or 0)
                    zone = str(r.get("entry_zone") or "")
                    zone_y = str(r.get("zone_yesterday") or "")
                    zone_change = ""
                    if zone != zone_y and zone_y:
                        zone_change = f" - zone: {_human_zone_label(zone_y)} -> {_human_zone_label(zone)}"
                    reason = _delta_reason(r, yest_by_symbol.get(sym), english=True)
                    direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
                    lines.append(f"{i}. **{sym}** {direction} - score {score:.0f} ({'+' if delta >= 0 else ''}{delta:.1f} vs yesterday){zone_change}\n   Why: {reason}.")
                return {"ok": True, "answer": "\n".join(lines), "count": len(rows), "items": rows}
            lines = [f"**O que mudou no top100 desde ontem ({len(rows)} moedas com maior variação)**\n"]
            for i, r in enumerate(rows, 1):
                sym = str(r.get("symbol") or "")
                delta = float(r.get("score_delta") or 0)
                score = float(r.get("score") or 0)
                zone = str(r.get("entry_zone") or "")
                zone_y = str(r.get("zone_yesterday") or "")
                arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
                zone_change = ""
                if zone != zone_y and zone_y:
                    zone_change = f" · zona: {_human_zone_label(zone_y)} → {_human_zone_label(zone)}"
                reason = _delta_reason(r, yest_by_symbol.get(sym), english=False)
                lines.append(
                    f"{i}. **{sym}** {arrow} score {score:.0f} "
                    f"({'+' if delta >= 0 else ''}{delta:.1f} pts vs yesterday){zone_change}\n"
                    f"   Why it changed: {reason}."
                )
            lines.append("\nNote: variation is in technical score points. The score combines technical zone, RSI, momentum, proximity to support/resistance and risk.")
            return {"ok": True, "answer": "\n".join(lines), "count": len(rows), "items": rows}
        return {"ok": True, "answer": "No yesterday's data available yet to compare.", "count": 0, "items": []}

    rows = [
        row for row in raw
        if str(row.get("symbol") or "").upper() not in TOP100_EXCLUDED_SYMBOLS
        and float(row.get("score") or 0) > 0
        and float(row.get("price") or 0) > 0
    ]
    rows = _sort_top100_rows(rows, mode)[:10]
    if not rows:
        answer = (
            "The top100 table exists but has no valid data for today.\n\n"
            "The holders cron updates it — check the logs for any errors.\n\n"
            "In the meantime you can try `analyze BTC`, `analyze SOL`, `analyze NEAR`, etc."
        )
        return {"ok": True, "answer": answer, "count": 0, "items": []}

    if english:
        titles = {
            "near_support": f"**Near support - possible entries ({len(rows)} coins)**",
            "low_rsi": f"**Lowest RSI / most punished prices ({len(rows)} coins)**",
            "low_risk": f"**Lowest technical risk now ({len(rows)} coins)**",
            "risk_reward": f"**Best risk/reward setups ({len(rows)} coins)**",
            "bounce": f"**Possible confirmed reversals ({len(rows)} coins)**",
        }
        header = titles.get(mode, f"**Best technical setups today ({len(rows)} coins)**")
        coin_blocks = [_format_top100_block_en(i, item, mode) for i, item in enumerate(rows, 1)]
    else:
        header = _top100_title(mode, len(rows))
        coin_blocks = [_format_top100_block(i, item, mode) for i, item in enumerate(rows, 1)]

    examples = ", ".join(str(r.get("symbol") or "").upper() for r in rows[:3] if r.get("symbol"))
    footer = f"_Ask_ `analyze {examples.split(', ')[0]}` _for detailed technical analysis._" if english and examples else (f"_Pede_ `analisa {examples.split(', ')[0]}` _para analise tecnica detalhada._" if examples else "")

    answer = header + "\n\n" + "\n\n---\n\n".join(coin_blocks)
    if footer:
        answer += "\n\n" + footer
    return {"ok": True, "answer": answer, "count": len(rows), "items": rows}

@router.get("/alerts/top100")
def get_top100_rankings(mode: str = "near_support", limit: int = 5):
    """
    Devolve ranking tecnico top100 em JSON para o painel inicial.
    """
    import logging
    log = logging.getLogger("vigia")

    if not supa.ok():
        return {"ok": False, "error": "Supabase nao configurado", "items": []}

    safe_limit = max(1, min(int(limit or 5), 10))
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    raw, _ = _fetch_top100_rows(today, log)
    if not raw:
        raw, _ = _fetch_top100_rows(yesterday, log)
    if not raw:
        raw, _ = _fetch_top100_rows(None, log)

    rows = [
        row for row in (raw or [])
        if str(row.get("symbol") or "").upper() not in TOP100_EXCLUDED_SYMBOLS
        and float(row.get("score") or 0) > 0
        and float(row.get("price") or 0) > 0
    ]
    allowed_modes = {"score", "near_support", "low_rsi", "low_risk", "risk_reward", "bounce"}
    selected_mode = mode if mode in allowed_modes else "near_support"
    rows = _sort_top100_rows(rows, selected_mode)[:safe_limit]
    return {"ok": True, "mode": selected_mode, "count": len(rows), "items": rows}

def _is_test_token(row: Dict[str, Any]) -> bool:
    token = str(row.get("token") or "").strip().upper()
    token_address = str(row.get("token_address") or "").strip().lower()
    pair_url = str(row.get("pair_url") or "").strip().lower()
    analysis = " ".join(
        str(row.get(field) or "").lower()
        for field in ("analysis", "analysis_text", "ai_analysis")
    )
    return (
        token in TEST_TOKENS
        or token in LISTING_EXCLUDED_SYMBOLS
        or _num(row, "value_usd") > LISTING_EXCLUDED_MAX_VALUE_USD
        or any(token.startswith(prefix) for prefix in LISTING_EXCLUDED_PREFIXES)
        or any(token.endswith(suffix) for suffix in LISTING_EXCLUDED_SUFFIXES)
        or (
            any(token.startswith(prefix) for prefix in LISTING_EXCLUDED_PREFIXES)
            and any(token.endswith(suffix) for suffix in LISTING_EXCLUDED_SUFFIXES)
        )
        or token_address.startswith("test")
        or "/test" in pair_url
        or "registo de teste" in analysis
        or "registro de teste" in analysis
    )

def _score(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0

def _num(row: Dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0

def _freshness_bonus(row: Dict[str, Any]) -> float:
    try:
        ts_raw = str(row.get("ts") or "")
        if not ts_raw:
            return 0.0
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours <= 24:
            return 6.0
        if age_hours <= 72:
            return 3.0
        return 0.0
    except Exception:
        return 0.0

def _listing_score(row: Dict[str, Any]) -> float:
    """Score continuo para UI/chat; evita dezenas de candidatos empatados em 70."""
    value_usd = _num(row, "value_usd")
    liquidity = _num(row, "liquidity")
    volume_24h = _num(row, "volume_24h")
    raw_score = _score(row)

    score = 22.0
    if value_usd > 0:
        score += min(24.0, math.log10(value_usd + 1) * 3.6)
    else:
        score -= 8.0

    if liquidity > 0:
        score += min(24.0, math.log10(liquidity + 1) * 3.2)
    if liquidity < 100_000:
        score -= 8.0

    if volume_24h > 0:
        score += min(14.0, math.log10(volume_24h + 1) * 2.1)

    if row.get("pair_url"):
        score += 2.0
    score += _freshness_bonus(row)

    # Mantem algum sinal do score original, mas sem deixar o 70 dominar tudo.
    score = score * 0.82 + raw_score * 0.18
    lower_bound = 50.0 if raw_score >= 50 else 0.0
    return round(min(max(score, lower_bound), 99.0), 1)

def _apply_listing_score(row: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(row)
    updated["raw_score"] = _score(row)
    updated["score"] = _listing_score(row)
    if row.get("source") == "arkham":
        updated["score"] = max(float(updated["score"] or 0), _score(row))
    return updated

def _arkham_signal_to_prediction(row: Dict[str, Any]) -> Dict[str, Any]:
    token_address = str(row.get("token_address") or "").strip()
    if token_address.startswith("arkham:"):
        token_address = ""
    return {
        "id": row.get("id") or row.get("signal_key"),
        "exchange": row.get("exchange") or row.get("entity"),
        "token": row.get("token"),
        "token_address": token_address,
        "chain": row.get("chain"),
        "score": row.get("score"),
        "ts": row.get("ts"),
        "pair_url": row.get("pair_url"),
        "value_usd": row.get("value_usd"),
        "liquidity": row.get("liquidity_usd") or row.get("liquidity"),
        "volume_24h": row.get("volume_24h") or 0,
        "analysis_text": row.get("analysis_text"),
        "source": "arkham",
        "market_cap_usd": row.get("market_cap_usd"),
        "position_pct": row.get("position_pct"),
        "liquidity_pct": row.get("liquidity_pct"),
        "exchange_count": row.get("exchange_count"),
    }

def _fetch_arkham_exchange_predictions(log=None) -> List[Dict[str, Any]]:
    params = {
        "entity_type": "eq.exchange",
        "select": (
            "id,signal_key,entity,exchange,token,token_address,chain,score,ts,pair_url,"
            "value_usd,liquidity_usd,market_cap_usd,position_pct,liquidity_pct,"
            "exchange_count,analysis_text"
        ),
        "limit": "500",
        "order": "score.desc",
        "ts": f"gte.{_prediction_since_iso()}",
    }
    try:
        r = supa.rest_get("arkham_signals", params=params, timeout=8)
        if r.status_code != 200:
            if log:
                log.warning("Erro ao buscar Arkham predictions: HTTP %s - %s", r.status_code, r.text[:200])
            return []
        return [_arkham_signal_to_prediction(row) for row in (r.json() or [])]
    except Exception as e:
        if log:
            log.warning("Erro ao buscar Arkham predictions: %s", e)
        return []

def _normalize_exchange(exchange: str) -> str:
    exchange = str(exchange or "").strip()
    return EXCHANGE_NORMALIZE.get(exchange, exchange)

def _token_candidates(token: str) -> set:
    base = str(token or "").strip().upper().lstrip("$")
    if not base:
        return set()
    candidates = {base}
    candidates.update({f"1000{base}", f"10000{base}", f"1000000{base}", f"1M{base}"})
    for prefix in ("1000000", "10000", "1000", "1M"):
        if base.startswith(prefix) and len(base) > len(prefix):
            candidates.add(base[len(prefix):])
    if base == "BABYDOGE":
        candidates.update({"1MBABYDOGE", "1000000BABYDOGE"})
    return candidates

def _dedupe_latest_predictions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = "|".join([
            str(row.get("exchange") or ""),
            str(row.get("token_address") or row.get("token") or ""),
            str(row.get("chain") or ""),
        ]).lower()
        if key not in latest or str(row.get("ts") or "") > str(latest[key].get("ts") or ""):
            latest[key] = row

    items = list(latest.values())
    items.sort(key=lambda x: (_score(x), str(x.get("ts") or "")), reverse=True)
    return items

def _load_listed_tokens_map(log=None) -> Dict[str, set]:
    try:
        rows = []
        page_size = 1000
        offset = 0
        while True:
            params = {
                "select": "exchange,token",
                "limit": str(page_size),
                "offset": str(offset),
            }
            r = supa.rest_get("exchange_tokens", params=params, timeout=8)
            if r.status_code != 200:
                if log:
                    log.warning("Nao foi possivel carregar exchange_tokens: HTTP %s", r.status_code)
                return _load_live_listing_fallbacks(log)
            page = r.json() or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        listed: Dict[str, set] = {}
        for row in rows:
            exchange = _normalize_exchange(str(row.get("exchange") or "").strip())
            token = str(row.get("token") or "").strip().upper()
            if exchange and token:
                listed.setdefault(exchange, set()).update(_token_candidates(token))
        for exchange, tokens in _load_live_listing_fallbacks(log).items():
            listed.setdefault(exchange, set()).update(tokens)
        return listed
    except Exception as e:
        if log:
            log.warning("Erro ao carregar exchange_tokens: %s", e)
        return _load_live_listing_fallbacks(log)

def _fetch_live_tokens(exchange: str) -> set:
    """Fetch currently listed spot tokens from exchange public API."""
    try:
        if exchange == "Binance":
            for url in (
                "https://data-api.binance.vision/api/v3/exchangeInfo",
                "https://api.binance.com/api/v3/exchangeInfo",
            ):
                r = requests.get(url, timeout=8)
                if r.status_code != 200:
                    continue
                data = r.json()
                tokens = {
                    str(s.get("baseAsset") or "").upper()
                    for s in data.get("symbols", [])
                    if s.get("status") == "TRADING" and s.get("baseAsset")
                }
                if tokens:
                    return tokens
        elif exchange == "Gate.io":
            r = requests.get("https://api.gateio.ws/api/v4/spot/currency_pairs", timeout=8)
            if r.status_code == 200:
                return {str(p.get("base") or "").upper() for p in r.json() if p.get("base")}
        elif exchange == "Coinbase":
            r = requests.get("https://api.exchange.coinbase.com/products", timeout=8)
            if r.status_code == 200:
                return {str(p.get("base_currency") or "").upper() for p in r.json() if p.get("base_currency")}
        elif exchange == "OKX":
            r = requests.get("https://www.okx.com/api/v5/public/instruments?instType=SPOT", timeout=8)
            if r.status_code == 200:
                return {str(p.get("baseCcy") or "").upper() for p in r.json().get("data", []) if p.get("baseCcy")}
        elif exchange == "Bybit":
            r = requests.get("https://api.bybit.com/v5/market/instruments-info?category=spot", timeout=8)
            if r.status_code == 200:
                return {str(p.get("baseCoin") or "").upper() for p in r.json().get("result", {}).get("list", []) if p.get("baseCoin")}
        elif exchange == "Kraken":
            r = requests.get("https://api.kraken.com/0/public/Assets", timeout=8)
            if r.status_code == 200:
                return {str(k).upper().lstrip("XZ") for k in r.json().get("result", {}).keys()}
    except Exception:
        pass
    return set()


def _load_live_listing_fallbacks(log=None) -> Dict[str, set]:
    """Load live listed tokens from all major exchange public APIs."""
    exchanges = ("Binance", "Gate.io", "Coinbase", "OKX", "Bybit", "Kraken")
    out: Dict[str, set] = {}
    for exchange in exchanges:
        if exchange in _LIVE_LISTING_CACHE:
            out[exchange] = _LIVE_LISTING_CACHE[exchange]
            continue
        tokens = _fetch_live_tokens(exchange)
        tokens.update(STATIC_LIVE_LISTING_FALLBACKS.get(exchange, set()))
        _LIVE_LISTING_CACHE[exchange] = tokens
        out[exchange] = tokens
        if log and tokens:
            log.info("Live listings carregados: %s (%s tokens)", exchange, len(tokens))
    return out

def _is_listed_on_own_exchange(row: Dict[str, Any], listed_tokens: Dict[str, set]) -> bool:
    exchange = _normalize_exchange(str(row.get("exchange") or ""))
    candidates = _token_candidates(str(row.get("token") or ""))
    if not exchange or not candidates:
        return False
    listed = listed_tokens.get(exchange, set())
    if any(token in listed for token in candidates):
        return True
    live_tokens = _load_live_listing_fallbacks().get(exchange, set())
    if live_tokens:
        listed_tokens.setdefault(exchange, set()).update(live_tokens)
        return any(token in live_tokens for token in candidates)
    return False

def _is_raw_arkham_row(row: Dict[str, Any]) -> bool:
    signature = str(row.get("signature") or "").lower()
    token_address = str(row.get("token_address") or "").lower()
    row_type = str(row.get("type") or "").lower()
    return (
        signature.startswith("arkham-")
        or token_address.startswith("arkham:")
        or row_type.startswith("arkham_")
    )

def _filter_prediction_rows(
    rows: List[Dict[str, Any]],
    listed_tokens: Dict[str, set],
    min_score: float = 50,
    log=None,
) -> List[Dict[str, Any]]:
    filtered = []
    excluded_listed = []
    for row in rows:
        if _is_raw_arkham_row(row):
            continue
        if _score(row) < min_score or _is_test_token(row):
            continue
        if _is_listed_on_own_exchange(row, listed_tokens):
            excluded_listed.append(f"{row.get('token')}@{_normalize_exchange(row.get('exchange'))}")
            continue
        filtered.append(_apply_listing_score(row))
    if log and excluded_listed:
        log.info("Predictions excluidas por ja estarem listadas na propria exchange: %s", ", ".join(excluded_listed[:20]))
    return _dedupe_latest_predictions(filtered)

def _merge_prediction_backfill(recent: List[Dict[str, Any]], fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined = list(recent)
    seen = {
        "|".join([
            str(row.get("exchange") or ""),
            str(row.get("token_address") or row.get("token") or ""),
            str(row.get("chain") or ""),
        ]).lower()
        for row in combined
    }
    for row in fallback:
        key = "|".join([
            str(row.get("exchange") or ""),
            str(row.get("token_address") or row.get("token") or ""),
            str(row.get("chain") or ""),
        ]).lower()
        if key in seen:
            continue
        combined.append(row)
        seen.add(key)
        if len(combined) >= PREDICTIONS_LIMIT:
            break
    return combined

class AskIn(BaseModel):
    prompt: str

@router.get("/alerts/health")
def alerts_health():
    import logging
    log = logging.getLogger("vigia")
    
    # Usa supa.ok() que recarrega automaticamente
    is_ok = supa.ok()
    
    # Obtém valores usando as funções do supa se disponíveis
    if hasattr(supa, '_get_url') and hasattr(supa, '_get_key'):
        supabase_url = supa._get_url()
        supabase_key = supa._get_key()
    else:
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE", "")
    
    log.info(f"🔍 Health check: URL={'✅' if supabase_url else '❌'}, KEY={'✅' if supabase_key else '❌'}, supa.ok()={is_ok}")
    
    return {
        "ok": True,
        "ts": int(time.time()),
        "supabase_url": bool(supabase_url),
        "has_key": bool(supabase_key),
        "supabase_url_length": len(supabase_url) if supabase_url else 0,
        "supabase_key_length": len(supabase_key) if supabase_key else 0,
        "supa_ok": is_ok
    }

@router.post("/alerts/test-insert")
def test_insert():
    """
    Endpoint de teste para inserir um registo de teste na tabela.
    Útil para verificar se a inserção funciona.
    """
    import logging
    from datetime import datetime, timezone
    
    log = logging.getLogger("vigia")
    
    if not supa.ok():
        return {"ok": False, "error": "Supabase não configurado"}
    
    try:
        from supabase import create_client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE")
        supabase_client = create_client(supabase_url, supabase_key)
        
        test_data = {
            "type": "holding",
            "exchange": "Binance",
            "token": "TEST",
            "token_address": "TestAddress123",
            "chain": "solana",
            "score": 75.5,
            "value_usd": 50000.0,
            "liquidity": 1000000.0,
            "volume_24h": 500000.0,
            "ts": datetime.now(timezone.utc).isoformat(),
            "pair_url": "https://dexscreener.com/test",
            "analysis_text": "Teste de inserção via API",
            "ai_analysis": "Este é um registo de teste inserido via endpoint /alerts/test-insert"
        }
        
        log.info("Inserindo dados de teste...")
        response = supabase_client.table("transacted_tokens").insert(test_data).execute()
        
        if hasattr(response, 'data') and response.data:
            return {
                "ok": True,
                "message": "Dados de teste inseridos com sucesso",
                "id": response.data[0].get('id'),
                "data": test_data
            }
        else:
            return {"ok": False, "error": "Resposta sem dados", "response": str(response)}
            
    except Exception as e:
        log.error(f"Erro ao inserir dados de teste: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}

@router.get("/alerts/holdings")
def get_holdings():
    """
    Devolve os holdings atuais (tabela transacted_tokens) — último snapshot por token/exchange.
    """
    import logging
    log = logging.getLogger("vigia")
    
    if not supa.ok():
        log.warning("Supabase não configurado")
        return {"ok": False, "error": "Supabase não configurado", "items": []}

    try:
        # 1) Trazer últimas linhas por (exchange, token, chain, type='holding')
        params = {
            "type": "eq.holding",
            "select": "exchange,token,token_address,chain,score,ts,listed_exchanges,analysis_text,ai_analysis,pair_url,value_usd,liquidity,volume_24h",
            "limit": "500",
            "order": "ts.desc"
        }
        
        log.info("Buscando holdings do Supabase...")
        r = supa.rest_get("transacted_tokens", params=params, timeout=8)
        
        if r.status_code != 200:
            error_msg = r.text[:200] if hasattr(r, 'text') else str(r.status_code)
            log.error(f"Erro ao buscar holdings: HTTP {r.status_code} - {error_msg}")
            return {"ok": False, "error": error_msg, "items": []}

        data: List[Dict[str, Any]] = r.json() or []
        log.info(f"Recebidos {len(data)} holdings do Supabase")

        # 2) Deduplicar por (exchange, token, chain) pegando o mais recente
        latest: Dict[str, Dict[str, Any]] = {}
        for row in data:
            k = f"{row.get('exchange')}|{row.get('token')}|{row.get('chain')}"
            if k not in latest:
                latest[k] = row
            else:
                prev_ts = latest[k].get("ts") or ""
                cur_ts  = row.get("ts") or ""
                if cur_ts > prev_ts:
                    latest[k] = row

        items = list(latest.values())
        # Ordena por score desc depois ts desc
        items.sort(key=lambda x: (float(x.get("score") or 0), str(x.get("ts") or "")), reverse=True)
        
        log.info(f"Holdings deduplicados: {len(items)}")

        return {"ok": True, "count": len(items), "items": items}
        
    except Exception as e:
        log.error(f"Erro ao processar holdings: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "items": []}

@router.get("/alerts/prelisting-watchlist")
def get_prelisting_watchlist():
    """
    Tokens investigados manualmente com sinais pre-listing fortes (listing_ts IS NULL).
    Dados de token_prelisting_wallets onde a investigacao identificou acumulacao antes do listing.
    """
    import logging
    log = logging.getLogger("vigia")

    if not supa.ok():
        return {"ok": False, "error": "Supabase nao configurado", "items": []}

    try:
        params = {
            "listing_ts": "is.null",
            "select": "token,token_id,listing_exchange,score,classification,labels,raw,address,investigation_status",
            "order": "score.desc",
            "limit": "200",
        }
        r = supa.rest_get("token_prelisting_wallets", params=params, timeout=8)
        if r.status_code != 200:
            log.warning("Prelisting watchlist: HTTP %s", r.status_code)
            return {"ok": False, "error": r.text[:200], "items": []}

        rows = r.json() or []

        # Group by token
        by_token: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            tok = str(row.get("token") or "").upper()
            if not tok:
                continue
            if tok not in by_token:
                by_token[tok] = {
                    "token": tok,
                    "token_id": row.get("token_id"),
                    "listing_exchange": str(row.get("listing_exchange") or "").replace(" (pending)", ""),
                    "max_score": 0,
                    "wallet_count": 0,
                    "classifications": [],
                    "labels": [],
                    "investigation_status": row.get("investigation_status") or "candidate",
                    "source": "prelisting_scanner",
                }
            entry = by_token[tok]
            score = int(row.get("score") or 0)
            if score > entry["max_score"]:
                entry["max_score"] = score
            entry["wallet_count"] += 1
            cls = row.get("classification") or ""
            if cls and cls not in entry["classifications"]:
                entry["classifications"].append(cls)
            for label in (row.get("labels") or []):
                if label and label not in entry["labels"]:
                    entry["labels"].append(label)

        items = sorted(by_token.values(), key=lambda x: -x["max_score"])
        return {"ok": True, "count": len(items), "items": items}

    except Exception as e:
        log.error("Prelisting watchlist error: %s", e, exc_info=True)
        return {"ok": False, "error": str(e), "items": []}


@router.get("/alerts/smart-money")
def get_smart_money(limit: int = 10):
    """
    Devolve movimentos relevantes de insiders/market makers via Arkham.
    Nao chama reducoes de venda: pode ser venda, pool, bridge ou transferencia.
    """
    import logging
    log = logging.getLogger("vigia")

    if not supa.ok():
        log.warning("Supabase nao configurado")
        return {"ok": False, "error": "Supabase nao configurado", "items": []}

    try:
        safe_limit = max(1, min(int(limit or 10), 25))
        select_cols = (
            "id,signal_key,entity,entity_type,token,token_address,chain,amount,value_usd,"
            "previous_value_usd,value_delta_usd,value_delta_pct,previous_amount,"
            "amount_delta,signal_direction,score,exchange_count,pair_url,analysis_text,ts"
        )
        # Fetch smart_money signals
        params_sm = {
            "entity_type": "eq.smart_money",
            "signal_direction": "in.(new,increased,decreased)",
            "select": select_cols,
            "limit": "400",
            "order": "ts.desc",
        }
        r_sm = supa.rest_get("arkham_signals", params=params_sm, timeout=8)
        # Fetch insider signals (in/out activity from prelisting_investigation wallets)
        params_ins = {
            "entity_type": "eq.insider",
            "select": select_cols,
            "limit": "100",
            "order": "ts.desc",
        }
        r_ins = supa.rest_get("arkham_signals", params=params_ins, timeout=8)

        if r_sm.status_code != 200:
            log.warning("Erro ao buscar smart money: HTTP %s - %s", r_sm.status_code, r_sm.text[:200])
            return {"ok": False, "error": r_sm.text[:200], "items": []}

        rows = (r_sm.json() or []) + (r_ins.json() if r_ins.status_code == 200 else [])
        rows = [
            row for row in rows
            if str(row.get("token") or "").strip()
            and (
                str(row.get("signal_direction") or "") in {"new", "increased", "decreased", "in", "out"}
            )
            and str(row.get("token") or "").strip().upper() not in TEST_TOKENS
            and str(row.get("token") or "").strip().upper() not in TOP100_EXCLUDED_SYMBOLS
            and _num(row, "value_usd") <= LISTING_EXCLUDED_MAX_VALUE_USD
        ]
        # Insiders always first, then sort by value within each group
        def _sort_key(row):
            is_insider = 0 if str(row.get("entity_type") or "") == "insider" else 1
            return (is_insider, -abs(_num(row, "value_delta_usd")), -_num(row, "value_usd"))
        rows.sort(key=_sort_key)
        return {"ok": True, "count": len(rows), "items": rows[:safe_limit]}
    except Exception as e:
        log.error("Erro ao processar smart money: %s", e, exc_info=True)
        return {"ok": False, "error": str(e), "items": []}

@router.get("/alerts/predictions")
def get_predictions():
    """
    Lê potenciais listings (holdings com score alto que ainda não foram listados).
    Busca na tabela transacted_tokens com type='holding' e filtra por score alto.
    Retorna lista direta de items (não objeto com ok/items) para compatibilidade com frontend.
    """
    import logging
    log = logging.getLogger("vigia")
    
    if not supa.ok():
        log.warning("Supabase não configurado")
        return []

    try:
        listed_tokens = _load_listed_tokens_map(log)
        # NOTA: transacted_tokens NAO tem coluna `id` (o id existe em arkham_signals).
        # Pedir `id` aqui fazia o Supabase devolver 42703 e a tabela de predictions
        # do site ficava vazia (corrigido a 2026-09-10).
        base_select = "exchange,token,chain,score,ts,listed_exchanges,analysis_text,ai_analysis,pair_url,value_usd,liquidity,volume_24h,token_address"
        # Busca holdings (que são as predictions de potencial listing)
        # Timeout reduzido para 8 segundos para evitar travamentos
        # Limite de 500 registos para evitar queries muito lentas
        params = {
            "type": "eq.holding",
            "select": base_select,
            "limit": "500",
            "order": "ts.desc",
            "ts": f"gte.{_prediction_since_iso()}"
        }
        
        log.info(f"Buscando predictions do Supabase...")
        r = supa.rest_get("transacted_tokens", params=params, timeout=8)
        
        if r.status_code != 200:
            log.error(f"Erro ao buscar predictions: HTTP {r.status_code} - {r.text[:200]}")
            return []

        arkham_data = _fetch_arkham_exchange_predictions(log)
        if arkham_data:
            log.info("Recebidos %s registos Arkham exchange", len(arkham_data))
            data = arkham_data
        else:
            data = r.json() or []
        log.info(f"Recebidos {len(data)} registos para predictions")
        
        # Filtra por score mínimo de 50 e ordena por score desc
        filtered = _filter_prediction_rows(data, listed_tokens, log=log)
        
        log.info(
            "Predictions filtradas (score >= 50, ultimas %sh): %s",
            _prediction_max_age_hours(),
            len(filtered),
        )
        
        # Retorna lista direta (formato esperado pelo frontend)
        return filtered[:PREDICTIONS_LIMIT]
        
    except Exception as e:
        log.error(f"Erro ao processar predictions: {e}", exc_info=True)
        return []

@router.post("/alerts/ask")
def ask_alerts(payload: AskIn):
    if not supa.ok():
        return {"ok": False, "answer": "Supabase nao configurado. Verifica as variaveis de ambiente no Render.", "count": 0, "items": []}

    q = (payload.prompt or "").lower()
    wants_english = _is_english_prompt(payload.prompt)
    log.info("/alerts/ask: %s", payload.prompt)

    is_top100_context = "top100" in q or "top 100" in q
    if _is_top100_buy_question(q):
        return _answer_top100_buy_watchlist(log, payload.prompt)

    # Transferências recentes (movimentos on-chain recentes) vs holdings acumulados
    is_recent_transfer_q = any(t in q for t in [
        "transferencia", "transferência", "transferencias", "transferências",
        "movimento recente", "movimentos recentes", "enviou", "recebeu",
        "ultima hora", "última hora", "ultimas horas", "últimas horas",
        "hoje cedo", "ontem", "recente", "recentes",
    ])
    if is_recent_transfer_q and not is_top100_context and not any(t in q for t in ["acumul", "holding", "detém", "detem"]):
        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r_recent = supa.rest_get("transacted_tokens", params={
            "select": "exchange,token,chain,score,ts,value_usd,pair_url",
            "ts": f"gte.{since_24h}",
            "order": "ts.desc",
            "limit": "20",
        }, timeout=8)
        if r_recent.status_code == 200 and r_recent.json():
            rows = r_recent.json()
            lines = [f"**Movimentos recentes nas wallets de exchanges (últimas 24h) — {len(rows)} entradas**\n"]
            for i, row in enumerate(rows[:10], 1):
                ts = str(row.get("ts") or "")[:16].replace("T", " ")
                lines.append(
                    f"{i}. **{row.get('token')}** · {row.get('exchange')} · {row.get('chain')}\n"
                    f"   Valor: ${float(row.get('value_usd') or 0):,.0f} · {ts} UTC"
                )
            lines.append("\n_Estes são movimentos detectados nas últimas 24h. Para tokens acumulados há mais tempo usa 'tokens que exchanges estão a acumular'._")
            return {"ok": True, "answer": "\n".join(lines), "count": len(rows), "items": rows}
        return {"ok": True, "answer": "Sem movimentos recentes detectados nas últimas 24h.", "count": 0, "items": []}

    # Defaults
    ex_norm = None
    min_score = 0
    chain = None
    is_buy_watchlist_question = _is_buy_watchlist_question(q)

    # Se perguntar sobre "tokens que vão ser listados" sem exchange específica, usa score mínimo
    is_more_listing_question = q.strip() in {"more", "show more", "more please"} or "more listings" in q
    is_listing_question = (
        is_more_listing_question
        or "listados" in q
        or "unlisted" in q
        or "exchange wallet" in q
        or "exchange wallets" in q
        or "listing" in q
        or "vão ser" in q
        or "vao ser" in q
        or "vai ser" in q
        or "achas" in q
    )
    if is_listing_question and not any(ex in q for ex in ["binance", "gate", "bybit", "bitget", "kraken", "okx", "mexc", "coinbase"]):
        min_score = 50  # Score mínimo para predictions
        log.info(f"Detectada pergunta sobre listings - aplicando score mínimo: {min_score}")

    # Inferência simples
    if is_buy_watchlist_question and not any(ex in q for ex in ["binance", "gate", "bybit", "bitget", "kraken", "okx", "mexc", "coinbase"]):
        min_score = max(min_score, 50)
        log.info("Detectada pergunta de watchlist de compra - usando candidatos filtrados")

    if "binance" in q: ex_norm = "Binance"
    if "gate" in q:    ex_norm = "Gate.io"
    if "bybit" in q:   ex_norm = "Bybit"
    if "bitget" in q:  ex_norm = "Bitget"
    if "kraken" in q:  ex_norm = "Kraken"
    if "okx" in q:     ex_norm = "OKX"
    if "mexc" in q:    ex_norm = "MEXC"
    if "coinbase" in q: ex_norm = "Coinbase"

    if "solana" in q:    chain = "solana"
    if "ethereum" in q:  chain = "ethereum"
    if "score >" in q:
        try:
            min_score = int(q.split("score >")[1].split()[0])
        except Exception:
            min_score = 70
    elif "score" in q and ("alto" in q or "elevado" in q):
        min_score = 70

    filter_unlisted = is_listing_question or "nao foram listados" in q or "nÃ£o foram listados" in q or "unlisted" in q
    listed_tokens = _load_listed_tokens_map(log) if filter_unlisted else {}
    if is_buy_watchlist_question and not filter_unlisted:
        filter_unlisted = True
        listed_tokens = _load_listed_tokens_map(log)

    # Base query
    params = {
        "type": "eq.holding",
        "select": "exchange,token,token_address,chain,score,ts,listed_exchanges,pair_url,value_usd,liquidity,volume_24h,analysis_text,ai_analysis",
        "limit": "500",
        "order": "score.desc"
    }
    if chain:
        params["chain"] = f"eq.{chain}"
    if is_listing_question or is_buy_watchlist_question:
        params["ts"] = f"gte.{_prediction_since_iso()}"

    log.info(f"Buscando holdings com params: {params}")
    r = supa.rest_get("transacted_tokens", params=params, timeout=8)
    if r.status_code != 200:
        error_msg = r.text[:200] if hasattr(r, 'text') else str(r.status_code)
        log.error(f"Erro ao buscar holdings: HTTP {r.status_code} - {error_msg}")
        return {"ok": False, "error": error_msg, "answer": f"Erro ao buscar dados: {error_msg}", "count": 0, "items": []}

    data: List[Dict[str, Any]] = r.json() or []
    if is_listing_question or is_buy_watchlist_question:
        arkham_data = _fetch_arkham_exchange_predictions(log)
        if arkham_data:
            data = arkham_data
            log.info("Ask usando %s sinais Arkham exchange", len(arkham_data))
    log.info(f"Recebidos {len(data)} holdings do Supabase")

    # Normalizar exchange → ex_norm
    def norm(ex: str) -> str:
        return EXCHANGE_NORMALIZE.get(ex, ex)

    # Filtrar
    out: List[Dict[str, Any]] = []
    for row in data:
        if _is_test_token(row):
            continue
        if filter_unlisted and _is_listed_on_own_exchange(row, listed_tokens):
            continue
        if ex_norm and norm(row.get("exchange", "")) != ex_norm:
            continue
        if _score(row) < min_score:
            continue

        # “ainda não foram listados” → listed_exchanges não contém ex_norm
        if "nao foram listados" in q or "não foram listados" in q or "unlisted" in q:
            lst = row.get("listed_exchanges") or []
            if not isinstance(lst, list):
                lst = []
            if ex_norm and ex_norm in lst:
                # já listado lá → exclui
                continue

        out.append(row)
    
    log.info(f"Holdings filtrados: {len(out)}")

    out = [_apply_listing_score(row) for row in out]

    # Ordena por score desc
    out = _dedupe_latest_predictions(out)

    if (
        len(out) < PREDICTIONS_LIMIT
        and (is_listing_question or is_buy_watchlist_question)
        and _wants_historical_predictions(q)
    ):
        fallback_params = params.copy()
        fallback_params.pop("ts", None)
        log.info(f"Resultados recentes insuficientes ({len(out)}/{PREDICTIONS_LIMIT}); buscando fallback historico com params: {fallback_params}")
        fallback_r = supa.rest_get("transacted_tokens", params=fallback_params, timeout=8)
        if fallback_r.status_code == 200:
            fallback_out: List[Dict[str, Any]] = []
            for row in fallback_r.json() or []:
                if _is_test_token(row):
                    continue
                if _is_listed_on_own_exchange(row, listed_tokens):
                    continue
                if ex_norm and norm(row.get("exchange", "")) != ex_norm:
                    continue
                if _score(row) < min_score:
                    continue
                fallback_out.append(row)
            fallback_out = [_apply_listing_score(row) for row in fallback_out]
            fallback_out = _dedupe_latest_predictions(fallback_out)
            out = _merge_prediction_backfill(out, fallback_out)
            log.info(f"Ask apos backfill historico: {len(out)}")

    try:
        if len(out) == 0:
            if ex_norm:
                answer = f"Nao encontrei holdings da {ex_norm} que correspondam aos criterios."
            elif is_listing_question:
                answer = "Nao encontrei tokens com potencial de listing nos dados recentes.\n\nO cron de holdings corre diariamente e analisa wallets de exchanges como Binance, Coinbase, Gate.io e Kraken. Se os dados estiverem desatualizados, aguarda o proximo ciclo."
            else:
                answer = "Nao encontrei tokens que correspondam a tua pesquisa."
            return {"ok": True, "answer": answer, "count": 0, "items": []}

        wants_more = is_more_listing_question or any(t in q for t in ["ver mais", "mais listings", "mais sinais", "mostrar mais", "show more", "more listings"])
        display_limit = 10 if wants_more else 3
        shown = out[:display_limit]
        if is_listing_question or "listados" in q or "listing" in q or "acumular" in q:
            header = f"**Sinais on-chain de possíveis listings**\n\n{len(out)} candidatos filtrados. Mostro os {len(shown)} com melhor sinal."
        elif is_buy_watchlist_question:
            header = f"**Watchlist proprietária de hoje**\n\n{len(out)} sinais on-chain filtrados. Mostro os {len(shown)} mais relevantes."
        else:
            header = f"**Top sinais on-chain detetados**\n\n{len(out)} sinais filtrados. Mostro os {len(shown)} mais relevantes."

        def _fmt_ts(ts_val) -> str:
            try:
                if isinstance(ts_val, (int, float)):
                    dt = datetime.fromtimestamp(ts_val / 1000 if ts_val > 1e10 else ts_val, tz=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = now - dt
                if diff.days >= 2:
                    return f"{diff.days}d ago" if wants_english else f"ha {diff.days} dias"
                if diff.days == 1:
                    return "yesterday" if wants_english else "ontem"
                hours = diff.seconds // 3600
                if hours >= 1:
                    return f"{hours}h ago" if wants_english else f"ha {hours}h"
                return "just now" if wants_english else "agora mesmo"
            except Exception:
                return ""

        def _confidence_label(score_val) -> str:
            try:
                s = float(score_val or 0)
            except (TypeError, ValueError):
                return "unknown" if wants_english else "desconhecida"
            if wants_english:
                if s >= 80:
                    return "high"
                if s >= 60:
                    return "moderate"
                return "low"
            if s >= 80:
                return "alta"
            if s >= 60:
                return "moderada"
            return "baixa"

        def _fmt_money(value) -> str:
            try:
                v = float(value or 0)
            except (TypeError, ValueError):
                return "N/A"
            if v <= 0:
                return "N/A"
            if v >= 1_000_000:
                return f"${v / 1_000_000:.1f}M"
            if v >= 1_000:
                return f"${v / 1_000:.0f}K"
            return f"${v:,.0f}"

        def _listing_verdict(score_val) -> str:
            try:
                s = float(score_val or 0)
            except (TypeError, ValueError):
                return "Signal under observation"
            if wants_english:
                if s >= 85:
                    return "Strong listing candidate"
                if s >= 75:
                    return "Good signal to watch"
                if s >= 65:
                    return "Useful signal to monitor"
                return "Early signal, confirm in the next cycles"
            if s >= 85:
                return "Forte candidato a listing"
            if s >= 75:
                return "Bom sinal, merece atencao"
            if s >= 65:
                return "Sinal util para acompanhar"
            return "Sinal inicial, confirmar nos proximos ciclos"

        blocks = []
        for i, item in enumerate(shown, 1):
            token = item.get("token", "N/A")
            exchange = _normalize_exchange(item.get("exchange", "N/A"))
            score = item.get("score", 0)
            value_usd = item.get("value_usd") or 0
            liquidity = item.get("liquidity") or 0
            pair_url = item.get("pair_url", "")
            ts = item.get("last_seen_ts") or item.get("ts")
            chain = (item.get("chain") or "").capitalize()

            block = f"### {i}. {token}"
            block += f" · {exchange}"
            if chain:
                block += f" · {chain}"
            block += "\n\n"

            # Contexto principal: onde apareceu o sinal e quanto vale.
            block += f"**Sinal:** posição relevante detetada numa wallet monitorizada da {exchange}"
            when = _fmt_ts(ts)
            if when:
                block += f" ({when})"
            block += ".\n"

            if value_usd and float(value_usd) > 0:
                block += f"**Exposição:** ${float(value_usd):,.0f}"
                if liquidity and float(liquidity) > 0:
                    block += f" · **Liquidez:** ${float(liquidity):,.0f}"
                block += "\n"

            # Probabilidade de listing
            conf = _confidence_label(score)
            block += f"**Leitura:** probabilidade {conf}"
            if score:
                block += f" (score {float(score):.0f}/100)"
            block += "\n"

            # Link
            if pair_url:
                block += f"[DexScreener]({pair_url})"

            blocks.append(block)

        pretty_blocks = []
        for i, item in enumerate(shown, 1):
            token = item.get("token", "N/A")
            exchange = _normalize_exchange(item.get("exchange", "N/A"))
            chain = (item.get("chain") or "").capitalize()
            score = item.get("score", 0)
            value_usd = item.get("value_usd") or 0
            liquidity = item.get("liquidity") or 0
            volume = item.get("volume_24h") or 0
            pair_url = item.get("pair_url", "")
            ts = item.get("last_seen_ts") or item.get("ts")

            line = f"### {i}. {token} - {exchange}"
            if chain:
                line += f" - {chain}"
            line += "\n\n"
            line += f"**Score:** {float(score or 0):.0f}/100 - **{_listing_verdict(score)}**\n"
            line += f"**Wallet:** {_fmt_money(value_usd)} - **Liquidez:** {_fmt_money(liquidity)}"
            if volume and float(volume or 0) > 0:
                line += f" - **Volume:** {_fmt_money(volume)}"
            line += "\n"

            when = _fmt_ts(ts)
            line += f"Detectado na wallet monitorizada da **{exchange}**"
            if when:
                line += f" ({when})"
            line += ".\n"
            line += f"**Leitura:** probabilidade {_confidence_label(score)}. Monitorizar se a posicao cresce nos proximos ciclos.\n"
            if pair_url:
                line += f"[Ver no DexScreener]({pair_url})"
            pretty_blocks.append(line)

        if pretty_blocks:
            blocks = pretty_blocks
            if is_listing_question or "listados" in q or "listing" in q or "acumular" in q:
                header = f"**Radar on-chain de possiveis listings**\n\n{len(out)} candidatos filtrados. Mostro {len(shown)} sinais fortes."
            elif is_buy_watchlist_question:
                header = f"**Watchlist propria de hoje**\n\n{len(out)} sinais on-chain filtrados. Mostro os {len(shown)} mais relevantes."
            else:
                header = f"**Top sinais on-chain detetados**\n\n{len(out)} sinais filtrados. Mostro os {len(shown)} mais relevantes."

        answer = header + "\n\n" + "\n\n".join(blocks)
        if len(out) > len(shown):
            answer += f"\n\n_+ {len(out) - len(shown)} sinais ocultos. Escreve **ver mais listings** para expandir._"
        if is_listing_question or "listados" in q or "listing" in q or "acumular" in q:
            answer += "\n\n_O radar filtra tokens ja listados na propria exchange e ignora stablecoins/wrapped assets._"

        if wants_english:
            replacements = {
                " - **Liquidez:**": " - **Liquidity:**",
                "**Radar on-chain de possiveis listings**": "**On-chain listing radar**",
                "**Watchlist propria de hoje**": "**Own watchlist today**",
                "**Top sinais on-chain detetados**": "**Top on-chain signals**",
                "candidatos filtrados. Mostro": "filtered candidates. Showing",
                "sinais fortes.": "strong signals.",
                "sinais on-chain filtrados. Mostro os": "filtered on-chain signals. Showing the",
                "mais relevantes.": "most relevant.",
                "sinais filtrados. Mostro os": "filtered signals. Showing the",
                "sinais ocultos. Escreve **ver mais listings** para expandir.": "hidden signals. Type **more listings** to expand.",
                "Detectado na wallet monitorizada da": "Detected in a monitored",
                "**Liquidez:**": "**Liquidity:**",
                "**Leitura:** probabilidade": "**Read:**",
                "Monitorizar se a posicao cresce nos proximos ciclos.": "Watch whether the position keeps growing in the next cycles.",
                "[Ver no DexScreener]": "[Open DexScreener]",
                "_O radar filtra tokens ja listados na propria exchange e ignora stablecoins/wrapped assets._": "_The radar filters tokens already listed on the same exchange and ignores stablecoins/wrapped assets._",
                "Forte candidato a listing": "Strong listing candidate",
                "Bom sinal, merece atencao": "Good signal to watch",
                "Sinal util para acompanhar": "Useful signal to monitor",
                "Sinal inicial, confirmar nos proximos ciclos": "Early signal, confirm in the next cycles",
            }
            for old, new in replacements.items():
                answer = answer.replace(old, new)
            answer = answer.replace(" **Binance**", " **Binance** wallet")
            answer = answer.replace(" **Coinbase**", " **Coinbase** wallet")
            answer = answer.replace(" **Gate.io**", " **Gate.io** wallet")
            answer = answer.replace(" **Bybit**", " **Bybit** wallet")
            answer = answer.replace(" **Bitget**", " **Bitget** wallet")
            answer = answer.replace(" **Kraken**", " **Kraken** wallet")

        return {"ok": True, "answer": answer, "count": len(out), "items": out}

    except Exception as e:
        log.error(f"Erro ao formatar resposta: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "answer": f"Erro ao processar: {str(e)}", "count": 0, "items": []}
