#!/usr/bin/env python3
"""Checks skills/shared/pokedb.py, the memory of each account's Pokémon, on a temp file. No phone.

  python3 tests/database.py    must say "all pokedb cases right"

Made-up Pokémon only: the repo is public.
"""
import datetime, os, sqlite3, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="pokedb-test-")
os.environ["POGO_DB"] = os.path.join(TMP, "test.db")
os.environ.pop("POGO_PHONE", None)
sys.path.insert(0, os.path.join(ROOT, "skills", "shared"))

import base, pokedb  # noqa: E402

base.RUN_DIR = os.path.join(TMP, "run")
bad = []


def check(what, got, want):
    if got != want:
        bad.append(f"{what}: got {got!r}, wanted {want!r}")


def rows(acct="Alice"):
    return pokedb.find(acct)


def reset():
    c = pokedb.connect()
    c.execute("DELETE FROM pokemon")
    pokedb._broken[0] = False
    pokedb.set_account(None)
    pokedb.set_account("Alice")


A = (1500, 120, 12.34, 0.81)  # cp, hp, kg, m
B = (1500, 120, 12.35, 0.81)  # A's twin by CP and HP, another weight

# no account: nothing written
pokedb.set_account(None)
check("no account", pokedb.seen(A, "Foo", []), None)
check("no account, no file rows", pokedb.connect().execute("SELECT COUNT(*) FROM pokemon").fetchone()[0], 0)

# a read with no weight or height: nothing written
reset()
check("no kg", pokedb.seen((1500, 120, None, 0.81), "Foo", []), None)
check("no kg rows", len(rows()), 0)

# the first read adds, the same read again updates the same record
reset()
i = pokedb.seen(A, "Foo", ["GIV"], shadow=False)
check("added", len(rows()), 1)
check("same again", pokedb.seen(A, "Foo2", ["GIV", "XLX"]), i)
r = rows()[0]
check("nickname follows", r["nickname"], "Foo2")
check("tags follow", r["tags"], '["GIV", "XLX"]')
check("flags kept", r["flags"], '{"shadow": false}')

# a twin by CP and HP but not weight: its own record
pokedb.seen(B, "Foo", [])
check("twin is its own", len(rows()), 2)

# a dropped CP digit still matches and never replaces the whole read
check("CP150 is CP1500", pokedb.seen((150, 120, 12.34, 0.81), "Foo2", None), i)
check("CP kept whole", [r["cp"] for r in rows() if r["id"] == i], [1500])

# an unread CP still matches on HP, weight and height
check("no CP", pokedb.seen((None, 120, 12.34, 0.81), None, None), i)

# another account's same Pokémon is another record
pokedb.set_account("Bob")
pokedb.seen(A, "Foo", [])
check("other account", len(rows("Bob")), 1)
check("first account untouched", len(rows("Alice")), 2)
pokedb.set_account("Alice")

# learn: IVs, species, star, nickname, caught; never adds
check("learn", pokedb.learn(A, ivs=(15, 14, 13), species="FOO", star=True, caught=datetime.date(2026, 1, 2),
                            traded=True), i)
r = next(r for r in rows() if r["id"] == i)
check("ivs", (r["atk"], r["def"], r["sta"]), (15, 14, 13))
check("species", r["species"], "FOO")
check("star", r["star"], 1)
check("caught", r["caught"], "2026-01-02")
check("flags merged", r["flags"], '{"shadow": false, "traded": true}')
check("learn never adds", pokedb.learn((999, 99, 1.0, 1.0), ivs=(1, 2, 3)), None)
check("learn never adds rows", len(rows()), 2)

# a misread IV (newest wins), weight, height, CP and HP the same
pokedb.learn(A, ivs=(15, 14, 12))
check("newest IVs win", next((r["atk"], r["def"], r["sta"]) for r in rows() if r["id"] == i), (15, 14, 12))

# power-up: the record follows the new CP and HP
up = (1600, 125, 12.34, 0.81)
check("changed", pokedb.changed(A, up), i)
check("new CP", next(r["cp"] for r in rows() if r["id"] == i), 1600)
check("old read finds nothing", pokedb.learn(A, star=False), None)

# tags set to Transfer: deleted
check("tagged GIV", pokedb.tagged(up, ["GIV"]), i)
pokedb.tagged(up, ["GIV", "Transfer"])
check("tagged Transfer deletes", [r["id"] for r in rows() if r["id"] == i], [])
check("twin stays", len(rows()), 1)

# the Transfer chip seen on the page (read one letter off) deletes too, and adds nothing
pokedb.seen(B, "Foo", ["Transter"])
check("Transfer chip deletes", len(rows()), 0)
pokedb.seen(A, "Foo", ["GIV Transfer"])
check("glued Transfer chip adds nothing", len(rows()), 0)

# two records fit one read: nothing changes
reset()
c = pokedb.connect()
for _ in range(2):
    c.execute("INSERT INTO pokemon (account, cp, hp, kg, m, first_seen, last_seen) VALUES ('Alice',1500,120,12.34,0.81,'x','x')")
check("two fit: none", pokedb.seen(A, "Foo", []), None)
pokedb.tagged(A, ["Transfer"])
check("two fit: none deleted", len(rows()), 2)

# gone (traded away)
reset()
pokedb.seen(A, "Foo", [])
pokedb.gone(A, "traded away")
check("gone", len(rows()), 0)

# the account: storage-limit guesses never override home.trainer()
pokedb.set_account(None)
pokedb.set_account("Alice", sure=False)
check("guess", pokedb.account(), "Alice")
pokedb.set_account("Bob")
pokedb.set_account("Alice", sure=False)
check("sure wins", pokedb.account(), "Bob")
pokedb.set_account(None)
check("sign out", pokedb.account(), None)

# off: nothing at all
os.environ["POGO_DB"] = "off"
check("off", pokedb.path(), None)
os.environ["POGO_DB"] = os.path.join(TMP, "test.db")

# a broken file: one line, then quiet, no exception
pokedb._conn[0] = None
os.environ["POGO_DB"] = os.path.join(TMP, "not-a-db")
open(os.environ["POGO_DB"], "w").write("this is not sqlite " * 100)
pokedb.set_account("Alice")
try:
    check("broken file", pokedb.seen(A, "Foo", []), None)
    check("broken: off", pokedb._broken[0], True)
except Exception as e:
    bad.append(f"broken file raised {e!r}")
pokedb._broken[0] = False
pokedb._conn[0] = None
os.environ["POGO_DB"] = os.path.join(TMP, "test.db")

# backups: one a day, 7 kept
folder = os.path.join(TMP, "backups")
c = pokedb.connect()
for d in range(1, 10):
    pokedb.backup(c, folder, datetime.date(2026, 1, d))
check("second backup same day", pokedb.backup(c, folder, datetime.date(2026, 1, 9)), None)
kept = sorted(os.listdir(folder))
check("7 kept", kept, [f"pokemon-202601{d:02d}.db" for d in range(3, 10)])
check("backup opens", sqlite3.connect(os.path.join(folder, kept[-1])).execute(
    "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], str(pokedb.SCHEMA))

# two processes writing at once: no "database is locked"
reset()
child = """
import os, sys
sys.path.insert(0, sys.argv[1])
import base, pokedb
base.RUN_DIR = sys.argv[2]
pokedb.set_account("Alice")
for k in range(200):
    pokedb.seen((1000 + k, 100, float(sys.argv[3]) + k / 100, 0.5), "W", [])
print(pokedb._broken[0])
"""
procs = [subprocess.Popen([sys.executable, "-c", child, os.path.join(ROOT, "skills", "shared"), base.RUN_DIR, s],
                          stdout=subprocess.PIPE, text=True, env=os.environ) for s in ("10", "50")]
outs = [p.communicate()[0].strip() for p in procs]
check("two writers no errors", outs, ["False", "False"])
check("two writers all rows", len(rows()), 400)

if bad:
    print("\n".join(bad))
    sys.exit(f"{len(bad)} pokedb case(s) wrong")
print("all pokedb cases right")
