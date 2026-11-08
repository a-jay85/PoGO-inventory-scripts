"""Line tracing for watch.py runs: which lines of the run's checkout ran. watch.py puts this folder first on
PYTHONPATH, so every python3 the run starts (pogo.py's steps, the scripts they start) loads it at startup.

It does nothing unless POGO_TRACE is set (watch.py sets it to /tmp/pogo-watch/<stamp>.lines). Then it records,
with sys.monitoring LINE events, the lines that ran in .py files under POGO_TRACE_ROOT (the run's checkout).
Each spot reports once, then is switched off, so a run goes at full speed. Each process writes its own
<stamp>.lines.<pid>-<n>: {"skills/x/y.py": [line, ...]}, at exit, on SIGTERM, before an exec, and at most every
30 s as new lines come in. merge_gate.py reads them all.

It must never break or slow a phone script: any error just turns tracing off. Python without sys.monitoring
(before 3.12) isn't traced. It first runs the sitecustomize this one hides (Homebrew's), so that still happens.
Written for any python3 (the Mac's /usr/bin/python3 is 3.9).
"""
import os
import sys


def _chain():
    """run the sitecustomize this file hides, as Python would have"""
    try:
        import importlib.machinery, importlib.util
        here = os.path.dirname(os.path.realpath(__file__))
        rest = [p for p in sys.path if os.path.realpath(p or ".") != here]
        spec = importlib.machinery.PathFinder.find_spec("sitecustomize", rest)
        if spec and spec.origin and os.path.realpath(spec.origin) != os.path.realpath(__file__):
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
    except Exception:
        pass


_chain()


def _start():
    out = os.environ.get("POGO_TRACE")
    root = os.environ.get("POGO_TRACE_ROOT")
    mon = getattr(sys, "monitoring", None)
    if not out or not root or mon is None:
        return
    import atexit, json, signal, time
    root = os.path.realpath(root) + os.sep
    me = os.path.realpath(__file__)
    tool = None
    for t in (mon.COVERAGE_ID, 4, 5):
        try:
            mon.use_tool_id(t, "pogo-trace")
            tool = t
            break
        except ValueError:
            continue
    if tool is None:
        return
    hits = {}  # relpath -> set of lines
    where = {}  # co_filename -> relpath, or None (not ours)
    state = {"dirty": False, "last": time.time(), "busy": False, "path": None, "pid": None}
    DISABLE = mon.DISABLE

    def path():
        if state.get("pid") != os.getpid():  # (a new file per process: a fork or an exec keeps the pid)
            state["pid"] = os.getpid()
            state["path"] = "%s.%d-%d" % (out, os.getpid(), time.time_ns() % 10 ** 9)
        return state["path"]

    def flush():
        if state["busy"] or not state["dirty"]:
            return
        state["busy"] = True
        try:
            p = path()
            tmp = p + ".tmp"
            with open(tmp, "w") as f:
                json.dump({k: sorted(v) for k, v in hits.items()}, f)
            os.replace(tmp, p)
            state["dirty"] = False
            state["last"] = time.time()
        except Exception:
            pass
        finally:
            state["busy"] = False

    def ours(code):
        """the file's path in the checkout, or None"""
        fn = code.co_filename
        rel = where.get(fn, 0)
        if rel == 0:
            full = os.path.realpath(fn) if fn and not fn.startswith("<") else ""
            rel = full[len(root):] if full.startswith(root) and full != me and full.endswith(".py") else None
            where[fn] = rel
        return rel

    def start(code, offset):
        """a function's first start: only the checkout's code gets line events (the rest never pays for them)"""
        try:
            if ours(code) is not None:
                mon.set_local_events(tool, code, mon.events.LINE)
        except Exception:
            pass
        return DISABLE

    def line(code, n):
        try:
            rel = ours(code)
            if rel is not None:
                s = hits.get(rel)
                if s is None:
                    s = hits[rel] = set()
                s.add(n)
                state["dirty"] = True
                if time.time() - state["last"] > 30:
                    flush()
        except Exception:
            pass
        return DISABLE

    def stop(signum, frame):
        flush()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def before(fn):
        def wrapped(*a, **k):
            flush()
            return fn(*a, **k)
        wrapped.__name__ = fn.__name__
        return wrapped

    def forked():
        hits.clear()  # (a fork's child keeps the parent's lines: those are the parent's to write)
        state["path"] = None
        state["pid"] = None
        state["dirty"] = False

    mon.register_callback(tool, mon.events.LINE, line)
    mon.register_callback(tool, mon.events.PY_START, start)
    mon.set_events(tool, mon.events.PY_START)
    atexit.register(flush)
    try:
        if signal.getsignal(signal.SIGTERM) == signal.SIG_DFL:
            signal.signal(signal.SIGTERM, stop)
    except Exception:
        pass
    for name in ("execv", "execve", "_exit"):  # (an exec or _exit skips atexit)
        if hasattr(os, name):
            setattr(os, name, before(getattr(os, name)))
    try:
        os.register_at_fork(after_in_child=forked)
    except Exception:
        pass


try:
    _start()
except Exception:
    pass
