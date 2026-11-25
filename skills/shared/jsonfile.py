#!/usr/bin/env python3
"""JSON files other runs read back (a day's count, a resume point, a skip list). Standard library only, so timer.py
and ui.py (which base imports) can use it too. base.read_json and base.write_json are these two."""
import json, os


def read(path, default=None):
    """-> the file's JSON, or default when it's missing or not whole JSON"""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write(path, data, **kw):
    """write a file other runs read: a temp file first, then swapped in, so a run stopped mid-write never leaves half
    a file. kw goes to json.dump"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, **kw)
    os.replace(tmp, path)
