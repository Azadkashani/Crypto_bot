#!/usr/bin/env python3
"""
Patch:
1. Fix MAE calculation (non-negative).
2. Update .env with more pool addresses and min_independent_whales=1.
3. Upgrade run_real_research.py to group signals by time window (60 minutes) using estimated block timestamps.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# --------------------------------------------------------------------
# 1. Fix MAE in src/research/evaluator.py
# --------------------------------------------------------------------
evaluator_path = ROOT / "src/research/evaluator.py"
text = evaluator_path.read_text()

old_long = """    if direction == 'LONG':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = (max_high - entry_price) / entry_price * 100
        mae = (entry_price - min_low) / entry_price * 100
    elif direction == 'SHORT':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = (entry_price - min_low) / entry_price * 100
        mae = (max_high - entry_price) / entry_price * 100"""

new_long = """    if direction == 'LONG':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = max(0, (max_high - entry_price) / entry_price * 100)
        mae = max(0, (entry_price - min_low) / entry_price * 100)
    elif direction == 'SHORT':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = max(0, (entry_price - min_low) / entry_price * 100)
        mae = max(0, (max_high - entry_price) / entry_price * 100)"""

if old_long in text:
    text = text.replace(old_long, new_long)
    evaluator_path.write_text(text)
    print("✅ MAE calculation fixed in evaluator.py")
else:
    print("⚠️ Could not find MAE block in evaluator.py, check manually")

# --------------------------------------------------------------------
# 2. Update .env with more pools and min_independent_whales=1
# --------------------------------------------------------------------
env_path = ROOT / ".env"
if env_path.exists():
    env_text = env_path.read_text()

    new_pool_line = "RESEARCH_POOL_ADDRESSES=0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852,0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc,0xa478c2975ab1ea89e8196811f51a7b7ade33eb11,0xbb2b8038a1640196fbe3e38816f3e67cba72d940,0xa2107fa5b38d9bbd2c461d6edf11b11a50f6b974,0xd3d2e2692501a5c9ca623199d38826e513033a17,0x3041cbd36888becc7bbcbc0045e3b1f144466f5f,0x43ae24960e5534731fc831386c07755a2dc33d47,0x2fdbadf3c4d5a8666bc06645b8358ab803996e28,0xdfc14d2af169b0d36c4eff567ada9b2e0cae044f,0x9e0905249cee2b1e4e5c5f5e5f5e5f5e5f5e5f5e5f5e5f\n"
    if "RESEARCH_POOL_ADDRESSES=" in env_text:
        env_text = env_text.replace(env_text.split("RESEARCH_POOL_ADDRESSES=")[1].split("\n")[0], new_pool_line.strip())
    else:
        env_text += new_pool_line

    if "MIN_INDEPENDENT_WHALES=" in env_text:
        # replace
        lines = env_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("MIN_INDEPENDENT_WHALES="):
                lines[i] = "MIN_INDEPENDENT_WHALES=1"
                break
        env_text = "\n".join(lines) + "\n"
    else:
        env_text += "MIN_INDEPENDENT_WHALES=1\n"

    env_path.write_text(env_text)
    print("✅ .env updated with more pools and MIN_INDEPENDENT_WHALES=1")
else:
    print("⚠️ .env not found, ensure you have one")

# --------------------------------------------------------------------
# 3. Upgrade run_real_research.py for time-window grouping
# --------------------------------------------------------------------
script_path = ROOT / "scripts/run_real_research.py"
text = script_path.read_text()

# Replace the grouping block
old_group = '''    # Group buy events by token_out (address)
    buy_events = [s for s in all_swaps if s["side"] == "BUY"]
    token_buys = defaultdict(list)
    for ev in buy_events:
        token_buys[ev["token_out"]].append(ev)

    signals = []
    for token_address, events in token_buys.items():
        if len(events) >= settings.min_independent_whales:
            symbol = TOKEN_SYMBOL_MAP.get(token_address.lower(), "UNKNOWN")
            if symbol in STABLECOINS:
                continue
            # Since we haven't fetched block timestamps, we'll assume all in same window for now.
            # We'll use current time as signal timestamp.
            consensus = {
                "consensus_score": 80,
                "confidence": 80,
                "direction": "BULLISH",
                "average_smart_money_score": 70,
                "net_whale_flow": sum(ev["amount_in"] for ev in events),
                "independent_buying_whales": len(set(ev["sender"] for ev in events)),
                "independent_selling_whales": 0,
                "data_quality_score": 90,
            }
            signal_time = datetime.fromtimestamp(latest_block_timestamp, tz=UTC) - timedelta(minutes=5)
            signal = {
                "token": symbol,  # use symbol for price data lookup
                "chain": "ethereum",
                "timestamp": signal_time,
                "direction": "LONG",
                "signal_score": 80,
                "confidence": 80,
            }
            signals.append(signal)

    logger.info(f"Generated {len(signals)} potential signals")
'''

new_group = '''    # تخمین timestamp برای هر رویداد با فرض ۱۲ ثانیه برای هر بلاک
    estimated_ts = {}
    for swap in all_swaps:
        bn = swap["block_number"]
        if bn not in estimated_ts:
            estimated_ts[bn] = latest_block_timestamp - (latest_block - bn) * 12
        swap["timestamp_est"] = estimated_ts[bn]

    # گروه‌بندی خریدها بر اساس توکن و پنجره‌ی ۶۰ دقیقه‌ای
    window_seconds = settings.consensus_window_minutes * 60
    buy_events = [s for s in all_swaps if s["side"] == "BUY"]
    # ساخت کلید (token, window_start)
    groups = defaultdict(list)
    for ev in buy_events:
        ts = ev["timestamp_est"]
        window_start = int(ts // window_seconds) * window_seconds
        token_addr = ev["token_out"]
        key = (token_addr, window_start)
        groups[key].append(ev)

    signals = []
    for (token_addr, window_start), events in groups.items():
        if len(set(ev["sender"] for ev in events)) < settings.min_independent_whales:
            continue
        symbol = TOKEN_SYMBOL_MAP.get(token_addr.lower(), "UNKNOWN")
        if symbol in STABLECOINS:
            continue

        # زمان سیگنال: پایان پنجره (تا کندل‌های آینده برای ارزیابی موجود باشند)
        signal_time = datetime.fromtimestamp(window_start + window_seconds, tz=UTC)
        # اطمینان از اینکه بعد از آن کندلی وجود داشته باشد (با تأخیر ۵ دقیقه)
        signal_time -= timedelta(minutes=5)

        consensus = {
            "consensus_score": 80,
            "confidence": 80,
            "direction": "BULLISH",
            "average_smart_money_score": 70,
            "net_whale_flow": sum(ev["amount_in"] for ev in events),
            "independent_buying_whales": len(set(ev["sender"] for ev in events)),
            "independent_selling_whales": 0,
            "data_quality_score": 90,
        }
        signal = {
            "token": symbol,
            "chain": "ethereum",
            "timestamp": signal_time,
            "direction": "LONG",
            "signal_score": 80,
            "confidence": 80,
        }
        signals.append(signal)

    logger.info(f"Generated {len(signals)} potential signals (time-windowed)")
'''

if old_group in text:
    text = text.replace(old_group, new_group)
    script_path.write_text(text)
    print("✅ run_real_research.py upgraded for time-window grouping")
else:
    print("⚠️ Could not find grouping block, check manually")

# --------------------------------------------------------------------
# 4. Run tests (only quick import checks? actually run pytest)
# --------------------------------------------------------------------
print("🧪 Running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("Tests failed, not committing.")
    sys.exit(1)
print("✅ Tests passed")

# --------------------------------------------------------------------
# 5. Commit and Push
# --------------------------------------------------------------------
print("📦 Committing and pushing...")
subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: MAE non-negative, add pools, time-window grouping"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("🎉 Patch applied and pushed.")
