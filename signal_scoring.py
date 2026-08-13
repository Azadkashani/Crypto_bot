"""
ماژول امتیازدهی و رتبه‌بندی سیگنال‌های معاملاتی.

این ماژول فقط سیگنال‌های معتبر را امتیازدهی می‌کند و بهترین سیگنال را
برای مراحل بعدی انتخاب می‌کند.

هیچ سفارشی در این ماژول ارسال نمی‌شود.
هیچ سیگنالی دوباره تولید نمی‌شود.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import math

import config


MIN_24H_VOLUME_USDT = getattr(config, "MIN_24H_VOLUME_USDT", 1_000_000)

# وزن‌های امتیازدهی (مجموع = 100)
WEIGHTS = {
    "regime": getattr(config, "REGIME_SCORE_WEIGHT", 25),
    "rsi": getattr(config, "RSI_SCORE_WEIGHT", 20),
    "choch": getattr(config, "CHOCH_SCORE_WEIGHT", 20),
    "bos": getattr(config, "BOS_SCORE_WEIGHT", 20),
    "volume": getattr(config, "VOLUME_SCORE_WEIGHT", 10),
    "rr": getattr(config, "RR_SCORE_WEIGHT", 5),
}


def _extract_volume(signal: Dict[str, Any]) -> Optional[float]:
    """استخراج حجم ۲۴ ساعته USDT از سیگنال."""
    raw = None
    for key in ("volume_24h_usdt", "quote_volume", "quoteVolume", "volume"):
        if key in signal:
            raw = signal.get(key)
            break

    if raw is None:
        return None

    try:
        volume = float(raw)
    except (TypeError, ValueError):
        return None

    if math.isnan(volume) or math.isinf(volume):
        return None

    return volume


def _has_valid_price_geometry(signal: Dict[str, Any]) -> bool:
    """
    بررسی هندسه قیمتی پایه برای LONG/SHORT.

    LONG:
        stop_loss < entry_price < take_profit

    SHORT:
        take_profit < entry_price < stop_loss
    """
    direction = signal.get("signal")
    entry = signal.get("entry_price")
    sl = signal.get("stop_loss")
    tp = signal.get("take_profit")

    try:
        entry = float(entry)
        sl = float(sl)
        tp = float(tp)
    except (TypeError, ValueError):
        return False

    if entry <= 0 or sl <= 0 or tp <= 0:
        return False

    if math.isnan(entry) or math.isnan(sl) or math.isnan(tp):
        return False
    if math.isinf(entry) or math.isinf(sl) or math.isinf(tp):
        return False

    if direction == "LONG":
        return sl < entry < tp
    elif direction == "SHORT":
        return tp < entry < sl
    else:
        return False


def _validate_signal(signal: Dict[str, Any]) -> bool:
    """
    بررسی اولیه سیگنال برای ورود به امتیازدهی.

    فقط سیگنال‌هایی مجاز هستند که:
    - valid=True
    - direction = LONG یا SHORT
    - حجم ۲۴ ساعته >= 1_000_000
    - هندسه قیمتی ورود/حد ضرر/حد سود معتبر باشد
    """
    if not isinstance(signal, dict):
        return False

    if signal.get("valid") is not True:
        return False

    direction = signal.get("signal")
    if direction not in ("LONG", "SHORT"):
        return False

    volume = _extract_volume(signal)
    if volume is None:
        return False

    if volume < MIN_24H_VOLUME_USDT:
        return False

    if not _has_valid_price_geometry(signal):
        return False

    return True


def _score_regime(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت هم‌جهتی رژیم 4H/1H."""
    direction = signal.get("signal")
    r4h = signal.get("regime_4h")
    r1h = signal.get("regime_1h")

    if direction == "LONG":
        if r4h == "BULLISH" and r1h == "BULLISH":
            return 100.0
    elif direction == "SHORT":
        if r4h == "BEARISH" and r1h == "BEARISH":
            return 100.0

    return 0.0


def _score_rsi(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت RSI pullback/recovery."""
    rsi_recovery = signal.get("rsi_recovery", False)
    if rsi_recovery:
        return 100.0

    rsi_5m = signal.get("rsi_5m")
    if rsi_5m is None:
        return 0.0

    try:
        rsi = float(rsi_5m)
    except (TypeError, ValueError):
        return 0.0

    direction = signal.get("signal")
    if direction == "LONG":
        if rsi <= config.RSI_OVERSOLD:
            return 60.0
        elif rsi < 50:
            return 40.0
        else:
            return 0.0
    else:
        if rsi >= config.RSI_OVERBOUGHT:
            return 60.0
        elif rsi > 50:
            return 40.0
        else:
            return 0.0


def _score_choch(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت CHOCH."""
    return 100.0 if signal.get("choch") is True else 0.0


def _score_bos(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت BOS."""
    return 100.0 if signal.get("bos") is True else 0.0


def _score_volume(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت حجم ۲۴ ساعته USDT (بین 0 تا 100)."""
    volume = _extract_volume(signal)
    if volume is None or volume < MIN_24H_VOLUME_USDT:
        return 0.0

    upper = 10_000_000
    if volume >= upper:
        return 100.0

    return ((volume - MIN_24H_VOLUME_USDT) / (upper - MIN_24H_VOLUME_USDT)) * 100.0


def _score_rr(signal: Dict[str, Any]) -> float:
    """امتیاز کیفیت نسبت ریسک به ریوارد."""
    rr = signal.get("risk_reward")
    if rr is None:
        return 0.0

    try:
        rr = float(rr)
    except (TypeError, ValueError):
        return 0.0

    if rr >= 2.0:
        return 100.0
    elif rr >= 1.0:
        return ((rr - 1.0) / 1.0) * 100.0
    else:
        return 0.0


def calculate_score(signal: Dict[str, Any]) -> Optional[float]:
    """
    محاسبه امتیاز سیگنال در بازه 0 تا 100.

    اگر سیگنال نامعتبر باشد یا حجم آن کمتر از حداقل لازم باشد،
    یا هندسه قیمتی نامعتبر باشد، None برمی‌گردد.
    """
    if not _validate_signal(signal):
        return None

    components = {
        "regime": _score_regime(signal),
        "rsi": _score_rsi(signal),
        "choch": _score_choch(signal),
        "bos": _score_bos(signal),
        "volume": _score_volume(signal),
        "rr": _score_rr(signal),
    }

    total_weight = sum(WEIGHTS.values())
    if total_weight <= 0:
        return 0.0

    weighted_sum = sum(components[key] * WEIGHTS.get(key, 0) for key in components)

    score = weighted_sum / total_weight

    return max(0.0, min(100.0, score))


def rank_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    رتبه‌بندی سیگنال‌های معتبر بر اساس امتیاز.

    ترتیب:
        1. score نزولی
        2. risk_reward نزولی
        3. volume نزولی
        4. symbol صعودی (حروف الفبا)

    فقط سیگنال‌هایی که حجم >= 1M دارند و هندسه قیمت معتبر دارند وارد می‌شوند.
    """
    ranked = []
    for sig in signals:
        score = calculate_score(sig)
        if score is not None:
            copied = sig.copy()
            copied["score"] = score
            ranked.append(copied)

    # برای اطمینان از استفاده درست از حجم، مستقیماً حجم را از کلیدهای شناخته‌شده استخراج می‌کنیم
    def _sort_key(item):
        score = item.get("score", 0.0)
        rr = item.get("risk_reward")
        rr = float(rr) if rr is not None else -1.0
        vol = _extract_volume(item)
        vol = vol if vol is not None else -1.0
        sym = item.get("symbol", "")
        return (-score, -rr, -vol, sym.lower())

    ranked.sort(key=_sort_key)

    return ranked


def select_best_signal(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    انتخاب بهترین سیگنال از میان سیگنال‌های معتبر.

    اگر هیچ سیگنال معتبری وجود نداشته باشد:
        {"signal": "NONE"}
    """
    ranked = rank_signals(signals)
    if not ranked:
        return {"signal": "NONE"}

    return ranked[0]


# برای سازگاری احتمالی با نام‌های دیگر
score_signal = calculate_score
