import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta

import walk_forward
from walk_forward import generate_walk_forward_windows, run_walk_forward


# ---------- داده‌های ساختگی ----------

def _make_data_5m(n: int, start='2025-01-01') -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=n, freq='5min', tz='UTC')
    df = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 100,
    }, index=idx)
    return df


def _make_data_1h(n: int, start='2025-01-01') -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=n, freq='1h', tz='UTC')
    df = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 100,
    }, index=idx)
    return df


def _make_data_4h(n: int, start='2025-01-01') -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=n, freq='4h', tz='UTC')
    df = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.0,
        'volume': 100,
    }, index=idx)
    return df


# ---------- Fake BacktestEngine برای تست‌های Walk-Forward ----------

class FakeTradeEngine:
    """
    موتور بک‌تست جعلی که برای هر کندل ۵ دقیقه‌ای یک معامله ساختگی با PnL مثبت
    تولید می‌کند تا امکان آزمایش فیلتر پنجره‌ها فراهم شود.
    """
    def __init__(self, data_5m, data_1h, data_4h, initial_balance):
        self.data_5m = data_5m
        self.data_1h = data_1h
        self.data_4h = data_4h
        self.initial_balance = initial_balance

    def run(self):
        trades = []
        for ts in self.data_5m.index:
            trades.append({
                "direction": "LONG",
                "entry_time": ts,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "position_size": 1.0,
                "risk_amount": 10.0,
                "exit_time": ts + timedelta(minutes=5),
                "exit_price": 101.0,
                "exit_reason": "TP",
                "pnl": 1.0,
                "r_multiple": 0.1,
            })
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.initial_balance + len(trades),
            "net_profit": len(trades),
            "total_trades": len(trades),
            "winning_trades": len(trades),
            "losing_trades": 0,
            "win_rate": 100.0,
            "profit_factor": float('inf'),
            "max_drawdown": 0.0,
            "average_r": 0.1,
            "trades": trades,
        }


# ---------- تست‌ها ----------

def test_valid_expanding_windows():
    windows = generate_walk_forward_windows(100, 30, 10)
    assert len(windows) == 7
    assert windows[0]["train_start"] == 0
    assert windows[0]["train_end"] == 29
    assert windows[0]["test_start"] == 30
    assert windows[0]["test_end"] == 39
    assert windows[1]["train_end"] == 39
    assert windows[1]["test_start"] == 40


def test_correct_train_test_boundaries():
    windows = generate_walk_forward_windows(50, 20, 5)
    assert windows[0]["train_start"] == 0
    assert windows[0]["train_end"] == 19
    assert windows[0]["test_start"] == 20
    assert windows[0]["test_end"] == 24


def test_correct_step_size():
    windows = generate_walk_forward_windows(100, 30, 10, step_size=20)
    assert len(windows) == 4
    assert windows[1]["test_start"] == 50
    assert windows[1]["test_end"] == 59


def test_chronological_ordering():
    windows = generate_walk_forward_windows(80, 20, 5)
    for i in range(len(windows) - 1):
        assert windows[i]["test_end"] < windows[i + 1]["test_start"]


def test_no_shuffled_data():
    windows = generate_walk_forward_windows(60, 10, 5)
    starts = [w["test_start"] for w in windows]
    assert starts == sorted(starts)


def test_insufficient_data():
    result = run_walk_forward(
        _make_data_5m(10), _make_data_1h(5), _make_data_4h(3),
        train_size=20, test_size=5
    )
    assert result["aggregated"]["total_windows"] == 0
    assert result["windows"] == []


def test_invalid_train_size():
    with pytest.raises(ValueError):
        generate_walk_forward_windows(100, 0, 10)


def test_invalid_test_size():
    with pytest.raises(ValueError):
        generate_walk_forward_windows(100, 20, 0)


def test_invalid_step_size():
    with pytest.raises(ValueError):
        generate_walk_forward_windows(100, 20, 10, step_size=0)


def test_duplicate_timestamps_rejected():
    df = _make_data_5m(5)
    df.index = list(df.index[:4]) + [df.index[3]]  # تکراری
    with pytest.raises(ValueError):
        run_walk_forward(df, _make_data_1h(3), _make_data_4h(2), 2, 1)


def test_unsorted_timestamps_rejected():
    df = _make_data_5m(5)
    df = df.iloc[::-1]  # برعکس کردن ترتیب
    with pytest.raises(ValueError):
        run_walk_forward(df, _make_data_1h(3), _make_data_4h(2), 2, 1)


def test_5m_primary_timeline():
    data_5m = _make_data_5m(50)
    windows = generate_walk_forward_windows(len(data_5m), 20, 5)
    assert windows[0]["train_end"] == 19
    assert windows[0]["test_start"] == 20


def test_1h_data_remains_independent(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_1h = _make_data_1h(20)
    data_5m = _make_data_5m(30)
    data_4h = _make_data_4h(10)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    assert result["aggregated"]["total_windows"] > 0
    assert data_1h.index.is_monotonic_increasing
    assert data_1h.index.duplicated().sum() == 0


def test_4h_data_remains_independent(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_4h = _make_data_4h(10)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    assert data_4h.index.is_monotonic_increasing
    assert data_4h.index.duplicated().sum() == 0


def test_validation_results_only_cover_test_periods(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    assert result["windows"][0]["total_trades"] == 5
    assert result["windows"][1]["total_trades"] == 5


def test_warmup_context_not_count_as_validation_trades(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(20)
    data_1h = _make_data_1h(10)
    data_4h = _make_data_4h(5)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    assert result["windows"][0]["total_trades"] == 5
    assert result["windows"][0]["test_candles"] == 5


def test_zero_trade_validation_window(monkeypatch):
    class NoTradeEngine:
        def __init__(self, *args, **kwargs):
            pass
        def run(self):
            return {"trades": [], "initial_balance": 1000,
                    "final_balance": 1000, "net_profit": 0}

    monkeypatch.setattr(walk_forward, "BacktestEngine", NoTradeEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    assert result["windows"][0]["total_trades"] == 0
    assert result["windows"][0]["win_rate"] == 0.0


def test_multiple_validation_windows(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(50)
    data_1h = _make_data_1h(30)
    data_4h = _make_data_4h(15)
    result = run_walk_forward(data_5m, data_1h, data_4h, 20, 5)
    assert result["aggregated"]["total_windows"] == 6
    assert result["aggregated"]["total_trades"] == 30


def test_aggregation_of_window_results(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    agg = result["aggregated"]
    assert agg["total_windows"] == 4
    assert agg["total_trades"] == 20
    assert agg["total_net_profit"] == 20.0
    assert agg["average_window_return"] == pytest.approx(5.0)
    assert agg["average_win_rate"] == pytest.approx(1.0)
    assert agg["average_profit_factor"] == float('inf')
    assert agg["average_expectancy"] == pytest.approx(0.1)


def test_profitable_window_ratio(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    agg = result["aggregated"]
    assert agg["profitable_windows"] == agg["total_windows"]
    assert agg["losing_windows"] == 0
    assert agg["profitable_window_ratio"] == pytest.approx(1.0)


def test_best_worst_window_detection(monkeypatch):
    class MixedEngine:
        # شمارندهٔ مشترک بین نمونه‌ها برای تولید نتایج متفاوت
        _counter = 0
        pnl_values = [1.0, 5.0, -2.0, 3.0, 1.0, 5.0]

        def __init__(self, data_5m, data_1h, data_4h, initial_balance):
            self.data_5m = data_5m

        def run(self):
            MixedEngine._counter += 1
            pnl = MixedEngine.pnl_values[(MixedEngine._counter - 1) % len(MixedEngine.pnl_values)]
            trades = []
            if pnl != 0:
                entry_time = self.data_5m.index[-1]  # داخل بازهٔ test
                trades = [{
                    "entry_time": entry_time,
                    "exit_time": entry_time + timedelta(minutes=5),
                    "pnl": pnl,
                    "r_multiple": pnl / 10.0,
                    "risk_amount": 10.0,
                }]
            return {
                "trades": trades,
                "initial_balance": 1000,
                "final_balance": 1000 + pnl,
                "net_profit": pnl,
            }

    monkeypatch.setattr(walk_forward, "BacktestEngine", MixedEngine)
    data_5m = _make_data_5m(40)
    data_1h = _make_data_1h(30)
    data_4h = _make_data_4h(15)
    result = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    agg = result["aggregated"]
    assert agg["worst_window_profit"] == -2.0
    assert agg["best_window_profit"] == 5.0


def test_no_future_validation_data_leakage(monkeypatch):
    captured_slices = []

    class SpyEngine:
        def __init__(self, data_5m, data_1h, data_4h, initial_balance):
            captured_slices.append({
                "5m_last": data_5m.index[-1],
                "5m_len": len(data_5m),
            })
        def run(self):
            return {"trades": [], "initial_balance": 1000,
                    "final_balance": 1000, "net_profit": 0}

    monkeypatch.setattr(walk_forward, "BacktestEngine", SpyEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)
    run_walk_forward(data_5m, data_1h, data_4h, 10, 5)

    assert captured_slices[0]["5m_last"] == data_5m.index[14]
    assert captured_slices[0]["5m_len"] == 15


def test_deterministic_repeated_execution(monkeypatch):
    monkeypatch.setattr(walk_forward, "BacktestEngine", FakeTradeEngine)
    data_5m = _make_data_5m(30)
    data_1h = _make_data_1h(20)
    data_4h = _make_data_4h(10)

    result1 = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)
    result2 = run_walk_forward(data_5m, data_1h, data_4h, 10, 5)

    assert result1["aggregated"] == result2["aggregated"]
    assert result1["windows"] == result2["windows"]


def test_realistic_multi_window_scenario(monkeypatch):
    class RealisticEngine:
        def __init__(self, data_5m, data_1h, data_4h, initial_balance):
            self.data_5m = data_5m
        def run(self):
            trades = []
            for i, ts in enumerate(self.data_5m.index):
                if i % 2 == 0:
                    pnl = 1.0 if i % 4 == 0 else -0.5
                    trades.append({
                        "entry_time": ts,
                        "exit_time": ts + timedelta(minutes=5),
                        "pnl": pnl,
                        "r_multiple": pnl / 5.0,
                        "risk_amount": 5.0,
                    })
            return {
                "trades": trades,
                "initial_balance": 1000,
                "final_balance": 1000 + sum(t['pnl'] for t in trades),
                "net_profit": sum(t['pnl'] for t in trades),
            }

    monkeypatch.setattr(walk_forward, "BacktestEngine", RealisticEngine)
    data_5m = _make_data_5m(60)
    data_1h = _make_data_1h(40)
    data_4h = _make_data_4h(20)

    result = run_walk_forward(data_5m, data_1h, data_4h, 20, 5)
    assert result["aggregated"]["total_windows"] == 8
    assert result["aggregated"]["total_trades"] > 0
    assert result["aggregated"]["profitable_windows"] >= 0
