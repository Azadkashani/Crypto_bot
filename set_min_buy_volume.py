#!/usr/bin/env python3
"""
Patch: Add minimum buy volume filter (500000) to run_real_research.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

script_path = ROOT / "scripts/run_real_research.py"
text = script_path.read_text()

# یافتن بخش گروه‌بندی و تولید سیگنال
old_marker = """    signals = []
    for (token_addr, window_start), events in groups.items():
        if len(set(ev["sender"] for ev in events)) < settings.min_independent_whales:
            continue
        symbol = TOKEN_SYMBOL_MAP.get(token_addr.lower(), "UNKNOWN")
        if symbol in STABLECOINS:
            continue
"""

new_marker = """    signals = []
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
"""

if old_marker in text:
    text = text.replace(old_marker, new_marker)
    script_path.write_text(text)
    print("✅ حداقل حجم خرید ۵۰۰,۰۰۰ اعمال شد.")
else:
    print("⚠️ بخش موردنظر پیدا نشد، بررسی دستی لازم است.")
    sys.exit(1)

# اجرای تست‌ها (فقط syntax check)
print("🧪 بررسی صحت syntax...")
res = subprocess.run([sys.executable, "-m", "py_compile", "scripts/run_real_research.py"], cwd=ROOT)
if res.returncode != 0:
    print("❌ خطا در syntax")
    sys.exit(1)
print("✅ Syntax OK")

# Commit و Push
print("📦 Commit و Push...")
subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "feat: add minimum buy volume filter (500000) to research signals"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("🎉 تغییرات اعمال و Push شد.")
