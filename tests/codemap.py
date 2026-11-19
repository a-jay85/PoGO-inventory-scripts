#!/usr/bin/env python3
"""Checks the two code maps (.claude/rules/codemap.md, skills/MAP.md) match the code, so a new or renamed function
shows up for the next Claude. No phone.

  python3 tests/codemap.py     check (out of date: run python3 codemap.py and commit both maps)
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, os.path.join(ROOT, "codemap.py"), "--check"], capture_output=True, text=True)
print(r.stdout + r.stderr, end="")
if r.returncode:
    sys.exit(1)
print("all code maps the same")
