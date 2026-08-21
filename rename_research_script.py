#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

old = ROOT / "tests/unit/research/test_no_lookahead.py"
new = ROOT / "tests/unit/research/test_backtest_no_lookahead.py"
if old.exists():
    old.rename(new)
    print(f"renamed: {old} -> {new}")
else:
    print("old file not found")

print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: rename research no-lookahead test to unique basename"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and pushed.")
