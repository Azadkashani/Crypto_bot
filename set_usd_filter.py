#!/usr/bin/env python3
"""
Patch: Add USD value calculation and filter by real USD (>=500000)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel}")

script_path = ROOT / "scripts/run_real_research.py"
text = script_path.read_text()

# --------------------------------------------------------------------
# 1. Add TOKEN_DECIMALS after STABLECOINS
# --------------------------------------------------------------------
if "TOKEN_DECIMALS" not in text:
    insert_after = "STABLECOINS = {\"USDT\", \"USDC\", \"DAI\", \"TUSD\", \"BUSD\", \"FRAX\"}\n"
    idx = text.index(insert_after) + len(insert_after)
    decimals_code = '''TOKEN_DECIMALS = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": 18,  # WETH
    "0xdac17f958d2ee523a2206206994597c13d831ec7": 6,   # USDT
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": 6,   # USDC
    "0x6b175474e89094c44da98b954eedeac495271d0f": 18,  # DAI
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": 8,   # WBTC
    "0x514910771af9ca656af840dff83e8264ecf986ca": 18,  # LINK
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": 18,  # UNI
    "0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f": 18,  # SNX
    "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e": 18,  # YFI
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": 18,  # AAVE
    "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce": 18,  # SHIB
    "0x6982508145454ce325ddbe47a25d4ec3d2311933": 18,  # PEPE
    "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": 18,  # MATIC
}

'''
    text = text[:idx] + decimals_code + text[idx:]
    print("✅ TOKEN_DECIMALS اضافه شد.")
else:
    print("ℹ️ TOKEN_DECIMALS قبلاً وجود دارد.")

# --------------------------------------------------------------------
# 2. Add token price fetching before pool scanning
# --------------------------------------------------------------------
old_scan_start = "    latest_block = await rpc.fetch_block_number()\n"
new_scan_start = '''    latest_block = await rpc.fetch_block_number()

    # دریافت قیمت‌های لحظه‌ای توکن‌ها از Gate.io
    token_prices = {}
    for addr, symbol in TOKEN_SYMBOL_MAP.items():
        if symbol in STABLECOINS:
            token_prices[symbol] = 1.0
            continue
        try:
            ticker = await gate.get_futures_ticker(f"{symbol}_USDT")
            if ticker and 'last' in ticker:
                token_prices[symbol] = float(ticker['last'])
            else:
                token_prices[symbol] = 0.0
        except Exception as e:
            logger.warning(f"Could not fetch price for {symbol}: {e}")
            token_prices[symbol] = 0.0
    logger.info(f"Fetched prices for {len(token_prices)} tokens")

'''
if old_scan_start in text:
    text = text.replace(old_scan_start, new_scan_start, 1)
    print("✅ دریافت قیمت‌ها اضافه شد.")
else:
    print("⚠️ نقطه‌ی شروع اسکن یافت نشد.")

# --------------------------------------------------------------------
# 3. Add USD calculation in swap parsing
# --------------------------------------------------------------------
old_usd_add = '''                parsed.update({
                    "token_in": token_in,
                    "token_out": token_out,
                    "symbol_in": symbol_in,
                    "symbol_out": symbol_out,
                    "side": side,
                    "amount_in": parsed["amount0_in"] if side == "BUY" else parsed["amount1_in"],
                    "amount_out": parsed["amount1_out"] if side == "BUY" else parsed["amount0_out"],
                    "token0": token0,
                    "token1": token1,
                })'''
new_usd_add = '''                # محاسبه USD
                token_in_decimals = TOKEN_DECIMALS.get(token_in.lower(), 18)
                amount_in_raw = parsed["amount0_in"] if side == "BUY" else parsed["amount1_in"]
                if symbol_in in STABLECOINS:
                    usd_value = amount_in_raw / (10 ** token_in_decimals)
                else:
                    price = token_prices.get(symbol_in, 0.0)
                    if price > 0:
                        usd_value = (amount_in_raw / (10 ** token_in_decimals)) * price
                    else:
                        usd_value = 0.0

                parsed.update({
                    "token_in": token_in,
                    "token_out": token_out,
                    "symbol_in": symbol_in,
                    "symbol_out": symbol_out,
                    "side": side,
                    "amount_in": amount_in_raw,
                    "amount_out": parsed["amount1_out"] if side == "BUY" else parsed["amount0_out"],
                    "token0": token0,
                    "token1": token1,
                    "usd_value": usd_value,
                })'''

if old_usd_add in text:
    text = text.replace(old_usd_add, new_usd_add, 1)
    print("✅ محاسبه USD اضافه شد.")
else:
    print("⚠️ بخش محاسبه USD یافت نشد.")

# --------------------------------------------------------------------
# 4. Change signal filtering to use usd_value
# --------------------------------------------------------------------
old_filter = '''    signals = []
    # حداقل حجم خرید (مجموع amount_in خام) برای تولید سیگنال
    MIN_BUY_VOLUME = 500000  # می‌توانید از settings استفاده کنید، فعلاً ثابت

    for (token_addr, window_start), events in groups.items():
        # فیلتر تعداد کیف پول مستقل
        if len(set(ev["sender"] for ev in events)) < settings.min_independent_whales:
            continue
        symbol = TOKEN_SYMBOL_MAP.get(token_addr.lower(), "UNKNOWN")
        if symbol in STABLECOINS:
            continue
        # فیلتر حداقل حجم خرید
        total_buy_amount = sum(ev["amount_in"] for ev in events)
        if total_buy_amount < MIN_BUY_VOLUME:
            logger.info(f"Skipping {symbol} window {window_start}: total buy amount {total_buy_amount} < {MIN_BUY_VOLUME}")
            continue
'''

new_filter = '''    signals = []
    # حداقل حجم خرید USD برای تولید سیگنال
    MIN_BUY_USD = 500000

    for (token_addr, window_start), events in groups.items():
        # فیلتر تعداد کیف پول مستقل
        if len(set(ev["sender"] for ev in events)) < settings.min_independent_whales:
            continue
        symbol = TOKEN_SYMBOL_MAP.get(token_addr.lower(), "UNKNOWN")
        if symbol in STABLECOINS:
            continue
        # فیلتر حداقل حجم خرید USD
        total_buy_usd = sum(ev.get("usd_value", 0.0) for ev in events)
        if total_buy_usd < MIN_BUY_USD:
            logger.info(f"Skipping {symbol} window {window_start}: total buy USD {total_buy_usd:.2f} < {MIN_BUY_USD}")
            continue
'''

if old_filter in text:
    text = text.replace(old_filter, new_filter, 1)
    print("✅ فیلتر USD اعمال شد.")
else:
    print("⚠️ بخش فیلتر یافت نشد، شاید قبلاً تغییر کرده است.")

# ذخیره فایل
script_path.write_text(text)

# --------------------------------------------------------------------
# 5. اجرای syntax check
# --------------------------------------------------------------------
print("🧪 بررسی صحت syntax...")
res = subprocess.run([sys.executable, "-m", "py_compile", "scripts/run_real_research.py"], cwd=ROOT)
if res.returncode != 0:
    print("❌ خطا در syntax")
    sys.exit(1)
print("✅ Syntax OK")

# --------------------------------------------------------------------
# 6. Commit و Push
# --------------------------------------------------------------------
print("📦 Commit و Push...")
subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "feat: add USD value calculation and filter by real USD (>=500000)"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("🎉 تغییرات اعمال و Push شد.")
