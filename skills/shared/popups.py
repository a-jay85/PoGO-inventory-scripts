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
AGAIN_WINDOW, MAX_AGAIN = 60, 6  # the same box closed (or pages.py page left) this many times within this many seconds: it isn't closing
closed = {}  # box name -> the times it was closed lately

MANAGE_X = (0.5, 0.906)  # the round X that closes the Manage Favorite Search box
FRIEND_CARD_X = (0.5, 0.918)  # its round X, in the same spot on both phones: higher than X_BUTTON, which grazes its edge
SAFETY_TO_OK = 0.08  # the safety warning: its OK this far under 'playing Pokémon GO.' (iPhone 0.645 -> 0.723)
WALK_X = (0.5, 0.86)  # the weekly walk reward's round X after CLAIM REWARD (Pixel 2026-11-16: where the button was)
EGG_TO_X = 0.082  # a friend card with USE LUCKY EGG: its X sits this far under the button's middle (Pixel 0.849 -> 0.931)


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
    ok = ui.label(texts, "OK")
    if ok:
        return ui.center(ok)
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
    ok = ui.label(texts, "OK")
    return ui.center(ok) if ok else None


def manage_favorite(texts):
    """the Manage Favorite Search box (a saved-search tap that landed as a long press): its round X"""
    return MANAGE_X if "MANAGE FAVORITE" in ui.joined(texts) else None


def exit_box(texts):
    """Android: 'Do you want to exit Pokémon GO?' (Back on the map): CANCEL"""
    if "EXIT POK" not in ui.joined(texts):
        return None
    hit = ui.label(texts, "CANCEL") or ui.label(texts, "NO")
    return ui.center(hit) if hit else None


def evolve_box(texts):
    """'Do you want to evolve ...?': a late tap landed on EVOLVE. Never evolve here: NO"""
    no = [t for t in texts if ui.up(t) == "NO"]
    return ui.center(no[0]) if no and "WANT TO EVOLVE" in ui.joined(texts) else None


def friend_card(texts):
    """'... and you became Lucky Friends! New Bonus Unlocked', with SHARE and SAVE IMAGE under it: only news.
    Its X, because the iPhone has no Back key. 'You and X are now Great Friends! 3 NEW BONUSES UNLOCKED!' (Pixel,
    2026-11-10) has USE LUCKY EGG over its X instead, which puts the X lower: the X, never the egg"""
    j = ui.joined(texts)
    if "FRIENDS" not in j or not ("AND YOU BECAME" in j or "NEW BONUS" in j):
        return None
    egg = ui.label(texts, "USE LUCKY EGG")
    return (0.5, ui.center(egg)[1] + EGG_TO_X) if egg else FRIEND_CARD_X


def passenger(texts):
    """'You're going too fast!' (the phone moving): I'M A PASSENGER. OCR runs the words together ('I'M APASSENGER',
    2026-10-28)"""
    if "TOO FAST" not in ui.joined(texts):
        return None
    hit = next((t for t in texts if "PASSENGER" in ui.up(t)), None)
    return ui.center(hit) if hit else None


def challenge(texts):
    """a Weekly Challenge box. A friend's invite over the profile: its X is greyed out and Back does nothing, so only
    its two buttons get past it. The user's rule (2026-11-03): MAYBE LATER, so a run never sticks here. The "You've
    completed 77%" box over the map (2026-11-04) has one button, LET'S GO!"""
    if "WEEKLY CHALLENGE" not in ui.joined(texts):
        return None
    hit = ui.label(texts, "MAYBE LATER") or ui.label(texts, "LETS GO")
    return ui.center(hit) if hit else None


def party_done(texts):
    """a finished Party Challenge over the map (2026-11-04): Back does nothing there, and it comes back each time the
    map does, so CLAIM REWARD"""
    hit = ui.label(texts, "CLAIM REWARD")
    return ui.center(hit) if hit and "PARTY CHALLENGE" in ui.joined(texts) else None


def walk_reward(texts):
    """Adventure Sync's weekly reward on Monday ('You walked 390.9 km last week!', Pixel HashTagAJay, 2026-11-16:
    the account switch's egg check and /leftovers stopped on it): CLAIM REWARD, its only button. Then the same card
    stays up with a round X where the button was (WALK_X, higher than base.X_BUTTON, which misses it)"""
    if "LAST WEEK" not in ui.joined(texts) or not ui.label(texts, "REWARDS"):
        return None
    hit = ui.label(texts, "CLAIM REWARD")
    return ui.center(hit) if hit else WALK_X


def party_pick(texts):
    """'Choose a Party Challenge' (the party's leader picks one): Back does nothing, and its countdown on START ran
    out without closing it (Pixel, 2026-11-07). The user's rule: START. OCR glues the countdown on: '58  START'"""
    if "CHOOSE A PARTY CHALLENGE" not in ui.joined(texts):
        return None
    hit = next((t for t in texts if re.fullmatch(r"[\d\s]*START", ui.up(t))), None)
    return ui.center(hit) if hit else None


def party_rejoin(texts):
    """'Continue Party Play?' after signing in (Pixel, 2026-11-14: CyrillJan, after the switch from HashTagAJay):
    REJOIN PARTY or LEAVE PARTY, and Back opens 'leave your party?'. REJOIN PARTY, so nothing the user set up is
    lost; leaving disbands the party and loses its rewards"""
    hit = ui.label(texts, "REJOIN PARTY")
    return ui.center(hit) if hit and "CONTINUE PARTY PLAY" in ui.joined(texts) else None


def party_leave(texts):
    """'Are you sure you want to leave your party? If you leave, your party will disband.' (what Back on 'Continue
    Party Play?' opens): NO, which goes back to that box"""
    hit = ui.label(texts, "NO")
    return ui.center(hit) if hit and "PARTY WILL DISBAND" in ui.joined(texts) else None


def party_ended(texts):
    """'The party has ended' (a party lasts 3 hours): OK"""
    hit = ui.label(texts, "OK")
    return ui.center(hit) if hit and "THE PARTY HAS ENDED" in ui.joined(texts) else None


def party_summary(texts):
    """the party's summary after it: only its round X closes it"""
    return base.X_BUTTON if "TOTAL KM EXPLORED" in ui.joined(texts) else None


def rocket_radar(texts):
    """a new Rocket Radar (2026-11-05): Back does nothing, no X. EQUIP, its only button"""
    hit = ui.label(texts, "EQUIP")
    return ui.center(hit) if hit and "ROCKET RADAR" in ui.joined(texts) else None


def safety(texts):
    """the game's 'Stay Aware of Your Surroundings' warning as it loads (iPhone, 2026-11-13: /trade stopped on it):
    OK, its only button. OCR can miss its white-on-green OK: it sits SAFETY_TO_OK under the message's last line"""
    if "STAY AWARE OF YOUR SURROUNDINGS" not in ui.joined(texts):
        return None
    hit = ui.label(texts, "OK")
    if hit:
        return ui.center(hit)
    last = next((t for t in texts if "PLAYING POK" in ui.norm(t[4])), None)
    return (0.5, last[1] + last[3] / 2 + SAFETY_TO_OK) if last else None


def news(texts):
    """an event's news card as the game loads ('Dynamax Trails', SEE DETAILS and DISMISS; iPhone, 2026-11-13: /trade's
    restart stopped on it): DISMISS"""
    hit = ui.label(texts, "DISMISS")
    return ui.center(hit) if hit and ui.label(texts, "SEE DETAILS") else None


def battery_saver(texts):
    """Android's own 'Turn on Extreme Battery Saver?' box at 10% battery, over any screen (Pixel, 2026-11-13: over a
    hatched egg's rewards): No thanks"""
    hit = ui.label(texts, "NO THANKS")
    return ui.center(hit) if hit and "BATTERY SAVER" in ui.joined(texts) else None


def mirroring_welcome(texts):
    """iPhone Mirroring's own 'iPhone on Your Mac' welcome page as it opens ('Stay up to date', Learn More... / Not Now
    / Continue; iPhone, 2026-11-18: home.start stopped on it as an unknown screen): Not Now, which changes nothing"""
    hit = ui.label(texts, "NOT NOW")
    return ui.center(hit) if hit and "IPHONE ON YOUR MAC" in ui.joined(texts) else None


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
    ("walk reward", walk_reward, "Adventure Sync's weekly reward is up: CLAIM REWARD, then its X", 2.5),
    ("party pick", party_pick, "the party's challenge picker is up: tapping START", 2.5),
    ("party rejoin", party_rejoin, "'Continue Party Play?' is up: tapping REJOIN PARTY", 2.5),
    ("party leave", party_leave, "'leave your party?' is up: tapping NO", 1.5),
    ("party ended", party_ended, "the party has ended: tapping OK", 1.5),
    ("party summary", party_summary, "the party's summary is up: closing it", 1.5),
    ("news", news, "an event's news card is up: tapping DISMISS", 1.5),
    ("safety", safety, "the 'Stay Aware of Your Surroundings' warning is up: tapping OK", 1.5),
    ("rocket radar", rocket_radar, "a new Rocket Radar is up: tapping EQUIP, its only button", 2.5),
    ("mirroring welcome", mirroring_welcome, "iPhone Mirroring's welcome page is up: tapping Not Now", 2.0),
    ("battery saver", battery_saver, "Android asks to turn on Extreme Battery Saver: tapping No thanks", 1.0),
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


def once_more(hist, name, texts, kind, did):
    """note one more time `name` was left or closed. Raises Stop (with a `kind` capture) when that makes more than
    MAX_AGAIN times in AGAIN_WINDOW seconds: its way out doesn't work. hist: the caller's {name: [times]}"""
    now = time.time()
    hist[name] = [t for t in hist.get(name, []) if now - t < AGAIN_WINDOW] + [now]
    if len(hist[name]) > MAX_AGAIN:
        base.keep_capture(kind)
        raise base.Stop(f"{did} {MAX_AGAIN} times in {AGAIN_WINDOW}s and it keeps coming back: {ui.summary(texts, 120)}")


def clear(texts, bounds):
    """close the box up on this screen, if one is. -> its name, or None when no box is up. Raises Stop when the same
    box keeps coming back"""
    got = which(texts)
    if not got:
        return None
    name, (fx, fy), say, wait = got
    once_more(closed, name, texts, "popup", f"closed the {name} box")
    base.log(f"  {say}")
    base.click(fx, fy, bounds, fuzz=0.004)
    time.sleep(wait)
    return name


if __name__ == "__main__":
    for png in sys.argv[1:]:
        got = which(ui.ocr(png))
        print(f"{png}: {got[0]} at {got[1][0]:.3f},{got[1][1]:.3f}" if got else f"{png}: no box")
