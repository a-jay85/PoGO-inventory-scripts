#!/usr/bin/env python3
"""Boxes the game pops up over any screen, by itself or left over from another script, that one safe tap closes.
Every script gets past them the same way, from two places:

- base.wait_for: a box over the screen it waits for is closed, and the wait goes on.
- home.unstick: the step out of a screen a script doesn't know tries these first, before Back (Android) or opening
  the game again (iPhone). Every script's "unknown screen" path ends in unstick, so all of them know every box here.

Only safe taps: OK on a box that only tells something, CANCEL, NO, X, MAYBE LATER, I'M A PASSENGER, and the one
button of a box that has nothing else (CLAIM REWARD, LET'S GO!, EQUIP). Never CONFIRM, EVOLVE, or a trade's YES.

A script that handles a box itself puts its name in HANDS_OFF (trade/phone.py: the trade boxes, since trade.py
starts the round over on them). A box that comes back right after each close stops the run instead of looping.

  python3 popups.py <png>     which box this screenshot shows, and where its tap would go (nothing is tapped)
"""
import re, sys, time

import ui
import base

HANDS_OFF = set()  # box names the running script handles itself
AGAIN_WINDOW, MAX_AGAIN = 60, 6  # the same box closed this many times within this many seconds: it isn't closing
closed = {}  # box name -> the times it was closed lately

MANAGE_X = (0.5, 0.906)  # the round X that closes the Manage Favorite Search box
FRIEND_CARD_X = (0.5, 0.918)  # its round X, in the same spot on both phones: higher than X_BUTTON, which grazes its edge
SAFETY_TO_OK = 0.08  # the safety warning: its OK this far under 'playing Pokémon GO.' (iPhone 0.645 -> 0.723)
EGG_TO_X = 0.082  # a friend card with USE LUCKY EGG: its X sits this far under the button's middle (Pixel 0.849 -> 0.931)


def label(texts, word):
    """the text box that reads exactly word, or None"""
    return next((t for t in texts if ui.norm(t[4]) == word), None)


def center(t):
    return t[0] + t[2] / 2, t[1] + t[3] / 2


# ---------- what each box is, and where its tap goes ----------
# each: texts -> (fx, fy) to tap (screen fractions), or None when it isn't up

def trade_box(texts):
    """a trade's info box, with OK: 'range' ('... is out of range for trading') or 'expired' (a trade left open too
    long, the other side left, or the trading service lost it). It can come up late, after the trade screens are
    gone (2026-11-07: over the Pokémon screens, /cleantrades stopped on it). -> the kind, or None"""
    j = ui.joined(texts)
    if "OUT OF RANGE" in j:
        return "range"
    if any(w in j for w in ("TRADE EXPIRED", "TRADE WAS CANCELED", "HAS EXPIRED", "ERROR FETCHING TRADE",
                            "TRADING SERVICE")):
        return "expired"
    return None


def trade_ok(texts):
    """the trade box's OK. The iPhone's "This trade with ... has expired." and "... is out of range" boxes: OCR can
    miss their white-on-green OK, which sits just under the message (on the Android, "expired." gets a line of its own)"""
    if not trade_box(texts):
        return None
    ok = label(texts, "OK")
    if ok:
        return center(ok)
    msg = [t for t in texts if "EXPIRED" in ui.up(t) or "OUT OF RANGE" in ui.up(t) or "CANCELED" in ui.up(t)]
    return (0.5, max(t[1] for t in msg) + 0.077) if msg else None


def trade_limit(texts):
    """the account has made the game's 100 trades today: the Pixel's "<trainer> has reached the daily trading limit
    for today." box (its OK), or the iPhone's "Daily trading limit reached. Come back tomorrow to trade more." (a
    message with no button, which goes by itself: None). -> True when either is up"""
    return "TRADING LIMIT" in ui.joined(texts)


def trade_limit_ok(texts):
    """the daily trading limit box's OK (Pixel), or None"""
    if not trade_limit(texts):
        return None
    ok = label(texts, "OK")
    return center(ok) if ok else None


def manage_favorite(texts):
    """the Manage Favorite Search box (a saved-search tap that landed as a long press): its round X"""
    return MANAGE_X if "MANAGE FAVORITE" in ui.joined(texts) else None


def exit_box(texts):
    """Android: 'Do you want to exit Pokémon GO?' (Back on the map): CANCEL"""
    if "EXIT POK" not in ui.joined(texts):
        return None
    hit = label(texts, "CANCEL") or label(texts, "NO")
    return center(hit) if hit else None


def evolve_box(texts):
    """'Do you want to evolve ...?': a late tap landed on EVOLVE. Never evolve here: NO"""
    no = [t for t in texts if ui.up(t) == "NO"]
    return center(no[0]) if no and "WANT TO EVOLVE" in ui.joined(texts) else None


def friend_card(texts):
    """'... and you became Lucky Friends! New Bonus Unlocked', with SHARE and SAVE IMAGE under it: only news.
    Its X, because the iPhone has no Back key. 'You and X are now Great Friends! 3 NEW BONUSES UNLOCKED!' (Pixel,
    2026-11-10) has USE LUCKY EGG over its X instead, which puts the X lower: the X, never the egg"""
    j = ui.joined(texts)
    if "FRIENDS" not in j or not ("AND YOU BECAME" in j or "NEW BONUS" in j):
        return None
    egg = label(texts, "USE LUCKY EGG")
    return (0.5, center(egg)[1] + EGG_TO_X) if egg else FRIEND_CARD_X


def passenger(texts):
    """'You're going too fast!' (the phone moving): I'M A PASSENGER. OCR runs the words together ('I'M APASSENGER',
    2026-10-28)"""
    if "TOO FAST" not in ui.joined(texts):
        return None
    hit = next((t for t in texts if "PASSENGER" in ui.up(t)), None)
    return center(hit) if hit else None


def challenge(texts):
    """a Weekly Challenge box. A friend's invite over the profile: its X is greyed out and Back does nothing, so only
    its two buttons get past it. The user's rule (2026-11-03): MAYBE LATER, so a run never sticks here. The "You've
    completed 77%" box over the map (2026-11-04) has one button, LET'S GO!"""
    if "WEEKLY CHALLENGE" not in ui.joined(texts):
        return None
    hit = label(texts, "MAYBE LATER") or label(texts, "LETS GO")
    return center(hit) if hit else None


def party_done(texts):
    """a finished Party Challenge over the map (2026-11-04): Back does nothing there, and it comes back each time the
    map does, so CLAIM REWARD"""
    hit = label(texts, "CLAIM REWARD")
    return center(hit) if hit and "PARTY CHALLENGE" in ui.joined(texts) else None


def party_pick(texts):
    """'Choose a Party Challenge' (the party's leader picks one): Back does nothing, and its countdown on START ran
    out without closing it (Pixel, 2026-11-07). The user's rule: START. OCR glues the countdown on: '58  START'"""
    if "CHOOSE A PARTY CHALLENGE" not in ui.joined(texts):
        return None
    hit = next((t for t in texts if re.fullmatch(r"[\d\s]*START", ui.up(t))), None)
    return center(hit) if hit else None


def party_ended(texts):
    """'The party has ended' (a party lasts 3 hours): OK"""
    hit = label(texts, "OK")
    return center(hit) if hit and "THE PARTY HAS ENDED" in ui.joined(texts) else None


def party_summary(texts):
    """the party's summary after it: only its round X closes it"""
    return base.X_BUTTON if "TOTAL KM EXPLORED" in ui.joined(texts) else None


def rocket_radar(texts):
    """a new Rocket Radar (2026-11-05): Back does nothing, no X. EQUIP, its only button"""
    hit = label(texts, "EQUIP")
    return center(hit) if hit and "ROCKET RADAR" in ui.joined(texts) else None


def safety(texts):
    """the game's 'Stay Aware of Your Surroundings' warning as it loads (iPhone, 2026-11-13: /trade stopped on it):
    OK, its only button. OCR can miss its white-on-green OK: it sits SAFETY_TO_OK under the message's last line"""
    if "STAY AWARE OF YOUR SURROUNDINGS" not in ui.joined(texts):
        return None
    hit = label(texts, "OK")
    if hit:
        return center(hit)
    last = next((t for t in texts if "PLAYING POK" in ui.norm(t[4])), None)
    return (0.5, last[1] + last[3] / 2 + SAFETY_TO_OK) if last else None


# name, where its tap goes, what the log says, seconds the box takes to go
BOXES = (
    ("trade box", trade_ok, "a trade's box is up ({}): tapping OK", 1.5),
    ("trade limit", trade_limit_ok, "the daily trading limit box is up: tapping OK", 1.5),
    ("manage favorite", manage_favorite, "the Manage Favorite Search box is up: its X", 1.0),
    ("exit", exit_box, "'exit Pokémon GO?' is up: CANCEL", 1.5),
    ("evolve", evolve_box, "an 'evolve?' box came up: NO", 1.0),
    ("friend card", friend_card, "a new friend level card is up: closing it", 1.0),
    ("passenger", passenger, "'going too fast' popup: tapping I'M A PASSENGER", 1.5),
    ("challenge", challenge, "a Weekly Challenge box is up: {}", 1.5),
    ("party done", party_done, "a finished Party Challenge is up: tapping CLAIM REWARD", 2.5),
    ("party pick", party_pick, "the party's challenge picker is up: tapping START", 2.5),
    ("party ended", party_ended, "the party has ended: tapping OK", 1.5),
    ("party summary", party_summary, "the party's summary is up: closing it", 1.5),
    ("safety", safety, "the 'Stay Aware of Your Surroundings' warning is up: tapping OK", 1.5),
    ("rocket radar", rocket_radar, "a new Rocket Radar is up: tapping EQUIP, its only button", 2.5),
)


def which(texts):
    """the box up on this screen -> (name, (fx, fy), log line, wait), or None"""
    for name, where, say, wait in BOXES:
        if name in HANDS_OFF:
            continue
        at = where(texts)
        if at:
            detail = trade_box(texts) if name == "trade box" else \
                ui.summary([t for t in texts if ui.norm(t[4]) in ("MAYBE LATER", "LETS GO")], 30)
            return name, at, say.format(detail), wait
    return None


def clear(texts, bounds):
    """close the box up on this screen, if one is. -> its name, or None when no box is up. Raises Stop when the same
    box keeps coming back"""
    got = which(texts)
    if not got:
        return None
    name, (fx, fy), say, wait = got
    now = time.time()
    recent = closed[name] = [t for t in closed.get(name, []) if now - t < AGAIN_WINDOW] + [now]
    if len(recent) > MAX_AGAIN:
        base.keep_capture("popup")
        raise base.Stop(f"closed the {name} box {MAX_AGAIN} times in {AGAIN_WINDOW}s and it keeps coming back: "
                        f"{ui.summary(texts, 120)}")
    base.log(f"  {say}")
    base.click(fx, fy, bounds, fuzz=0.004)
    time.sleep(wait)
    return name


if __name__ == "__main__":
    for png in sys.argv[1:]:
        got = which(ui.ocr(png))
        print(f"{png}: {got[0]} at {got[1][0]:.3f},{got[1][1]:.3f}" if got else f"{png}: no box")
