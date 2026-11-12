#!/usr/bin/env python3
"""A memory of each account's Pokémon, built from what the scripts already read. Nothing here taps, waits or looks:
base.py's detail-page steps hand it their steady reads (steady_detail, exact_ivs, set_tags, do_rename, set_star),
home.py tells it the account, and a Pokémon tagged Transfer is deleted.

  python3 skills/shared/pokedb.py stats            counts per account
  python3 skills/shared/pokedb.py show [account]   every record, newest first
  python3 skills/shared/pokedb.py stale [days]     records no script has seen in that many days (default 30)

Pokémon tagged Transfer in bulk, never opened: ../cleanup/dbsweep.py deletes their records. savedsearch.tag_pile marks
the sweep due (sweep_due), and cleantrades.py runs it right after its Transfer tag.

The file: ~/.config/pogo/pokemon.db (SQLite), one for both accounts, never in the repo. POGO_DB=off turns it off,
POGO_DB=/path/x.db uses another file (tests). A copy goes to ~/claude-plans/_backups/pokemon-db/ once a day (7 kept).

Which record a read is (plan 2026-11-12): weight + height + CP + HP, by base.same_pokemon's rule (each value read on
both sides must agree, an unread one doesn't block). Species and IVs are filled in when an appraisal reads them; a
disagreeing one is a misread, the newest steady read wins. Two records fit one read: nothing is written.
"""
import datetime, glob, json, os, sqlite3, sys, time

DEFAULT = os.path.expanduser("~/.config/pogo/pokemon.db")
BACKUPS = os.path.expanduser("~/claude-plans/_backups/pokemon-db")
KEEP_BACKUPS = 7
SCHEMA = 1
TRANSFER = "TRANSFER"  # rules.TRANSFER as ui.norm reads the chip

_conn = [None]
_broken = [False]  # a database error once: say it once and stay quiet (a run never stops for the database)
ACCOUNT = {"name": None, "sure": False}  # sure: home.trainer() said it (not just the storage limit)
SEEN_BY = os.path.basename(os.path.dirname(os.path.abspath(sys.argv[0]))) + "/" + os.path.basename(sys.argv[0]) \
    if sys.argv and sys.argv[0] else "?"


def path():
    p = os.environ.get("POGO_DB", "")
    if p.lower() in ("off", "0", "no"):
        return None
    return os.path.expanduser(p) if p else DEFAULT


def _log(msg):
    b = sys.modules.get("base")
    (b.log if b else print)(f"  pokedb: {msg}")


def _guard(fn):
    """a database error logs one line and the run goes on"""
    def run(*a, **kw):
        if _broken[0]:
            return None
        try:
            return fn(*a, **kw)
        except Exception as e:  # (not KeyboardInterrupt: Ctrl-C still stops the run)
            _broken[0] = True
            _log(f"off for this run: {type(e).__name__}: {e}")
            return None
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


def connect():
    """the open file (WAL, so two runs can write at once), made and backed up on first use. None: off"""
    if _conn[0] is not None:
        return _conn[0]
    p = path()
    if not p:
        return None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    c = sqlite3.connect(p, timeout=5, isolation_level=None)  # autocommit: each write its own short transaction
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS pokemon (
            id INTEGER PRIMARY KEY,
            account TEXT NOT NULL,
            species TEXT, nickname TEXT,
            cp INTEGER, hp INTEGER, kg REAL, m REAL,
            atk INTEGER, def INTEGER, sta INTEGER,
            tags TEXT, star INTEGER, caught TEXT, flags TEXT,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, seen_by TEXT);
        CREATE INDEX IF NOT EXISTS by_size ON pokemon (account, kg, m);
    """)
    c.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA),))
    _conn[0] = c
    if p == DEFAULT:
        backup(c)
    return c


def backup(c, folder=BACKUPS, today=None):
    """the day's copy, if there isn't one yet, and only the newest KEEP_BACKUPS kept"""
    today = today or datetime.date.today()
    dest = os.path.join(folder, f"pokemon-{today:%Y%m%d}.db")
    if os.path.exists(dest):
        return None
    os.makedirs(folder, exist_ok=True)
    tmp = dest + ".tmp"
    out = sqlite3.connect(tmp)
    try:
        c.backup(out)
    finally:
        out.close()
    os.replace(tmp, dest)
    for old in sorted(glob.glob(os.path.join(folder, "pokemon-*.db")))[:-KEEP_BACKUPS]:
        os.remove(old)
    return dest


# ---------- the account ----------

def set_account(name, sure=True):
    """home.trainer() (sure) or the storage limit (not sure: a trainer() read later wins). None: signing out"""
    if name is None:
        ACCOUNT.update(name=None, sure=False)
    elif sure or not ACCOUNT["sure"]:
        ACCOUNT.update(name=name, sure=sure or ACCOUNT["sure"] and ACCOUNT["name"] == name)


def account():
    return ACCOUNT["name"]


# ---------- matching ----------

def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _r2(x):
    return None if x is None else round(float(x), 2)


def _same(row, who):
    """base.same_pokemon, row against a who() read (cp, hp, kg, m)"""
    import base
    return base.same_pokemon((row["cp"], row["hp"], row["kg"], row["m"]), tuple(who))


def matches(c, acct, who):
    """the records this read could be: same weight and height to the hundredth, then CP and HP by same_pokemon"""
    cp, hp, kg, m = who
    rows = c.execute("SELECT * FROM pokemon WHERE account=? AND kg=? AND m=?", (acct, _r2(kg), _r2(m))).fetchall()
    return [r for r in rows if _same(r, who)]


def _cp(old, new):
    """a dropped digit ('CP62' for CP626) never replaces a whole read"""
    if old and new and str(old).startswith(str(new)) and len(str(new)) < len(str(old)):
        return old
    return new if new is not None else old


def _fingerprint(who):
    """(cp, hp, kg, m) with weight and height read, or None: no weight or height, no telling twins apart"""
    if not who or len(who) != 4:
        return None
    cp, hp, kg, m = who
    if kg is None or m is None:
        return None
    return cp, hp, _r2(kg), _r2(m)


def _one(c, acct, who, what):
    got = matches(c, acct, who)
    if len(got) > 1:
        _log(f"{what}: {len(got)} records fit CP{who[0]} {who[1]}HP {who[2]}kg {who[3]}m, none changed")
        return None
    return got[0] if got else None


# ---------- what the scripts saw ----------

def _norm_tags(tags):
    """chip or sheet texts as base.row_name reads them, upper case"""
    import base
    return sorted({n for t in tags or () if (n := base.row_name(str(t)))})


def _transfer(tags):
    """a Transfer chip among them, one OCR letter off too ('TRANSTER', 2026-11-06), or glued to another chip"""
    import base
    return any(w == TRANSFER or base.one_letter_off(w, TRANSFER) for t in tags for w in t.split())


@_guard
def seen(who, nickname=None, tags=None, **facts):
    """a steady read of the detail page's top. Adds or updates its record; one wearing the Transfer chip is deleted.
    -> the record id, or None (off, no account, no weight or height, two fit, or deleted)"""
    who = _fingerprint(who)
    acct = account()
    if not who or not acct:
        return None
    c = connect()
    if c is None:
        return None
    tags = None if tags is None else _norm_tags(tags)
    if tags and _transfer(tags):
        return _delete(c, acct, who, "Transfer chip")
    got = matches(c, acct, who)
    if len(got) > 1:
        _log(f"seen: {len(got)} records fit CP{who[0]} {who[1]}HP {who[2]}kg {who[3]}m, none changed")
        return None
    row = got[0] if got else None
    cp, hp, kg, m = who
    if row is None:
        cur = c.execute(
            "INSERT INTO pokemon (account, nickname, cp, hp, kg, m, tags, first_seen, last_seen, seen_by)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (acct, nickname, cp, hp, kg, m, None if tags is None else json.dumps(tags), _now(), _now(), SEEN_BY))
        rid = cur.lastrowid
    else:
        rid = row["id"]
        c.execute("UPDATE pokemon SET cp=?, hp=COALESCE(?, hp), nickname=COALESCE(?, nickname),"
                  " tags=COALESCE(?, tags), last_seen=?, seen_by=? WHERE id=?",
                  (_cp(row["cp"], cp), hp, nickname, None if tags is None else json.dumps(tags), _now(), SEEN_BY, rid))
    if facts:
        _facts(c, rid, facts)
    return rid


def _facts(c, rid, facts):
    cols = {k: facts.pop(k) for k in ("species", "caught", "star") if k in facts and facts[k] is not None}
    if "ivs" in facts and facts["ivs"] is not None:
        cols["atk"], cols["def"], cols["sta"] = (int(v) for v in facts.pop("ivs"))
    facts.pop("ivs", None)
    if "caught" in cols:
        cols["caught"] = str(cols["caught"])
    if "star" in cols:
        cols["star"] = int(bool(cols["star"]))
    extra = {k: v for k, v in facts.items() if v is not None}
    if extra:
        old = c.execute("SELECT flags FROM pokemon WHERE id=?", (rid,)).fetchone()
        merged = {**json.loads(old["flags"] or "{}"), **extra}
        cols["flags"] = json.dumps(merged, sort_keys=True)
    if cols:
        c.execute(f"UPDATE pokemon SET {', '.join(f'{k}=?' for k in cols)}, last_seen=? WHERE id=?",
                  (*cols.values(), _now(), rid))


@_guard
def learn(who, **facts):
    """more about a record already seen (species, ivs, caught, star, nickname, flags like traded or shiny). Never adds
    one: a Pokémon whose top wasn't read steady stays out"""
    who = _fingerprint(who)
    acct = account()
    if not who or not acct:
        return None
    c = connect()
    if c is None:
        return None
    row = _one(c, acct, who, "learn")
    if row is None:
        return None
    nick = facts.pop("nickname", None)
    if nick is not None:
        c.execute("UPDATE pokemon SET nickname=? WHERE id=?", (nick, row["id"]))
    _facts(c, row["id"], facts)
    return row["id"]


@_guard
def tagged(who, tags):
    """the tags after set_tags checked them: Transfer among them deletes the record"""
    who = _fingerprint(who)
    acct = account()
    if not who or not acct:
        return None
    c = connect()
    if c is None:
        return None
    tags = _norm_tags(tags)
    if _transfer(tags):
        return _delete(c, acct, who, "tagged Transfer")
    row = _one(c, acct, who, "tagged")
    if row is not None:
        c.execute("UPDATE pokemon SET tags=?, last_seen=? WHERE id=?", (json.dumps(tags), _now(), row["id"]))
        return row["id"]
    return None


@_guard
def changed(before, after, **facts):
    """the same Pokémon, its CP, HP, weight or height moved (power-up, purify, evolve): the record follows it"""
    before, after = _fingerprint(before), _fingerprint(after)
    acct = account()
    if not before or not after or not acct:
        return None
    c = connect()
    if c is None:
        return None
    row = _one(c, acct, before, "changed")
    if row is None:
        return seen(after, **facts)
    cp, hp, kg, m = after
    c.execute("UPDATE pokemon SET cp=?, hp=COALESCE(?, hp), kg=?, m=?, last_seen=?, seen_by=? WHERE id=?",
              (cp, hp, kg, m, _now(), SEEN_BY, row["id"]))
    if facts:
        _facts(c, row["id"], facts)
    return row["id"]


@_guard
def gone(who, why):
    """it left this account (traded away, transferred): delete its record"""
    who = _fingerprint(who)
    acct = account()
    if not who or not acct:
        return None
    c = connect()
    return None if c is None else _delete(c, acct, who, why)


def _delete(c, acct, who, why):
    got = matches(c, acct, who)
    if len(got) > 1:
        _log(f"{why}: {len(got)} records fit CP{who[0]} {who[1]}HP {who[2]}kg {who[3]}m, none deleted")
    elif got:
        c.execute("DELETE FROM pokemon WHERE id=?", (got[0]["id"],))
        _log(f"{why}: deleted CP{who[0]} {who[2]}kg {who[3]}m")
    return None


@_guard
def sweep_due(acct=None, due=None):
    """a bulk tag gave Transfer to ones never opened (savedsearch.tag_pile): ../cleanup/dbsweep.py is due for this
    account. due True/False sets it (dbsweep clears it after a whole walk). -> is it due"""
    c = connect()
    acct = acct or account()
    if c is None or not acct:
        return False
    k = f"sweep_due:{acct}"
    if due is True:
        c.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, _now()))
    elif due is False:
        c.execute("DELETE FROM meta WHERE key=?", (k,))
    return c.execute("SELECT 1 FROM meta WHERE key=?", (k,)).fetchone() is not None


@_guard
def find(acct=None, **where):
    """records of an account (default: this run's), filtered by exact column values"""
    c = connect()
    acct = acct or account()
    if c is None or not acct:
        return []
    cols = [k for k in where if k.isidentifier()]
    q = "SELECT * FROM pokemon WHERE account=?" + "".join(f" AND {k}=?" for k in cols)
    return [dict(r) for r in c.execute(q, (acct, *(where[k] for k in cols)))]


def stats(c):
    out = []
    for r in c.execute("""SELECT account, COUNT(*) n, COUNT(species) species, COUNT(atk) ivs, COUNT(caught) caught,
                          MAX(last_seen) last FROM pokemon GROUP BY account ORDER BY account"""):
        out.append(f"{r['account']}: {r['n']} Pokémon, {r['species']} with species, {r['ivs']} with IVs, "
                   f"{r['caught']} with a caught date, last seen {r['last']}")
    return out or ["no Pokémon yet"]


if __name__ == "__main__":
    args = sys.argv[1:]
    c = connect()
    if c is None:
        sys.exit("POGO_DB is off")
    if not args or args[0] == "stats":
        print("\n".join(stats(c)))
    elif args[0] == "show":
        q = "SELECT * FROM pokemon" + (" WHERE account=?" if len(args) > 1 else "") + " ORDER BY last_seen DESC"
        for r in c.execute(q, tuple(args[1:2])):
            ivs = f"{r['atk']}/{r['def']}/{r['sta']}" if r["atk"] is not None else "-"
            print(f"{r['account']:12} {r['species'] or '?':16} {r['nickname'] or '':14} CP{r['cp']} {r['hp']}HP "
                  f"{r['kg']}kg {r['m']}m {ivs} {r['tags'] or ''} {r['caught'] or ''} {r['last_seen']}")
    elif args[0] == "stale":
        days = int(args[1]) if len(args) > 1 else 30
        old = c.execute("""SELECT account, COUNT(*) n, MIN(last_seen) oldest FROM pokemon
                           WHERE last_seen < datetime('now', 'localtime', ?) GROUP BY account""", (f"-{days} days",))
        print("\n".join(f"{r['account']}: {r['n']} not seen in {days} days (oldest {r['oldest']})" for r in old)
              or f"every record seen in the last {days} days")
    else:
        sys.exit(__doc__)
