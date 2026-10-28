#!/usr/bin/env python3
"""Switch the Pixel's Pokémon GO between the user's two accounts: sign out, then back in with the other Google account.

  POGO_PHONE=android python3 account.py              the other account (HashTagAJay <-> CyrillJan)
  POGO_PHONE=android python3 account.py CyrillJan    that one (nothing done if it's already signed in)
  POGO_PHONE=android python3 account.py --who        only say who's signed in

The way (the user, 2026-10-28): main menu (the map's Poké Ball) -> the Settings gear, upper right -> scroll to the
bottom -> Sign Out -> YES -> RETURNING PLAYER -> Sign in with Google -> the account's row in Google's account picker.
Then it reads the trainer name off the profile to be sure.

Which Google account is which trainer lives in ~/.config/pogo/accounts.json (out of the repo, which is public):
  {"HashTagAJay": "...@gmail.com", "CyrillJan": "...@gmail.com"}

Android only. A screen it doesn't know after signing out (Google asking to verify, a captcha) stops the run: the
user signs in by hand from there.
"""
import json, os, random, sys, time

import ui
import run as base
from run import Stop, log, keep_capture
import home

ACCOUNTS = os.path.expanduser("~/.config/pogo/accounts.json")
POKEBALL = (0.5, 0.928)  # the map's Poké Ball: opens the main menu
GEAR = (0.938, 0.115)  # main menu: the Settings gear, right of its label (the label itself doesn't take a tap)
YES = (0.5, 0.515)  # "Are you sure you want to sign out?": YES sits over NO (OCR reads it as junk)
SIGN_IN_TIMEOUT = 120  # seconds from YES to the game loaded on the other account
TRIES = 4  # taps on one screen that don't move it on before giving up


def emails():
    try:
        with open(ACCOUNTS) as f:
            got = json.load(f)
    except (OSError, ValueError) as e:
        raise Stop(f"can't read {ACCOUNTS} (which Google account is which trainer): {e}")
    missing = [n for n in home.TRAINERS if not got.get(n)]
    if missing:
        raise Stop(f"{ACCOUNTS} has no Google account for {', '.join(missing)}")
    return got


def picker():
    """Google's account picker is in front (its own app, over the game)"""
    return "AccountPickerActivity" in ui.android.shell("dumpsys activity activities | grep topResumedActivity")


def screen_of(texts):
    """the screens on the way: settings, signout, landing, providers, or home.where's"""
    j = ui.joined(texts)
    if "SURE YOU WANT TO SIGN OUT" in j:
        return "signout"
    if "SIGN IN WITH GOOGLE" in j:
        return "providers"
    if "RETURNING PLAYER" in j:
        return "landing"
    words = {t[4].strip().upper() for t in texts}
    if "SETTINGS" in words and words & {"MUSIC", "ACCOUNT", "ADVANCED SETTINGS", "ABOUT", "SIGN OUT", "VERSION"}:
        return "settings"
    return None


def rest(wait):
    time.sleep(wait * random.uniform(0.85, 1.25))


def thumb(fx, fy, spread=(0.008, 0.004)):
    """a tap the way a thumb makes one (screen fractions): a random spot near (fx, fy), held 45-120 ms, drifting 1-6 px
    while down. The drift stays under Android's touch slop, so it still counts as a tap. Never the same pixel twice"""
    W, H = ui.android.size()
    x = round((fx + random.gauss(0, spread[0] / 2)) * W)
    y = round((fy + random.gauss(0, spread[1] / 2)) * H)
    dx, dy = random.choice((-1, 1)) * random.randint(1, 6), random.choice((-1, 1)) * random.randint(1, 6)
    ui.android.shell(f"input swipe {x} {y} {x + dx} {y + dy} {random.randint(45, 120)}")


def tap(fx, fy, wait=2.0):
    thumb(fx, fy)
    rest(wait)


def tap_box(t, wait=2.0):
    """somewhere in an OCR box's middle half, not its exact middle"""
    thumb(t[0] + t[2] * random.uniform(0.3, 0.7), t[1] + t[3] * random.uniform(0.3, 0.7), spread=(0.002, 0.001))
    rest(wait)


def tap_text(texts, pred, wait=2.0):
    hit = next((t for t in texts if pred(ui.up(t))), None)
    if hit:
        tap_box(hit, wait)
    return bool(hit)


def swipe_up():
    """up the list, a thumb's way: a random start, a slight slant, a random speed"""
    W, H = ui.android.size()
    x1, y1 = random.uniform(0.4, 0.65), random.uniform(0.72, 0.82)
    x2, y2 = x1 + random.uniform(-0.05, 0.05), random.uniform(0.18, 0.28)
    ui.android.drag((round(x1 * W), round(y1 * H)), (round(x2 * W), round(y2 * H)), random.randint(220, 380))


def sign_out():
    """from the map to the game's sign-in screen (RETURNING PLAYER)"""
    last, same = None, 0
    for _ in range(30):
        screen, texts, path, bounds = home.look()
        mine = screen_of(texts)
        if mine == "landing":
            return
        now = mine or screen
        same = same + 1 if now == last else 0
        last = now
        if same >= TRIES:
            keep_capture("signout")
            raise Stop(f"stuck on {now} on the way to Sign Out: {ui.summary(texts, 150)}")
        if mine == "signout":
            log("  signing out: YES")
            tap(*YES, wait=4.0)
        elif mine == "settings":
            if not tap_text(texts, lambda s: s == "SIGN OUT"):
                swipe_up()  # Sign Out is at the bottom (a scroll doesn't count as stuck)
                rest(1.2)
                same = 0
        elif screen == "mainmenu":
            tap(*GEAR, wait=2.5)  # a banner over the gear eats the tap: the next look tries again
        elif screen == "map":
            tap(*POKEBALL)
        elif screen in ("blank", "signin"):
            rest(1.5)  # signing out: the game goes blank a moment before RETURNING PLAYER
        elif screen == "exit":
            tap_text(texts, lambda s: s == "CANCEL", wait=1.5)
        else:
            home.start(storage=False)  # out of a popup or the Pokémon screens, to the map
    keep_capture("signout")
    raise Stop("couldn't get to Sign Out")


def sign_in(email):
    """from RETURNING PLAYER through Google's account picker to the game loading on that account"""
    end = time.time() + SIGN_IN_TIMEOUT
    picked, last, same = False, None, 0
    while time.time() < end:
        if not picked and picker():
            screen, texts, path, bounds = home.look()
            hit = next((t for t in texts if t[4].strip().lower() == email.lower()), None)
            if not hit:
                keep_capture("picker")
                raise Stop(f"Google's account picker has no {email}: {ui.summary(texts, 200)}")
            log(f"  Google account picker: {email}")
            tap_box(hit, wait=5.0)
            picked = True
            continue
        screen, texts, path, bounds = home.look()
        mine = screen_of(texts)
        now = mine or screen
        same = same + 1 if now == last and mine else 0
        last = now
        if same >= TRIES:
            keep_capture("signin")
            raise Stop(f"stuck on {now} signing in: {ui.summary(texts, 150)}")
        if mine == "landing":
            log("  RETURNING PLAYER")
            tap_text(texts, lambda s: s == "RETURNING PLAYER", wait=2.5)
        elif mine == "providers":
            log("  Sign in with Google")
            tap_text(texts, lambda s: s == "SIGN IN WITH GOOGLE", wait=4.0)
        elif picked and (screen in home.STORAGE or screen in ("map", "mainmenu")):
            return
        elif picked and screen in ("blank", "unknown") and "com.google" not in ui.android.shell(
                "dumpsys activity activities | grep topResumedActivity"):
            return  # the game is loading: home.trainer() waits it out and closes any popups
        else:
            rest(1.5)  # Google's screens or the game loading
    keep_capture("signin")
    raise Stop(f"not signed in after {SIGN_IN_TIMEOUT}s: Google may want you to sign in by hand")


def switch(to=None):
    """sign in as `to` (default: the other account). -> the trainer signed in at the end"""
    if not ui.ANDROID:
        raise Stop("account.py works on the Pixel only (POGO_PHONE=android)")
    accounts = emails()
    home.session.ready()
    home.android_launch()
    screen, texts, path, bounds = home.look()
    if screen_of(texts) in ("landing", "providers") or screen == "signin" or picker():
        if not to:  # signed out already (a run stopped half way): no one to switch from
            raise Stop("nobody is signed in: say which account (account.py HashTagAJay or CyrillJan)")
        log(f"signed out already: signing in as {to}")
        sign_in(accounts[to])
        return check(to)
    who = home.trainer()
    to = to or next(n for n in home.TRAINERS if n != who)
    if who == to:
        log(f"{to} is signed in already")
        return who
    log(f"switching {who} -> {to}")
    sign_out()
    sign_in(accounts[to])
    return check(to)


def check(to):
    now = home.trainer()
    if now != to:
        raise Stop(f"signed in as {now}, not {to}: check {ACCOUNTS}")
    log(f"switched to {to}")
    return now


if __name__ == "__main__":
    args = sys.argv[1:]
    base.new_run_dir(os.path.join(base.HERE, "runs"))
    try:
        if "--who" in args:
            print(home.trainer())
        else:
            names = {n.lower(): n for n in home.TRAINERS}
            want = [a for a in args if not a.startswith("--")]
            if want and want[0].lower() not in names:
                sys.exit(f"account.py: {want[0]!r} isn't one of {', '.join(home.TRAINERS)}")
            print(switch(names[want[0].lower()] if want else None))
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
