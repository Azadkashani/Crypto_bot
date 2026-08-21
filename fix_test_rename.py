#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# تغییر نام فایل تست Smart Money برای جلوگیری از تداخل با تست detection
old = ROOT / "tests/unit/smart_money/test_no_lookahead.py"
new = ROOT / "tests/unit/smart_money/test_smart_money_no_lookahead.py"
if old.exists():
    old.rename(new)
    print(f"renamed: {old} -> {new}")
else:
    print("old file not found")

# اجرای تست‌ها
print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

# commit و push
subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: rename test_no_lookahead to unique name in smart_money"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and pushed.")
