#!/usr/bin/env python3
"""Android phone for the /pvpc and /ivc scripts. Turned on with POGO_PHONE=android.
Sees the phone with its own screenshots (adb screencap) and taps and types with adb, so the Mac's mouse and
keyboard stay free. ui.py sends its helper calls (click, drag, scroll, key, type, front) here.

  POGO_PHONE=android python3 android.py check   phone plugged in (or on Wi-Fi, see adbwifi.py), Pokémon GO in front
  POGO_PHONE=android python3 android.py type <text>
  POGO_PHONE=android python3 android.py key <delete|return|back|clear|one character>
"""
import gzip, os, random, re, shlex, struct, subprocess, sys, threading, time
from PIL import Image

PKG = "com.nianticlabs.pokemongo"
WIDTH = 406  # captures get shrunk to the width of an iPhone Mirroring capture: some checks count pixels
IPHONE_H = 890  # ...and padded to its height: the iPhone's insets are taller. With the strips the search bar, tabs,
BOTTOM_PAD = 8  # dialogs, bottom buttons and the map's Poké Ball land within a few pixels of where the iPhone code expects them
CHECK_EVERY = 10  # seconds between ready() checks


class NotReady(Exception):
    """phone or game not in a state the scripts can work with"""


_picked = []  # pick() has run in this process
_last_adb = [0.0]  # when the last adb command (a tap, key, swipe...) finished: an older screenshot is stale


def adb(*a, timeout=30):
    if not _picked:
        pick()
    try:
        r = subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout)
    finally:
        _last_adb[0] = time.time()
    return r.stdout


def pick():
    """which link to the phone adb uses: USB first, then Wi-Fi (adbwifi.py keeps that one up). It goes in
    ANDROID_SERIAL, so every adb call goes to it: with both links up, a plain adb says "more than one device".
    Nothing up: connects the saved Wi-Fi address once. -> the serial, or None"""
    import adbwifi
    _picked.append(1)
    usb, wifi = adbwifi.devices()
    s = (usb or wifi or [adbwifi.connect()])[0]
    if s:
        os.environ["ANDROID_SERIAL"] = s
    return s


def shell(cmd, timeout=60):
    return adb("shell", cmd, timeout=timeout)


BRIGHT_FILE = os.path.expanduser("~/.config/pogo/android-brightness")  # "mode level" from before a Wi-Fi run


def dim():
    """over Wi-Fi (the phone is unplugged, no one is looking at it): screen brightness to 0 for the run. The old
    brightness goes in BRIGHT_FILE first, and a file already there is kept: a run that ended before restore()
    left 0 on the phone, and the file still holds the real one"""
    if ":" not in os.environ.get("ANDROID_SERIAL", ""):
        return
    if not os.path.exists(BRIGHT_FILE):
        mode, level = shell("settings get system screen_brightness_mode; settings get system screen_brightness").split()
        os.makedirs(os.path.dirname(BRIGHT_FILE), exist_ok=True)
        with open(BRIGHT_FILE, "w") as f:
            f.write(f"{mode} {level}\n")
    shell("settings put system screen_brightness_mode 0; settings put system screen_brightness 0")


def restore():
    """the brightness dim() saved back on the phone. -> True if there was one"""
    try:
        mode, level = open(BRIGHT_FILE).read().split()
    except (OSError, ValueError):
        return False
    shell(f"settings put system screen_brightness {int(level)}; settings put system screen_brightness_mode {int(mode)}")
    os.remove(BRIGHT_FILE)
    return True


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

bounds = None  # the padded picture of the latest capture, in Mac points (what ui.py's fractions are of)
phone = None  # where the phone itself sits, in Mac points: taps are converted with this


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


def raw_shot():
    """the phone's own screenshot (~0.3 s). adb can fail now and then (exit 255): once when looks came back to back
    (2026-10-25), twice on the first look after unlocking the phone (2026-11-01, 2026-11-03), where a second try
    after 0.5 s failed too. So a few tries over about 10 s before giving up, and the last error says what adb said.
    It can also hang with the phone fine (2026-10-27, 2026-11-10, 2026-11-11: no answer in 30 s, the next one took
    under 1 s), so a try that takes over 10 s is a failed try too (a shot takes 0.3-0.8 s)"""
    for wait in (1, 2, 3, 4, None):  # seconds before the next try
        try:
            if not _picked:
                pick()
            r = subprocess.run(["adb", "exec-out", "screencap | gzip -1"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:  # (run has already killed the hung adb)
            r = subprocess.CompletedProcess([], 124, b"", b"no answer in 10 s")
        if not r.returncode:
            break
        said = r.stderr.decode(errors="replace").strip() or "nothing"
        if wait is None:
            devices = adb("devices", "-l").strip().replace("\n", " | ")
            raise subprocess.CalledProcessError(r.returncode, f"adb screenshot (said: {said}; {devices})")
        print(f"android: screenshot failed (exit {r.returncode}, said: {said}), trying again in {wait} s",
              file=sys.stderr)
        time.sleep(wait)
        pick()  # the link may have changed: unplugged (Wi-Fi now), or Wi-Fi dropped
    raw = gzip.decompress(r.stdout)
    w, h = struct.unpack("<2I", raw[:8])
    return Image.frombuffer("RGBA", (w, h), raw[len(raw) - w * h * 4:], "raw", "RGBA", 0, 1).convert("RGB")


PREFETCH_AGE = 0.3  # seconds: a screenshot started this recently (and after the last adb command) counts as now.
# A script whose reads all look again till right can raise it (tradeable: 0.8). Not gymfeed: its berry count read early
# once fed 41 instead of 1
_next = [None]  # (when it started, its thread, [the picture or the error])


def phone_shot():
    """the phone's own screenshot. Each one starts the next in the background, so a look that follows (while the
    last one was being read) gets it without waiting. Only one started after the last tap or key, and lately"""
    pre, _next[0] = _next[0], None
    im = None
    if pre and pre[0] > _last_adb[0] and time.time() - pre[0] < PREFETCH_AGE:
        pre[1].join()
        if isinstance(pre[2][0], Image.Image):
            im = pre[2][0]
    if im is None:
        im = raw_shot()
    box = []

    def take():
        try:
            box.append(raw_shot())
        except Exception as e:  # (an error here only means no head start)
            box.append(e)
    th = threading.Thread(target=take, daemon=True)
    _next[0] = (time.time(), th, box)
    th.start()
    return im


def sharp(path="/tmp/pvpc_sharp.png"):
    """the phone's own screenshot in the capture layout, 3x bigger, for small symbols ('!', '&')"""
    shape(phone_shot(), 3)[0].save(path, compress_level=1)
    return path


_raw = [None]  # the phone's own screenshot the last capture() was made from


def sharp_last(path="/tmp/pvpc_sharp.png"):
    """sharp() of the last capture()'s own screenshot: no new one. Only right after that capture, so the two reads are
    of the same screen (a second read of small text at another size)"""
    shape(_raw[0], 3)[0].save(path, compress_level=1)
    return path


def capture(path):
    global bounds
    _raw[0] = phone_shot()
    im, top = shape(_raw[0])  # Mac "points" are the phone's own pixels here, so taps need no conversion
    im.save(path, compress_level=1)  # (the default packing took ~100 ms a look)
    W, H = size()
    globals()["phone"] = [0.0, 0.0, float(W), float(H)]
    k = W / WIDTH
    bounds = [0.0, -top * k, float(W), im.height * k]
    return path, list(bounds)


# ---------- getting ready ----------

_checked = 0.0


def ready(force=False):
    """phone plugged in and awake, Pokémon GO in front. Raises NotReady."""
    global _checked
    if not force and time.time() - _checked < CHECK_EVERY:
        return
    if not pick():
        raise NotReady("phone not connected: plug it in, turn on USB debugging, and tap Allow on the phone "
                       "(unplugged: same Wi-Fi as the Mac, and plugged in once since it restarted, see adbwifi.py)")
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
    _checked = time.time()


# ---------- doing ----------

def to_px(x, y):
    """Mac points (made from the latest capture's bounds) -> phone pixels"""
    if phone is None:
        W, H = size()
        globals()["phone"] = [0.0, 0.0, float(W), float(H)]
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


def slide():
    """(dx, dy) phone pixels a tap's finger moves while it's down: 0-3 each way, never both 0"""
    while True:
        dx, dy = random.randint(-3, 3), random.randint(-3, 3)
        if dx or dy:
            return dx, dy


def drag(p1, p2, ms, hold=None):
    """finger down, slide, pause, lift: the pause stops the list sliding on after the finger lifts.
    hold: ms to hold still first (a gym's Pokémon behind another one only follows a finger that held still)"""
    (x1, y1), (x2, y2) = p1, p2
    x2, y2 = x2 + random.randint(-4, 4), y2 + random.randint(-4, 4)
    bow = random.uniform(-0.04, 0.04)  # a thumb's path bends a little: this much of the length, sideways
    if not has_motionevent():
        shell(f"input swipe {x1} {y1} {x2} {y2} {int(ms)}")
        return
    steps = [f"input motionevent DOWN {x1} {y1}"] + ([f"sleep {hold / 1000:.2f}"] if hold else [])
    n = random.randint(5, 7)
    for i in range(1, n + 1):
        f = i / n
        e = f * f * (3 - 2 * f)
        b = bow * 4 * e * (1 - e)
        steps.append(f"input motionevent MOVE {round(x1 + (x2 - x1) * e - (y2 - y1) * b)} "
                     f"{round(y1 + (y2 - y1) * e + (x2 - x1) * b)}")
    steps += [f"sleep {random.uniform(0.12, 0.2):.2f}", f"input motionevent MOVE {x2} {y2}",
              f"input motionevent UP {x2} {y2}"]
    shell("; ".join(steps))


def hold_drag(fx1, fy1, fx2, fy2):
    """press, hold a moment, then slide (fractions of the screen). The list's slider only follows a finger that
    held still first: a plain swipe on it moves nothing (Pixel, 2026-10-09)"""
    W, H = size()
    x1, y1, x2, y2 = round(fx1 * W), round(fy1 * H), round(fx2 * W), round(fy2 * H)
    x2, y2 = x2 + random.randint(-4, 4), y2 + random.randint(-4, 4)
    steps = [f"input motionevent DOWN {x1} {y1}", f"sleep {random.uniform(0.35, 0.45):.2f}"]
    n = random.randint(4, 6)
    for i in range(1, n + 1):
        steps.append(f"input motionevent MOVE {round(x1 + (x2 - x1) * i / n)} {round(y1 + (y2 - y1) * i / n)}")
    steps += [f"sleep {random.uniform(0.12, 0.2):.2f}", f"input motionevent UP {x2} {y2}"]
    shell("; ".join(steps))


KEYCODES = {"delete": 67, "return": 66, " ": 62, "back": 4}


def type_text(text, lo=35, hi=80):
    """the whole text in one adb call: 'input text' per word, a space key between words.
    (lo, hi: the Mac's key timing, not needed here: input text never drops a shift)"""
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
    if cmd == "click":  # x y hold_ms: a swipe that doesn't move is a press held that long
        x, y = to_px(a[0], a[1])
        dx, dy = slide()  # a thumb rolls a pixel or two while it's down: well under the ~20 px that makes it a drag
        shell(f"input swipe {x} {y} {x + dx} {y + dy} {int(float(a[2]))}")
    elif cmd == "drag":  # x1 y1 x2 y2 ms [hold_ms]
        drag(to_px(a[0], a[1]), to_px(a[2], a[3]), float(a[4]), float(a[5]) if len(a) > 5 else None)
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
            print(f"ok: phone {size()[0]}x{size()[1]}, Pokémon GO in front, seeing it with the phone's own screenshots")
        elif a[:1] == ["type"] and len(a) == 2:
            type_text(a[1])
        elif a[:1] == ["key"] and len(a) == 2:
            key(a[1])
        else:
            sys.exit(__doc__)
    except NotReady as e:
        sys.exit(f"NOT READY: {e}")
