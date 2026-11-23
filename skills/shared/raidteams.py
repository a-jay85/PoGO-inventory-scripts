"""The raid team rule (the user, 2026-11-17): a Pokémon on its holder's own team of 6 against some 4★+ raid boss,
at its real level and IVs (team A, the user's Team Available), or with every copy at level 50 (team B, the user 2026-11-19), is a favorite. The door (verdict.final_tag) and /ivc (sort.decide) both ask on_team()
first. The teams come from the newest whole count (`roster/raidteam.py count`, no --limit) of the signed-in account,
however old: every script that asks logs its age in days once.

A copy is found in the count by species, shadow, kg and m (a power-up changes CP and HP, never those), else by CP
and HP. One the count doesn't have, at or over its pile's bar (the lowest CP that could make some team A), was caught
or powered up after the count: not sure. Under the bar it can still make a team B if its IV sum is at or over the
pile's bars50 (the lowest IV sum that could make some team B): not sure, and its IV sum unknown is not sure too.
Under both it can't make a team. Nor can one whose stars the count's
search left out (stars: its IV sum that low, its CP that low or lower).
"""
import glob, json, os, time

from base import log

RUNS = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "roster", "runs")
_TEAMS = {}  # account -> (teams dict or None, days old)
_PATHS = {}  # account -> its teams.json


def newest(who):
    """-> (teams dict, days since its count) for this account, or (None, None): the newest whole count (no --limit),
    however old. The first ask for an account logs which count it is and how old"""
    if who in _TEAMS:
        return _TEAMS[who]
    got = None, None
    for p in sorted(glob.glob(os.path.join(RUNS, "*-raidteam", "teams.json")), reverse=True):
        try:
            t = json.load(open(p))
        except (OSError, ValueError):
            continue
        if t.get("trainer") == who and not t.get("limit"):
            when = time.mktime(time.strptime(t["counted"], "%Y-%m-%d %H:%M"))
            got = t, (time.time() - when) / 86400
            _PATHS[who] = p
            break
    _TEAMS[who] = got
    if got[0] is None:
        log(f"raid teams: no whole count for {who} yet (raidteam.py count): the raid team rule is off")
    else:
        log(f"raid teams: {who}'s count is {got[1]:.1f} days old ({got[0]['counted']}, "
            f"{sum(bool(c['on']) for c in got[0]['copies'])} on a team)")
    return got


def path_of(who):
    """the teams.json newest(who) read, or None"""
    newest(who)
    return _PATHS.get(who)


def close(a, b, by):
    return a is not None and b is not None and abs(a - b) <= by


def on_team(who, sids, shadow, cp, hp, kg=None, m=None, t=None, iv_sum=None):
    """-> the bosses whose team it's on (a list: [] = on none), or None: not sure. () when there's no count to ask.
    t: the teams dict (default the account's newest). iv_sum: its IV sum, if known: the count's search may have left
    its stars out (stars)"""
    t = t if t is not None else newest(who)[0] if who else None
    if t is None:
        return ()
    b50s = t.get("bars50", {})  # (an older count has team A only)
    if not sids or len(sids) != 1:
        return None if sids and any(t["bars"].get(f"{s}{'|shadow' if shadow else ''}") is not None
                                    or b50s.get(f"{s}{'|shadow' if shadow else ''}") is not None for s in sids) else []
    sid = sids[0]
    key = f"{sid}{'|shadow' if shadow else ''}"
    bar, bar50 = t["bars"].get(key), b50s.get(key)
    if bar is None and bar50 is None:  # on no boss list, or no copy of it could make a team A or B
        return []
    mine = [c for c in t["copies"] if sid in c["species"] and bool(c["shadow"]) == bool(shadow)]
    same = [c for c in mine if close(c.get("kg"), kg, 0.015) and close(c.get("m"), m, 0.015)] \
        or [c for c in mine if c["cp"] == cp and hp in (c.get("hp"), None)] \
        or [c for c in mine if c["cp"] == cp and c.get("hp") is None and iv_sum is not None  # counted from its /ivc
            and iv_sum in {sum(v) for v in c.get("ivs") or ()}]  # name, never opened: no HP, so its IV sum too
    if len(same) == 1:
        return list(same[0]["on"])
    if same:  # twins: the same on every team, or not sure
        ons = {tuple(c["on"]) for c in same}
        return list(ons.pop()) if len(ons) == 1 else None
    if cp is None:
        return None
    if iv_sum is not None and any(iv_sum <= smax and (top is None or cp <= top)
                                  for smax, top in t.get("stars", {}).get(key, [])):
        return []
    if bar is not None and cp >= bar:  # could make a team A
        return None
    if bar50 is not None and (iv_sum is None or iv_sum >= bar50):  # could make a team B
        return None
    return []
