#!/usr/bin/env python3
"""The phone locks: one file per phone that session.claim() holds (flock) for a whole run. Who holds one, read
without touching a phone. One copy for heal.py, backlog.py, timer.py, adbwifi.py and session.busy (2026-11-22: there
were four). Standard library only, so the root scripts can import it cheaply.

A held flock means a live run, whatever pid the file names. A free lock's pid is stale (the lock goes with the
process however it ends), so the pid alone can't say busy: a reused pid read a dead run as live."""
import fcntl, os

PHONES = ("android", "iphone")


def path(phone):
    """the lock file of 'android' or 'iphone'"""
    return f"/tmp/pogo-{phone}.lock"


def holder(phone):
    """-> the lock's line ('pid N (script args)') while a run holds the phone, or None when it's free. Tries the lock
    and lets go at once. No file yet: free"""
    try:
        f = open(path(phone))
    except OSError:
        return None
    with f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return f.read().strip() or f"a script on the {phone}"
        fcntl.flock(f, fcntl.LOCK_UN)
        return None
