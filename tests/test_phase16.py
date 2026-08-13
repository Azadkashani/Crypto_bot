import pytest
import copy
import math

import signal_scoring
from signal_scoring import calculate_score, rank_signals, select_best_signal, MIN_24H_VOLUME_USDT


def _make_signal(symbol="BTC/USDT:USDT", direction="LONG", volume=2_000_000.0,
                 score_extra=None, **kwargs):
    """ساخت سیگنال تستی معتبر."""
    signal = {
        "signal": direction,
        "valid": True,
        "symbol": symbol,
        "volume_24h_usdt": volume,
        "regime_4h": "BULLISH" if direction == "LONG" else "BEARISH",
        "regime_1h": "BULLISH" if direction == "LONG" else "BEARISH",
        "rsi_recovery": True,
        "choch": True,
        "bos": True,
        "risk_reward": 2.0,
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
    }
    signal.update(kwargs)
    if score_extra:
        signal.update(score_extra)
    return signal


def test_single_valid_signal():
    signal = _make_signal()
    score = calculate_score(signal)
    assert score is not None
    assert 0.0 <= score <= 100.0


def test_multiple_signals_are_ranked():
    signals = [
        _make_signal(symbol="BTC/USDT:USDT", volume=2_000_000.0),
        _make_signal(symbol="ETH/USDT:USDT", volume=3_000_000.0),
        _make_signal(symbol="SOL/USDT:USDT", volume=10_000_000.0),
    ]
    ranked = rank_signals(signals)
    assert len(ranked) == 3
    # بالاترین حجم بالاترین امتیاز
    assert ranked[0]["symbol"] == "SOL/USDT:USDT"
    assert ranked[0]["score"] >= ranked[-1]["score"]


def test_best_signal_selected():
    signals = [
        _make_signal(symbol="BTC/USDT:USDT", volume=2_000_000.0),
        _make_signal(symbol="ETH/USDT:USDT", volume=3_000_000.0),
        _make_signal(symbol="SOL/USDT:USDT", volume=10_000_000.0),
    ]
    best = select_best_signal(signals)
    assert best["signal"] == "LONG"
    assert best["symbol"] == "SOL/USDT:USDT"


def test_no_valid_signals_returns_none():
    best = select_best_signal([])
    assert best["signal"] == "NONE"


def test_low_volume_signal_rejected():
    signal = _make_signal(volume=999_999.0)
    score = calculate_score(signal)
    assert score is None

    ranked = rank_signals([signal])
    assert ranked == []


def test_volume_exactly_one_million_allowed():
    signal = _make_signal(volume=1_000_000.0)
    score = calculate_score(signal)
    assert score is not None
    assert score >= 0.0


def test_volume_above_one_million_allowed():
    signal = _make_signal(volume=1_500_000.0)
    score = calculate_score(signal)
    assert score is not None


def test_invalid_signal_not_scored():
    signal = _make_signal()
    signal["valid"] = False
    assert calculate_score(signal) is None


def test_score_range():
    signals = [
        _make_signal(symbol="BTC/USDT:USDT", volume=1_000_000.0),
        _make_signal(symbol="ETH/USDT:USDT", volume=20_000_000.0),
        _make_signal(symbol="SOL/USDT:USDT", volume=5_000_000.0),
    ]
    for s in signals:
        score = calculate_score(s)
        assert score is not None
        assert 0.0 <= score <= 100.0


def test_deterministic_score():
    s1 = _make_signal()
    s2 = copy.deepcopy(s1)
    assert calculate_score(s1) == calculate_score(s2)


def test_deterministic_tie_break():
    # دو سیگنال با امتیاز یکسان، نمادها متفاوت
    sig1 = _make_signal(symbol="AAA/USDT:USDT", volume=2_000_000.0)
    sig2 = _make_signal(symbol="ZZZ/USDT:USDT", volume=2_000_000.0)

    # با تغییر rsi_recovery و bos یکسان نگه می‌داریم
    ranked = rank_signals([sig2, sig1])
    # چون امتیازها یکسان هستند، ترتیب نماد صعودی تعیین می‌کند
    assert ranked[0]["symbol"] == "AAA/USDT:USDT"
    assert ranked[1]["symbol"] == "ZZZ/USDT:USDT"


def test_high_score_beats_low_score():
    low = _make_signal(symbol="BTC/USDT:USDT", volume=1_000_000.0)
    high = _make_signal(symbol="ETH/USDT:USDT", volume=20_000_000.0)
    assert calculate_score(high) > calculate_score(low)


def test_volume_filter_before_ranking():
    signals = [
        _make_signal(symbol="BTC/USDT:USDT", volume=999_999.0),
        _make_signal(symbol="ETH/USDT:USDT", volume=1_000_000.0),
    ]
    ranked = rank_signals(signals)
    assert len(ranked) == 1
    assert ranked[0]["symbol"] == "ETH/USDT:USDT"


def test_only_one_best_signal_selected():
    signals = [
        _make_signal(symbol="BTC/USDT:USDT", volume=2_000_000.0),
        _make_signal(symbol="ETH/USDT:USDT", volume=2_000_000.0),
        _make_signal(symbol="SOL/USDT:USDT", volume=2_000_000.0),
    ]
    best = select_best_signal(signals)
    assert best is not None
    # فقط یک سیگنال برگردانده می‌شود (نه لیست)
    assert isinstance(best, dict)
    assert "symbol" in best


def test_strategy_validation_not_bypassed():
    invalid = _make_signal(symbol="BTC/USDT:USDT", volume=2_000_000.0)
    invalid["valid"] = False
    # حتی اگر بقیه فاکتورها قوی باشند، نباید امتیاز بگیرد
    assert calculate_score(invalid) is None


def test_risk_gate_not_bypassed():
    # سیگنالی که از نظر ساختاری نامعتبر است (مثلاً stop بالای entry)
    invalid = _make_signal(symbol="BTC/USDT:USDT", direction="LONG",
                           entry_price=100.0, stop_loss=110.0, take_profit=120.0,
                           volume=2_000_000.0)
    # چون ریسک نامعتبر است، امتیاز نباید محاسبه شود
    assert calculate_score(invalid) is None


def test_no_order_created_by_ranking():
    # تست که ranking هیچ سفارشی ایجاد نمی‌کند
    signals = [_make_signal()]
    ranked = rank_signals(signals)
    assert isinstance(ranked, list)
    for item in ranked:
        assert "order_id" not in item
        assert "order" not in item
