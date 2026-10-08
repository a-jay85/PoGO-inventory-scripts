#!/usr/bin/env python3
"""Android phone for the /pvpc, /ivc and /ivcsort scripts. Turned on with POGO_PHONE=android.
Sees the phone through a scrcpy window (read-only) and taps and types with adb, so the Mac's mouse and
keyboard stay free. ui.py sends its helper calls (click, drag, scroll, key, type, front) here.

  POGO_PHONE=android python3 android.py check   phone plugged in, Pokémon GO in front, scrcpy up, positions agree
  POGO_PHONE=android python3 android.py type <text>
  POGO_PHONE=android python3 android.py key <delete|return|back|clear|one character>
"""
import gzip, os, random, re, shlex, statistics, struct, subprocess, sys, time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = "com.nianticlabs.pokemongo"
TITLE = "PoGO Android"
WIDTH = 406  # captures get shrunk to the width of an iPhone Mirroring capture: some checks count pixels
IPHONE_H = 890  # ...and padded to its height: the iPhone's insets are taller. With the strips the search bar, tabs,
BOTTOM_PAD = 8  # dialogs, bottom buttons and the map's Poké Ball land within a few pixels of where the iPhone code expects them
CHECK_EVERY = 10  # seconds between ready() checks
NO_WINDOW = os.environ.get("POGO_NO_WINDOW") == "1"  # see the phone with adb screenshots only: no scrcpy window
# (slower per look, but nothing on the Mac's screen, and a covered or stalled window can't freeze the picture)


class NotReady(Exception):
    """phone, game or scrcpy window not in a state the scripts can work with"""


def adb(*a, timeout=30):
    r = subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout)
    return r.stdout


def shell(cmd, timeout=60):
    return adb("shell", cmd, timeout=timeout)


_size = None


def size():
    """phone screen in pixels, the space adb input works in ('Override size' wins if set)"""
    global _size
    if not _size:
        m = re.findall(r"(\d+)x(\d+)", shell("wm size"))
        if not m:
            raise NotReady("can't read the phone's screen size (is it plugged in with USB debugging on?)")
        w, h = map(int, m[-1])
        _size = (min(w, h), max(w, h))  # the game runs in portrait
    return _size


# ---------- seeing ----------

def scrcpy_window():
    """-> (window id, x, y, w, h) in points, or None"""
    for where in ([], ["all"]):  # on screen first: "all" can find a hidden 500x500 scrcpy window that never updates
        try:
            wid, x, y, w, h = subprocess.run([os.path.join(HERE, "helper"), "win", "scrcpy", *where],
                                             capture_output=True, text=True, check=True).stdout.split()
        except subprocess.CalledProcessError:
            continue
        if float(h) > 600:
            return int(wid), float(x), float(y), float(w), float(h)
    return None


def content(x, y, w, h):
    """the phone picture inside the window: scrcpy keeps its shape and adds black bars if the window doesn't fit"""
    W, H = size()
    s = min(w / W, h / H)
    return x + (w - W * s) / 2, y + (h - H * s) / 2, W * s, H * s


bounds = None  # the padded picture of the latest capture, in Mac points (what ui.py's fractions are of)
phone = None  # where the phone itself sits in the window, in Mac points: taps are converted with this


def shape(im, scale=1):
    """shrink to WIDTH, then add the strips (top one in the top row's colour, bottom one in the bottom row's).
    scale > 1: the same layout, bigger, for reading small text. -> (image, height of the top strip)"""
    W = WIDTH * scale
    im = im.resize((W, round(W * im.height / im.width)), Image.LANCZOS)
    pad = max(0, IPHONE_H * scale - im.height)
    top = pad - min(BOTTOM_PAD * scale, pad)
    out = Image.new("RGB", (W, im.height + pad), im.getpixel((W // 2, 0)))
    out.paste(Image.new("RGB", (W, pad - top), im.getpixel((W // 2, im.height - 1))), (0, top + im.height))
    out.paste(im, (0, top))
    return out, top


def phone_shot():
    """the phone's own screenshot (slow, ~1.5s: only to check scrcpy's picture)"""
    raw = gzip.decompress(subprocess.run(["adb", "exec-out", "screencap | gzip -1"], capture_output=True,
                                         check=True, timeout=30).stdout)
    w, h = struct.unpack("<2I", raw[:8])
    return Image.frombuffer("RGBA", (w, h), raw[len(raw) - w * h * 4:], "raw", "RGBA", 0, 1).convert("RGB")


def sharp(path="/tmp/pvpc_sharp.png"):
    """the phone's own screenshot in the capture layout, 3x bigger: scrcpy's picture loses small symbols ('!', '&')"""
    shape(phone_shot(), 3)[0].save(path)
    return path


def differ(a, b):
    """mean gap per pixel between two pictures of the screen, shrunk to a thumbnail (0-255)"""
    a, b = (im.convert("L").resize((51, 111), Image.BILINEAR) for im in (a, b))
    return sum(abs(x - y) for x, y in zip(a.getdata(), b.getdata())) / (51 * 111)


FROZEN_AFTER = 15  # seconds of an unchanged scrcpy picture before it's compared with the phone's own screenshot
AFTER_TAP = 2.5  # ...or this long after a tap that didn't change it
_frame = [None, 0.0, 0.0]  # thumbnail of the last picture, when it last changed, when it was last checked
_tapped = 0.0


def frozen(im, force=False):
    """scrcpy's video can stall: the window keeps showing an old frame while the phone moves on.
    -> True if the picture has sat still a while (or force) and the phone's own screenshot shows something else."""
    now, thumb = time.time(), im.convert("L").resize((51, 111), Image.BILINEAR)
    if not force:
        if _frame[0] is None or differ(thumb, _frame[0]) > 1:
            _frame[:2] = thumb, now
            return False
        still = now - _frame[1] >= FROZEN_AFTER or (_frame[1] < _tapped and now - _tapped >= AFTER_TAP)
        if not still or now - _frame[2] < AFTER_TAP:
            return False
    _frame[2] = now
    gap = differ(im, shape(phone_shot())[0])
    if gap > 25:  # a live screen is under 10 off (moving map), a stuck one ~100
        print(f"android: scrcpy's picture is stuck ({gap:.0f} off the phone's own screenshot), restarting it",
              file=sys.stderr)
        return True
    return False


def fresh(path="/tmp/pvpc_fresh.png"):
    """before tapping something again: is scrcpy's picture the phone's real screen? Restarts scrcpy if not.
    -> True if it was stuck (the last tap may well have landed)"""
    before = _restarts
    capture(path, force=True)
    return _restarts > before


_restarts = 0


def restart():
    """scrcpy's picture is stuck (found some other way): start it again"""
    global _aligned, _restarts
    if NO_WINDOW:
        return
    print("android: scrcpy's picture is stuck, restarting it", file=sys.stderr)
    close()
    start_scrcpy()
    _frame[0], _aligned, _restarts = None, False, _restarts + 1
    _win[:] = None, 0.0


WIN_CACHE = 3  # seconds a scrcpy window lookup is reused
_win = [None, 0.0]  # (window id, x, y, w, h), when it was looked up


def capture(path, retry=True, force=False):
    global bounds, _aligned, _restarts
    if NO_WINDOW:  # Mac "points" are the phone's own pixels here, so taps need no conversion
        im, top = shape(phone_shot())
        im.save(path)
        W, H = size()
        globals()["phone"] = [0.0, 0.0, float(W), float(H)]
        k = W / WIDTH
        bounds = [0.0, -top * k, float(W), im.height * k]
        return path, list(bounds)
    looked = not _win[0] or time.time() - _win[1] > WIN_CACHE
    if looked:
        _win[:] = scrcpy_window(), time.time()
    if not _win[0]:
        raise NotReady("scrcpy window not found (run: POGO_PHONE=android python3 android.py check)")
    wid, x, y, w, h = _win[0]
    if subprocess.run(["screencapture", "-l", str(wid), "-o", "-x", path]).returncode:
        if looked:
            raise NotReady("can't capture the scrcpy window")
        _win[:] = None, 0.0  # the window went away (scrcpy restarted): look it up again
        return capture(path, retry, force)
    im = Image.open(path).convert("RGB")
    k = im.width / w  # image pixels per point
    cx, cy, cw, ch = content(x, y, w, h)
    im = im.crop((round((cx - x) * k), round((cy - y) * k), round((cx - x + cw) * k), round((cy - y + ch) * k)))
    im, top = shape(im)
    if retry and frozen(im, force):
        close()
        start_scrcpy()
        _frame[0], _aligned, _restarts = None, False, _restarts + 1
        _win[:] = None, 0.0
        return capture(path, retry=False)
    im.save(path)
    globals()["phone"] = [cx, cy, cw, ch]
    k = cw / WIDTH  # points per capture pixel
    bounds = [cx, cy - top * k, cw, im.height * k]
    return path, list(bounds)


def start_scrcpy():
    subprocess.Popen(["scrcpy", "--no-control", "--no-audio", "--window-borderless", f"--window-title={TITLE}",
                      "--max-size=1280", "--capture-orientation=@0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(40):
        time.sleep(0.5)
        win = scrcpy_window()
        if win and subprocess.run(["screencapture", "-l", str(win[0]), "-o", "-x", "/tmp/pvpc_scrcpy_first.png"]
                                  ).returncode == 0 and Image.open("/tmp/pvpc_scrcpy_first.png").convert("L").getbbox():
            time.sleep(0.5)
            return  # the window is up and has shown a picture (it starts black)
    raise NotReady("scrcpy started but no picture showed up")


def close():
    """close the scrcpy window this started, and its half on the phone (a stuck one there blacks out the next)"""
    pat = f"window-title={TITLE}"
    ok = subprocess.run(["pkill", "-f", pat]).returncode == 0
    for _ in range(10):
        if subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode:
            break
        time.sleep(0.3)
    else:
        subprocess.run(["pkill", "-9", "-f", pat])  # a stuck scrcpy ignores the polite ask
        time.sleep(0.5)
    subprocess.run(["pkill", "-f", "scrcpy-server.jar app_process"])  # its adb shell on the Mac
    shell("pkill -f scrcpy-server", timeout=10)
    return ok


# ---------- getting ready ----------

_checked, _aligned = 0.0, False


def ready(force=False):
    """phone plugged in and awake, Pokémon GO in front, scrcpy window up. Raises NotReady."""
    global _checked, _aligned
    if not force and time.time() - _checked < CHECK_EVERY:
        return
    if adb("get-state").strip() != "device":
        raise NotReady("phone not connected: plug it in, turn on USB debugging, and tap Allow on the phone")
    for attempt in range(2):
        out = shell("dumpsys power | grep -m1 mWakefulness=; dumpsys activity activities | grep -E 'ResumedActivity'")
        awake = "mWakefulness=Awake" in out
        if awake or attempt:
            break
        shell("input keyevent KEYCODE_WAKEUP")
        time.sleep(1.5)
    if not awake:
        raise NotReady("phone screen is off")
    if PKG not in out:
        raise NotReady("Pokémon GO isn't on the phone screen (locked, or another app is in front)")
    if NO_WINDOW:
        _checked = time.time()
        return
    if not scrcpy_window():
        start_scrcpy()
    if not _aligned:
        _aligned = check_align()
    _checked = time.time()


def check_align():
    """scrcpy shows the picture, adb taps the phone: make sure a spot means the same place in both.
    Same text in a scrcpy capture and in the phone's own screenshot must sit in the same place.
    -> False if the screen has too little text to tell (ready() tries again next time)."""
    import ui
    for attempt in range(3):
        _, cap_bounds = capture("/tmp/pvpc_align_scrcpy.png")
        raw = "/tmp/pvpc_align_phone.png"
        im = phone_shot()
        if im.width > im.height:
            raise NotReady("phone is sideways: turn it to portrait")
        if (im.width, im.height) != size():
            raise NotReady(f"phone screenshot is {im.width}x{im.height} but adb says the screen is {size()}")
        shape(im)[0].save(raw)
        a = {}
        for t in ui.ocr("/tmp/pvpc_align_scrcpy.png"):
            a.setdefault(t[4], []).append(t)
        b = {}
        for t in ui.ocr(raw):
            b.setdefault(t[4], []).append(t)
        pairs = [(a[k][0], b[k][0]) for k in a if len(a[k]) == 1 and len(b.get(k, [])) == 1 and len(k) >= 3]
        if len(pairs) < 3:
            print(f"android: only {len(pairs)} texts to line up on this screen, can't check positions yet", file=sys.stderr)
            return False
        dx = statistics.median(p[0][0] - p[1][0] for p in pairs)
        dy = statistics.median(p[0][1] - p[1][1] for p in pairs)
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return True
        time.sleep(1)  # the screen may have been moving: look again
    raise NotReady(f"scrcpy and the phone disagree on positions by {dx:+.3f}, {dy:+.3f} of the screen")


# ---------- doing ----------

def to_px(x, y):
    """Mac points (made from the latest capture's bounds) -> phone pixels"""
    if phone is None and NO_WINDOW:
        W, H = size()
        globals()["phone"] = [0.0, 0.0, float(W), float(H)]
    if phone is None:
        win = scrcpy_window()
        if not win:
            raise NotReady("no scrcpy window to work out where to tap")
        globals()["phone"] = list(content(*win[1:]))
    bx, by, bw, bh = phone
    W, H = size()
    px, py = (float(x) - bx) / bw * W, (float(y) - by) / bh * H
    if not (0 <= px < W and 0 <= py < H):
        raise NotReady(f"tap at {px:.0f},{py:.0f} is off the phone screen (or in the top strip)")
    return round(px), round(py)


_motion = None


def has_motionevent():
    global _motion
    if _motion is None:
        _motion = "motionevent" in shell("input 2>&1")
    return _motion


def drag(p1, p2, ms):
    """finger down, slide, pause, lift: the pause stops the list sliding on after the finger lifts"""
    (x1, y1), (x2, y2) = p1, p2
    if not has_motionevent():
        shell(f"input swipe {x1} {y1} {x2} {y2} {int(ms)}")
        return
    steps = [f"input motionevent DOWN {x1} {y1}"]
    n = random.randint(5, 7)
    for i in range(1, n + 1):
        f = i / n
        e = f * f * (3 - 2 * f)
        steps.append(f"input motionevent MOVE {round(x1 + (x2 - x1) * e)} {round(y1 + (y2 - y1) * e)}")
    steps += [f"sleep {random.uniform(0.12, 0.2):.2f}", f"input motionevent MOVE {x2} {y2}",
              f"input motionevent UP {x2} {y2}"]
    shell("; ".join(steps))


KEYCODES = {"delete": 67, "return": 66, " ": 62, "back": 4}


def type_text(text, lo=35, hi=80):
    """the whole text in one adb call: 'input text' per word, a space key between words.
    (lo, hi: the Mac's gap between keys, not needed here: input text never drops a shift)"""
    bad = [c for c in text if not (c.isascii() and c.isprintable()) or c in "%'\"\\`"]
    if bad:
        raise NotReady(f"can't type {bad[0]!r}")
    steps = []
    for i, word in enumerate(text.split(" ")):
        if i:
            steps.append("input keyevent 62")
        if word:
            steps.append(f"input text {shlex.quote(word)}")
    shell("; ".join(steps))


def key(name, cmd=False):
    if cmd and name == "a":  # select-all + delete on the Mac: here, jump to the end and delete everything
        name = "clear"
    elif cmd:
        raise NotReady(f"no Android version of cmd+{name}")
    if name == "clear":
        shell("input keyevent KEYCODE_MOVE_END; input keyevent " + " ".join(["67"] * 20))
    elif name in KEYCODES:
        shell(f"input keyevent {KEYCODES[name]}")
    elif len(name) == 1:
        type_text(name)
    else:
        raise NotReady(f"unknown key {name}")


ACTIONS = ("click", "drag", "scroll", "key", "type", "front")


def act(cmd, *a):
    """stand-in for the Mac helper's commands: same arguments, Mac points in, adb out"""
    global _tapped
    if cmd == "click":  # x y hold_ms: a swipe that doesn't move is a press held that long
        x, y = to_px(a[0], a[1])
        shell(f"input swipe {x} {y} {x} {y} {int(float(a[2]))}")
        _tapped = time.time()
    elif cmd == "drag":  # x1 y1 x2 y2 ms
        drag(to_px(a[0], a[1]), to_px(a[2], a[3]), float(a[4]))
    elif cmd == "scroll":  # x y dy steps: no wheel on a phone, drag the same way (dy < 0 moves the list down)
        drag(to_px(a[0], a[1]), to_px(a[0], float(a[1]) + float(a[2])), 500)
    elif cmd == "key":
        key(a[0], len(a) > 1 and a[1] == "cmd")
    elif cmd == "type":
        type_text(a[0], float(a[1]), float(a[2]))
    elif cmd == "front":
        ready()
        return "Pokémon GO\n"
    return ""


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a[:1] == ["check"]:
            ready(force=True)
            print(f"ok: phone {size()[0]}x{size()[1]}, Pokémon GO in front, scrcpy window up, "
                  + ("positions agree" if _aligned else "positions not checked yet (too little text on screen)"))
        elif a[:1] == ["type"] and len(a) == 2:
            type_text(a[1])
        elif a[:1] == ["key"] and len(a) == 2:
            key(a[1])
        else:
            sys.exit(__doc__)
    except NotReady as e:
        sys.exit(f"NOT READY: {e}")
