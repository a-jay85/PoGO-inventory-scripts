#!/usr/bin/env python3
"""Read the saved searches off the phone and check they hold the terms in rules.SAVED. It only reads: it tags nothing.

  POGO_PHONE=android caffeinate -dimsu python3 savedsearches.py [Clean Trades] ...

Signed in as either account: it checks that account's searches (or the ones named). The bar shows about 35 letters, so
each search is read in pieces, moving the cursor left with the keyboard's keys (Pixel only). A missing term is listed.
The script doesn't change it: fix the search on the phone, or rules.SAVED if the phone is right.
Exit 0: fine. Exit 1: a term is missing, or a search isn't on the account's first page of saved searches.
"""
import difflib, os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, look
import home, search, session, savedsearch
from rules import SAVED

STEP = 20  # cursor moves between reads: under the 35 letters the bar shows, so the pieces overlap
SAME = 0.8  # a long term this close to part of the bar counts as there (OCR reads letters wrong now and then)


def key(s):
    """what OCR can't tell apart, made the same"""
    s = re.sub(r"[!'’|:lI1]", "!", s)
    return re.sub(r"[*°\"”]", "*", s).replace("‹", "").replace(" ", "").lower()


def bar():
    """the search bar's text, without the back arrow and the Q in front of it"""
    t = sorted((x for x in ui.ocr(ui.capture()[0]) if 0.14 < x[1] < 0.21), key=lambda x: x[0])
    return re.sub(r"^\W*Q\s", "", " ".join(x[4] for x in t).strip())


def pieces():
    """the search just run, end to start -> what the bar showed at each stop"""
    if not savedsearch.bar_end():
        raise Stop("the tap on the search bar didn't open it")
    time.sleep(0.5)
    out = [bar()]
    while len(out) < 40:
        ui.android.shell("input keyevent " + " ".join(["KEYCODE_DPAD_LEFT"] * STEP))
        time.sleep(0.4)
        now = bar()
        if key(now) == key(out[-1]) and len(out) > 1:  # at the start: it stopped moving
            break
        out.append(now)
    base.key("back")
    time.sleep(0.5)
    return out


def fits(term, text):
    """the best match of this term anywhere in the text -> 0 to 1"""
    k, w = key(term), key(text)
    size = min(len(k), len(w))
    return max((difflib.SequenceMatcher(None, k, w[i:i + size]).ratio() for i in range(len(w) - size + 1)), default=0)


def missing(terms, got):
    """the terms rules.SAVED wants, the pieces read off the phone -> the terms that aren't in them"""
    text = " ".join(got)
    return [t for t in terms if key(t) not in key(text) and (len(key(t)) < 5 or fits(t, text) < SAME)]


def check(names, wanted):
    """read each one -> how many are wrong or missing"""
    bad = 0
    for name in names:
        if savedsearch.run_shortcut(name) is None:
            log(f"{name}: not on this account's first page of saved searches")
            bad += 1
            continue
        got = pieces()
        log(f"{name}: read {' <- '.join(got)}")
        gone = missing(wanted.get(name, ()), got)
        log(f"{name}: {'MISSING ' + ', '.join(gone) if gone else 'fine'}")
        bad += bool(gone)
    return bad


def script(a):
    base.start()
    who = home.trainer()
    base.start()  # (trainer leaves it on the profile)
    search.to_search_list()
    wanted = SAVED[who]
    names = a or list(wanted)
    log(f"{who}: checking {names}")
    if check(names, wanted):
        raise Stop("a saved search doesn't hold what rules.SAVED wants: see above")
    log("all fine")


if __name__ == "__main__":
    if not ui.ANDROID:
        sys.exit("savedsearches.py needs the Pixel: POGO_PHONE=android")
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="saved")
    session.main(script, sys.argv[1:])
